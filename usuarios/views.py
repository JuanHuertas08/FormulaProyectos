from django.shortcuts import render, redirect
from .forms import RegistroForm  # El punto es clave ahora
from django.contrib import messages

def registrar_usuario(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            # Mapeo de campos adicionales a campos estándar de Django
            user.first_name = form.cleaned_data['nombres']
            user.last_name = form.cleaned_data['apellidos']
            user.email = form.cleaned_data['email']
            user.save()
            messages.success(request, "¡Registro exitoso! Ya puedes iniciar sesión.")
            return redirect('login')
    else:
        form = RegistroForm()
    # Asegúrate de que la ruta del template sea correcta
    return render(request, 'registration/registrar.html', {'form': form})

def home(request):
    return render(request, 'home.html') 

from django.shortcuts import render, redirect
from .forms import RegistroForm
from .models import Perfil # Importa el nuevo modelo
from django.contrib import messages

def registrar_usuario(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid(): # Línea 34 (según tu error)
            # Todo esto debe tener una sangría (indentación) hacia la derecha
            user = form.save(commit=False) 
            user.set_password(form.cleaned_data['password'])
            user.first_name = form.cleaned_data['nombres']
            user.last_name = form.cleaned_data['apellidos']
            user.email = form.cleaned_data['email']
            user.save() 

            # Actualizamos el perfil que la SEÑAL creó automáticamente
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