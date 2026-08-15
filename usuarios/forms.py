from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Proyecto, DocumentoSoporte

class RegistroForm(forms.ModelForm):
    nombres = forms.CharField(label=_("Nombres"), widget=forms.TextInput(attrs={'placeholder': 'Ej. Juan Pedro'}))
    apellidos = forms.CharField(label=_("Apellidos"), widget=forms.TextInput(attrs={'placeholder': 'Ej. Pérez Castro'}))
    telefono = forms.CharField(label=_("Número de teléfono"), widget=forms.TextInput(attrs={'placeholder': '+57 300...'}))
    fecha_nacimiento = forms.DateField(label=_("Fecha de nacimiento"), widget=forms.DateInput(attrs={'type': 'date'}))
    pais = forms.CharField(label=_("País de residencia"))
    ciudad = forms.CharField(label=_("Ciudad de residencia"))
    email = forms.EmailField(label=_("Correo electrónico"))
    confirmar_email = forms.EmailField(label=_("Confirmar correo electrónico"))
    password = forms.CharField(label=_("Contraseña"), widget=forms.PasswordInput())
    confirmar_password = forms.CharField(label=_("Confirmar contraseña"), widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'nombres', 'apellidos', 'email', 'telefono']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("email") != cleaned_data.get("confirmar_email"):
            raise ValidationError(_("Los correos electrónicos no coinciden."))
        if cleaned_data.get("password") != cleaned_data.get("confirmar_password"):
            raise ValidationError(_("Las contraseñas no coinciden."))
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
        label=_("Descripción detallada")
    )


    # 1. Definición de Opciones (Choices)
    ODS_CHOICES = [
        ('1', _('1. Fin de la pobreza')), ('2', _('2. Hambre cero')), ('3', _('3. Salud y bienestar')),
        ('4', _('4. Educación de calidad')), ('5', _('5. Igualdad de género')), ('6', _('6. Agua limpia y saneamiento')),
        ('7', _('7. Energía asequible')), ('8', _('8. Trabajo decente y crecimiento')), ('9', _('9. Industria, innovación e infra.')),
        ('10', _('10. Reducción de desigualdades')), ('11', _('11. Ciudades sostenibles')), ('12', _('12. Producción y consumo resp.')),
        ('13', _('13. Acción por el clima')), ('14', _('14. Vida submarina')), ('15', _('15. Vida de ecosistemas terrestres')),
        ('16', _('16. Paz, justicia e inst. sólidas')), ('17', _('17. Alianzas para lograr objetivos'))
    ]

    CATEGORIA_CHOICES = [
        ('', _('--- Seleccione una categoría ---')),
        ('PUBLICO', _('Público')),
        ('PRIVADO', _('Privado')),
    ]

    PAISES_CHOICES = [
        ('', _('--- Seleccione un País ---')),
        ('COL', _('Colombia')),
        ('SLV', _('El Salvador')),
        ('HND', _('Honduras')),
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
        label=_("Fecha de Finalización"),
        required=False,
        widget=forms.DateInput(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'type': 'date'})
    )

    # Paso 4: Recursos
    presupuesto = forms.DecimalField(
        label=_("Presupuesto Estimado (USD)"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'placeholder': '0.00', 'step': '0.01'})
    )

    # Paso 5: Riesgos
    riesgos = forms.CharField(
        label=_("Identificación de Riesgos"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 5, 'placeholder': _('Menciona posibles obstáculos críticos')})
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