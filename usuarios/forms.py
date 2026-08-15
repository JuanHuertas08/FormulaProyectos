from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Proyecto, DocumentoSoporte

class RegistroForm(forms.ModelForm):
    nombres = forms.CharField(label="Nombres", widget=forms.TextInput(attrs={'placeholder': 'Ej. Juan Pedro'}))
    apellidos = forms.CharField(label="Apellidos", widget=forms.TextInput(attrs={'placeholder': 'Ej. Pérez Castro'}))
    telefono = forms.CharField(label="Número de teléfono", widget=forms.TextInput(attrs={'placeholder': '+57 300...'}))
    fecha_nacimiento = forms.DateField(label="Fecha de nacimiento", widget=forms.DateInput(attrs={'type': 'date'}))
    pais = forms.CharField(label="País de residencia")
    ciudad = forms.CharField(label="Ciudad de residencia")
    email = forms.EmailField(label="Correo electrónico")
    confirmar_email = forms.EmailField(label="Confirmar correo electrónico")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput())
    confirmar_password = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'nombres', 'apellidos', 'email', 'telefono']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("email") != cleaned_data.get("confirmar_email"):
            raise ValidationError("Los correos electrónicos no coinciden.")
        if cleaned_data.get("password") != cleaned_data.get("confirmar_password"):
            raise ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

class DynamicMultipleChoiceField(forms.MultipleChoiceField):
    """MultipleChoiceField cuyas opciones válidas se cargan por JS en tiempo de ejecución
    (vía AJAX según el país seleccionado), por lo que no pueden declararse de antemano."""
    def valid_value(self, value):
        return True


class Paso1ProjectForm(forms.ModelForm):

    descripcion_detallada = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 4}),
        required=False,
        label="Descripción detallada"
    )

    
    # 1. Definición de Opciones (Choices)
    ODS_CHOICES = [
        ('1', '1. Fin de la pobreza'), ('2', '2. Hambre cero'), ('3', '3. Salud y bienestar'),
        ('4', '4. Educación de calidad'), ('5', '5. Igualdad de género'), ('6', '6. Agua limpia y saneamiento'),
        ('7', '7. Energía asequible'), ('8', '8. Trabajo decente y crecimiento'), ('9', '9. Industria, innovación e infra.'),
        ('10', '10. Reducción de desigualdades'), ('11', '11. Ciudades sostenibles'), ('12', '12. Producción y consumo resp.'),
        ('13', '13. Acción por el clima'), ('14', '14. Vida submarina'), ('15', '15. Vida de ecosistemas terrestres'),
        ('16', '16. Paz, justicia e inst. sólidas'), ('17', '17. Alianzas para lograr objetivos')
    ]

    CATEGORIA_CHOICES = [
        ('', '--- Seleccione una categoría ---'),
        ('PUBLICO', 'Público'),
        ('PRIVADO', 'Privado'),
    ]

    PAISES_CHOICES = [
        ('', '--- Seleccione un País ---'),
        ('COL', 'Colombia'),
        ('SLV', 'El Salvador'),
        ('HND', 'Honduras'),
    ]

    # 2. Campos Extra (No están directamente en el modelo o requieren lógica especial)
    categoria = forms.ChoiceField(
        choices=CATEGORIA_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none bg-white'})
    )

    pais = forms.ChoiceField(
        choices=PAISES_CHOICES, 
        widget=forms.Select(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none bg-white'})
    )

    objetivos_desarrollo = forms.MultipleChoiceField(
        choices=ODS_CHOICES, 
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-1 md:grid-cols-2 gap-2'}),
        required=False
    )

    leyes = DynamicMultipleChoiceField(
        choices=[], # Se llena dinámicamente con JS
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'space-y-2'})
    )

    # Paso 3: Cronograma
    fecha_fin = forms.DateField(
        label="Fecha de Finalización",
        required=False,
        widget=forms.DateInput(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'type': 'date'})
    )

    # Paso 4: Recursos
    presupuesto = forms.DecimalField(
        label="Presupuesto Estimado (USD)",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'placeholder': '0.00', 'step': '0.01'})
    )

    # Paso 5: Riesgos
    riesgos = forms.CharField(
        label="Identificación de Riesgos",
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 5, 'placeholder': 'Menciona posibles obstáculos críticos'})
    )

    # 3. Configuración del Modelo
    class Meta:
        model = Proyecto
        fields = [
            'nombre', 'categoria', 'fecha_inicio', 'descripcion',
            'articulacion_nacional', 'articulacion_regional',
            'articulacion_municipal', 'articulacion_institucional',
            'pais', 'fecha_fin', 'presupuesto', 'riesgos',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-3 border rounded-lg', 'placeholder': 'Ej: Proyecto Integración social'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'w-full p-3 border rounded-lg', 'type': 'date'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 3}),
            'articulacion_nacional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_regional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_municipal': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_institucional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
                    }