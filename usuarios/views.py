from decimal import Decimal

from django.db import transaction
from django.shortcuts import render, redirect
from .forms import RegistroForm, Paso1ProjectForm, ActividadFormSet, RubroFormSet, RiesgoFormSet
from .models import Perfil, DocumentoSoporte
from .diagnostico import generar_diagnostico, DiagnosticoError, FUENTES_POR_PAIS
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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
    """Genera (vía IA + búsqueda web restringida a fuentes oficiales de
    planeación) el diagnóstico de contexto del Paso 2, a partir de los datos
    del proyecto capturados en el Paso 1."""
    pais = request.POST.get('pais', '')
    categoria = request.POST.get('categoria', '')
    nombre = request.POST.get('nombre', '')
    descripcion = request.POST.get('descripcion', '')

    if pais not in FUENTES_POR_PAIS:
        return JsonResponse({'error': _('Selecciona primero el país del proyecto.')}, status=400)
    if not nombre or not descripcion:
        return JsonResponse({'error': _('Completa el nombre y la descripción del proyecto en el Paso 1.')}, status=400)

    try:
        resultado = generar_diagnostico(
            pais=pais, categoria=categoria, nombre=nombre, descripcion=descripcion,
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
    """Formularios del formset con datos y no marcados para eliminar."""
    return [
        f for f in formset.forms
        if f.has_changed() and not (formset.can_delete and formset._should_delete_form(f))
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


@login_required
def crear_proyecto(request):
    """
    Vista única que orquesta el Wizard de 6 pasos.
    El formulario completo se envía en un solo POST (el JS solo oculta/muestra
    secciones), así que al validar se persiste el Proyecto directamente en la BD,
    junto con las tablas del cronograma (Paso 3), presupuesto (Paso 4) y
    matriz de riesgos (Paso 5).
    """
    paso_con_error = 1
    if request.method == 'POST':
        form = Paso1ProjectForm(request.POST, request.FILES)
        actividades = ActividadFormSet(request.POST, prefix=PREFIJO_ACTIVIDADES)
        rubros = RubroFormSet(request.POST, prefix=PREFIJO_RUBROS)
        riesgos = RiesgoFormSet(request.POST, prefix=PREFIJO_RIESGOS)

        form_ok = form.is_valid()
        actividades_ok = actividades.is_valid() and form_ok and _validar_cronograma(form, actividades)
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

            messages.success(request, _('Proyecto "%(nombre)s" creado con éxito.') % {'nombre': proyecto.nombre})
            return redirect('home')

        # Reabrir el wizard en el primer paso que tenga errores
        errores_paso_1 = {'nombre', 'categoria', 'fecha_inicio', 'descripcion', 'pais'}
        if form.errors.keys() & errores_paso_1:
            paso_con_error = 1
        elif not actividades_ok or 'fecha_fin' in form.errors:
            paso_con_error = 3
        elif not rubros_ok:
            paso_con_error = 4
        elif not riesgos_ok:
            paso_con_error = 5
    else:
        form = Paso1ProjectForm()
        actividades = ActividadFormSet(prefix=PREFIJO_ACTIVIDADES)
        rubros = RubroFormSet(prefix=PREFIJO_RUBROS)
        riesgos = RiesgoFormSet(prefix=PREFIJO_RIESGOS)

    return render(request, 'usuarios/crear_proyecto.html', {
        'form': form,
        'actividades': actividades,
        'rubros': rubros,
        'riesgos': riesgos,
        'paso_inicial': paso_con_error,
        'leyes_seleccionadas': request.POST.getlist('leyes') if request.method == 'POST' else [],
    })
