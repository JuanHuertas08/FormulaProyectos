from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class RegistroForm(forms.ModelForm):
    # Campos adicionales
    nombres = forms.CharField(label="Nombres", widget=forms.TextInput(attrs={'placeholder': 'Ej. Juan Pedro'}))
    apellidos = forms.CharField(label="Apellidos", widget=forms.TextInput(attrs={'placeholder': 'Ej. Pérez Castro'}))
    telefono = forms.CharField(label="Número de teléfono", widget=forms.TextInput(attrs={'placeholder': '+57 300...'}))
    fecha_nacimiento = forms.DateField(label="Fecha de nacimiento", widget=forms.DateInput(attrs={'type': 'date'}))
    pais = forms.CharField(label="País de residencia")
    ciudad = forms.CharField(label="Ciudad de residencia")
    
    # Campos de correo con confirmación
    email = forms.EmailField(label="Correo electrónico")
    confirmar_email = forms.EmailField(label="Confirmar correo electrónico")
    
    # Campos de contraseña
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput())
    confirmar_password = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'nombres', 'apellidos', 'email', 'telefono'] # Campos base

    def clean(self):
        cleaned_data = super().clean()
        # Validar correos
        email = cleaned_data.get("email")
        conf_email = cleaned_data.get("confirmar_email")
        if email != conf_email:
            raise ValidationError("Los correos electrónicos no coinciden.")

        # Validar contraseñas
        pass1 = cleaned_data.get("password")
        pass2 = cleaned_data.get("confirmar_password")
        if pass1 != pass2:
            raise ValidationError("Las contraseñas no coinciden.")
        
        return cleaned_data