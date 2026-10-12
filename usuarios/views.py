from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from .forms import RegistroForm, Paso1ProjectForm, ActividadFormSet, RubroFormSet, RiesgoFormSet
from .models import Perfil, Proyecto, DocumentoSoporte
from .diagnostico import generar_diagnostico, DiagnosticoError, FUENTES_POR_PAIS, SECCIONES as SECCIONES_DIAGNOSTICO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

# Relaciona cada campo de archivo del Paso 1 con su sección de DocumentoSoporte
SECCIONES_SOPORTE = {
    'int': 'INT',
    'nac': 'NAC',
    'reg': 'REG',
    'mun': 'MUN',
    'ins': 'INS',
}

def obtener_leyes_por_pais(request):
    pais_codigo = request.GET.get('pais')
    
    # Base de datos simulada de leyes
    leyes_data = {
        'COL': {
            'politica': ['Política Nacional de Envejecimiento', 'Ley 100 de 1993'],
            'resolucion': ['Resolución 3100 de 2019', 'Resolución 518 de 2015'],
            'decretos': ['Decreto 780 de 2016', 'Decreto 1427 de 2022'],
            'otras': ['Circular 008 de 2018']
        },
        'SLV': {
            'politica': ['Política Nacional de Salud', 'Ley de Deberes y Derechos'],
            'decretos': ['Decreto Ejecutivo 12', 'Decreto 45 de Salud'],
            # ... puedes agregar más
        },
        'HND': {
            'politica': ['Marco Estratégico de Salud (Honduras)'],
            'resolucion': ['Norma Técnica de Pediatría'],
            'decretos': ['Decreto Legislativo 15-2020']
        }
    }
    
    data = leyes_data.get(pais_codigo, {})
    return JsonResponse(data)


@login_required
@require_POST
def buscar_diagnostico(request):
    """Genera (vía IA + búsqueda web restringida a fuentes oficiales) el
    diagnóstico de contexto del Paso 2 a partir de los datos del Paso 1.
    Con el parámetro "seccion" genera solo esa sección."""
    pais = request.POST.get('pais', '')
    nombre = request.POST.get('nombre', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    seccion = request.POST.get('seccion') or None

    if pais not in FUENTES_POR_PAIS:
        return JsonResponse({'error': _('Selecciona primero el país del proyecto.')}, status=400)
    if not nombre or not descripcion:
        return JsonResponse({'error': _('Completa el nombre y la descripción del proyecto en el Paso 1.')}, status=400)
    if seccion and seccion not in SECCIONES_DIAGNOSTICO:
        return JsonResponse({'error': _('Sección del diagnóstico no válida.')}, status=400)

    # La IA trabaja en español: enviar las etiquetas (no los códigos) en español
    with translation.override('es'):
        etiquetas_ods = dict(Paso1ProjectForm.ODS_CHOICES)
        etiquetas_categoria = dict(Paso1ProjectForm.CATEGORIA_CHOICES)
        categoria = str(etiquetas_categoria.get(request.POST.get('categoria', ''), ''))
        ods = [str(etiquetas_ods[c]) for c in request.POST.getlist('ods') if c in etiquetas_ods]

    contexto = {
        'fecha_inicio': request.POST.get('fecha_inicio', ''),
        'fecha_fin': request.POST.get('fecha_fin', ''),
        'ods': ods,
        'leyes': request.POST.getlist('leyes'),
        'articulacion_nacional': request.POST.get('articulacion_nacional', ''),
        'articulacion_regional': request.POST.get('articulacion_regional', ''),
        'articulacion_municipal': request.POST.get('articulacion_municipal', ''),
        'articulacion_institucional': request.POST.get('articulacion_institucional', ''),
        'descripcion_detallada': request.POST.get('descripcion_detallada', ''),
    }

    try:
        resultado = generar_diagnostico(
            pais=pais, categoria=categoria, nombre=nombre, descripcion=descripcion,
            contexto=contexto, seccion=seccion,
        )
    except DiagnosticoError as exc:
        return JsonResponse({'error': str(exc)}, status=503)

    return JsonResponse(resultado)

def home(request):
    """Página de inicio del sistema."""
    return render(request, 'home.html') 

def registrar_usuario(request):
    """Maneja el registro de nuevos usuarios y sus perfiles."""
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False) 
            user.set_password(form.cleaned_data['password'])
            user.first_name = form.cleaned_data['nombres']
            user.last_name = form.cleaned_data['apellidos']
            user.email = form.cleaned_data['email']
            user.save() 

            # El perfil se suele crear vía signals, aquí lo actualizamos
            perfil = user.perfil 
            perfil.telefono = form.cleaned_data.get('telefono')
            perfil.pais = form.cleaned_data.get('pais')
            perfil.ciudad = form.cleaned_data.get('ciudad')
            perfil.fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
            perfil.save()

            messages.success(request, _("¡Cuenta creada con éxito!"))
            return redirect('login')
    else:
        form = RegistroForm()
    return render(request, 'registration/registrar.html', {'form': form})

