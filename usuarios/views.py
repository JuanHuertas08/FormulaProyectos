from django.shortcuts import render, redirect
from .forms import RegistroForm, Paso1ProjectForm
from .models import Perfil, DocumentoSoporte
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

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

            messages.success(request, "¡Cuenta creada con éxito!")
            return redirect('login')
    else:
        form = RegistroForm()
    return render(request, 'registration/registrar.html', {'form': form})

@login_required
def crear_proyecto(request):
    """
    Vista única que orquesta el Wizard de 6 pasos.
    El formulario completo se envía en un solo POST (el JS solo oculta/muestra
    secciones), así que al validar se persiste el Proyecto directamente en la BD.
    """
    if request.method == 'POST':
        form = Paso1ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.usuario = request.user
            proyecto.objetivos_desarrollo = ','.join(form.cleaned_data.get('objetivos_desarrollo', []))
            proyecto.leyes = ','.join(form.cleaned_data.get('leyes', []))
            proyecto.save()

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

            messages.success(request, f'Proyecto "{proyecto.nombre}" creado con éxito.')
            return redirect('home')
    else:
        form = Paso1ProjectForm()

    return render(request, 'usuarios/crear_proyecto.html', {'form': form})