# Prefijos de los formsets de los pasos 3, 4 y 5 (usados también por el JS
# del template para clonar filas).
PREFIJO_ACTIVIDADES = 'actividades'
PREFIJO_RUBROS = 'rubros'
PREFIJO_RIESGOS = 'riesgos_matriz'


def _filas_vigentes(formset):
    """Formularios del formset con datos (filas ya guardadas o nuevas con
    cambios) y no marcados para eliminar."""
    return [
        f for f in formset.forms
        if (f.instance.pk or f.has_changed()) and not formset._should_delete_form(f)
    ]


def _validar_cronograma(form, actividades):
    """Las actividades deben caer dentro del rango de fechas del proyecto."""
    inicio = form.cleaned_data.get('fecha_inicio')
    fin = form.cleaned_data.get('fecha_fin')
    valido = True
    for f in _filas_vigentes(actividades):
        act_inicio = f.cleaned_data.get('fecha_inicio')
        act_fin = f.cleaned_data.get('fecha_fin')
        if inicio and act_inicio and act_inicio < inicio:
            f.add_error('fecha_inicio', _('Inicia antes que el proyecto.'))
            valido = False
        if fin and act_fin and act_fin > fin:
            f.add_error('fecha_fin', _('Termina después que el proyecto.'))
            valido = False
    return valido


def _paso_valido(valor, defecto=1):
    try:
        return min(max(int(valor), 1), 6)
    except (TypeError, ValueError):
        return defecto


@login_required
def crear_proyecto(request, pk=None):
    """
    Wizard de 6 pasos para crear (sin pk) o continuar/editar (con pk) un proyecto.

    Todo el formulario se envía en un solo POST (el JS solo oculta/muestra
    pasos) con un campo "accion":
    - "borrador" (botón "Guardar avance" de los pasos 1 a 5): guarda lo que haya,
      exigiendo solo el nombre, deja el proyecto "En Proceso" y vuelve al mismo paso.
    - "finalizar" (botón del Paso 6): valida todo, guarda y deja el proyecto "Completo".
    """
    proyecto = get_object_or_404(Proyecto, pk=pk, usuario=request.user) if pk else None
    paso_inicial = _paso_valido(request.GET.get('paso'), proyecto.paso_actual if proyecto else 1)

    if request.method == 'POST':
        borrador = request.POST.get('accion') == 'borrador'
        paso_enviado = _paso_valido(request.POST.get('paso'))
        form = Paso1ProjectForm(request.POST, request.FILES, instance=proyecto, borrador=borrador)
        actividades = ActividadFormSet(request.POST, instance=proyecto, prefix=PREFIJO_ACTIVIDADES)
        rubros = RubroFormSet(request.POST, instance=proyecto, prefix=PREFIJO_RUBROS)
        riesgos = RiesgoFormSet(request.POST, instance=proyecto, prefix=PREFIJO_RIESGOS)

        form_ok = form.is_valid()
        actividades_ok = actividades.is_valid() and form_ok and (borrador or _validar_cronograma(form, actividades))
        rubros_ok = rubros.is_valid()
        riesgos_ok = riesgos.is_valid()

        if form_ok and actividades_ok and rubros_ok and riesgos_ok:
            with transaction.atomic():
                proyecto = form.save(commit=False)
                proyecto.usuario = request.user
                proyecto.objetivos_desarrollo = ','.join(form.cleaned_data.get('objetivos_desarrollo', []))
                proyecto.leyes = ','.join(form.cleaned_data.get('leyes', []))
                # El presupuesto total es la suma de los rubros del Paso 4
                proyecto.presupuesto = sum(
                    (f.cleaned_data['monto'] for f in _filas_vigentes(rubros)), Decimal('0')
                ) or None
                if borrador:
                    proyecto.estado = Proyecto.ESTADO_EN_PROCESO
                    proyecto.paso_actual = paso_enviado
                else:
                    proyecto.estado = Proyecto.ESTADO_COMPLETO
                    proyecto.paso_actual = 6
                proyecto.save()

                for formset in (actividades, rubros, riesgos):
                    formset.instance = proyecto
                    formset.save()

                # Documentos de soporte: uno por sección que tenga archivo adjunto
                for sufijo, seccion in SECCIONES_SOPORTE.items():
                    archivo = request.FILES.get(f'archivo_{sufijo}')
                    if archivo:
                        DocumentoSoporte.objects.create(
                            proyecto=proyecto,
                            archivo=archivo,
                            tipo_documento=request.POST.get(f'tipo_archivo_{sufijo}', 'OTRO'),
                            seccion=seccion,
                        )

            if borrador:
                messages.success(request, _('Proyecto guardado temporalmente. Estado: En Proceso.'))
                url = reverse('editar_proyecto', args=[proyecto.pk])
                return redirect(f'{url}?paso={paso_enviado}')

            messages.success(
                request,
                _('Proyecto "%(nombre)s" almacenado satisfactoriamente. Estado: Completo.') % {'nombre': proyecto.nombre},
            )
            return redirect('home')

        # Reabrir el wizard en el primer paso que tenga errores
        errores_paso_1 = {'nombre', 'categoria', 'fecha_inicio', 'descripcion', 'pais'}
        if form.errors.keys() & errores_paso_1:
            paso_inicial = 1
        elif not actividades_ok or 'fecha_fin' in form.errors:
            paso_inicial = 3
        elif not rubros_ok:
            paso_inicial = 4
        elif not riesgos_ok:
            paso_inicial = 5
        else:
            paso_inicial = paso_enviado
        leyes_seleccionadas = request.POST.getlist('leyes')
    else:
        form = Paso1ProjectForm(instance=proyecto)
        actividades = ActividadFormSet(instance=proyecto, prefix=PREFIJO_ACTIVIDADES)
        rubros = RubroFormSet(instance=proyecto, prefix=PREFIJO_RUBROS)
        riesgos = RiesgoFormSet(instance=proyecto, prefix=PREFIJO_RIESGOS)
        leyes_seleccionadas = proyecto.leyes.split(',') if proyecto and proyecto.leyes else []

    # Documentos ya cargados, agrupados por sufijo de sección (int, nac, ...)
    documentos = {sufijo: [] for sufijo in SECCIONES_SOPORTE}
    if proyecto and proyecto.pk:
        seccion_a_sufijo = {v: k for k, v in SECCIONES_SOPORTE.items()}
        for doc in proyecto.documentos.all():
            documentos[seccion_a_sufijo[doc.seccion]].append(doc)

    return render(request, 'usuarios/crear_proyecto.html', {
        'form': form,
        'proyecto': proyecto if proyecto and proyecto.pk else None,
        'actividades': actividades,
        'rubros': rubros,
        'riesgos': riesgos,
        'paso_inicial': paso_inicial,
        'leyes_seleccionadas': leyes_seleccionadas,
        'documentos': documentos,
    })
