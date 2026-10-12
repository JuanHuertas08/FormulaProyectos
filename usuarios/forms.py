from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import validar_descripcion_minima, Proyecto, DocumentoSoporte, ActividadCronograma, RubroPresupuesto, RiesgoProyecto

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
    # Nombres oficiales de los ODS (el número se muestra aparte, en el color
    # oficial de cada objetivo; ver .ods-N en crear_proyecto.html)
    ODS_CHOICES = [
        ('1', _('Fin de la pobreza')), ('2', _('Hambre cero')), ('3', _('Salud y bienestar')),
        ('4', _('Educación de calidad')), ('5', _('Igualdad de género')), ('6', _('Agua limpia y saneamiento')),
        ('7', _('Energía asequible y no contaminante')), ('8', _('Trabajo decente y crecimiento económico')),
        ('9', _('Industria, innovación e infraestructura')), ('10', _('Reducción de las desigualdades')),
        ('11', _('Ciudades y comunidades sostenibles')), ('12', _('Producción y consumo responsables')),
        ('13', _('Acción por el clima')), ('14', _('Vida submarina')), ('15', _('Vida de ecosistemas terrestres')),
        ('16', _('Paz, justicia e instituciones sólidas')), ('17', _('Alianzas para lograr los objetivos')),
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
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'ods-check h-4 w-4 shrink-0 mt-0.5 accent-[#c2410c] cursor-pointer'}),
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
        widget=forms.DateInput(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'type': 'date'}, format='%Y-%m-%d')
    )

    # Paso 4: Recursos. El total se calcula a partir de los rubros (ver
    # ProyectoRubroFormSet); el campo queda solo lectura en la UI.
    presupuesto = forms.DecimalField(
        label=_("Presupuesto Total (USD)"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'w-full p-3 border rounded-lg bg-gray-50 font-bold', 'readonly': 'readonly', 'step': '0.01'})
    )

    # Paso 5: Riesgos
    riesgos = forms.CharField(
        label=_("Observaciones generales sobre riesgos"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 3, 'placeholder': _('Supuestos, dependencias externas u otros comentarios')})
    )

    # Paso 2: Diagnóstico del contexto (cargado por IA, editable/ampliable)
    diagnostico_cifras = forms.CharField(
        label=_("Cifras y datos estadísticos"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 10})
    )
    diagnostico_antecedentes = forms.CharField(
        label=_("Antecedentes (últimos 5 años)"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 10})
    )
    diagnostico_necesidades = forms.CharField(
        label=_("Necesidades y desafíos"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-orange-500 outline-none', 'rows': 10})
    )
    diagnostico_fuentes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'hidden'})
    )

    # 3. Configuración del Modelo
    class Meta:
        model = Proyecto
        fields = [
            'nombre', 'categoria', 'fecha_inicio', 'descripcion', 'descripcion_detallada',
            'articulacion_nacional', 'articulacion_regional',
            'articulacion_municipal', 'articulacion_institucional',
            'pais', 'fecha_fin', 'presupuesto', 'riesgos',
            'diagnostico_cifras', 'diagnostico_antecedentes',
            'diagnostico_necesidades', 'diagnostico_fuentes',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-3 border rounded-lg', 'placeholder': 'Ej: Proyecto Integración social'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'w-full p-3 border rounded-lg', 'type': 'date'}, format='%Y-%m-%d'),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 3, 'minlength': 50}),
            'articulacion_nacional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_regional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_municipal': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
            'articulacion_institucional': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg', 'rows': 2}),
                    }

    # Campos del Paso 1 obligatorios para finalizar el proyecto. Un borrador
    # ("Guardar avance") solo exige el nombre.
    CAMPOS_OBLIGATORIOS_FINAL = ['categoria', 'fecha_inicio', 'descripcion', 'pais']

    def __init__(self, *args, borrador=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.borrador = borrador
        for nombre in self.CAMPOS_OBLIGATORIOS_FINAL:
            self.fields[nombre].required = not borrador
        if not borrador:
            self.fields['descripcion'].validators.append(validar_descripcion_minima)
        # Al editar, reflejar los ODS guardados (texto separado por comas)
        if self.instance.pk and self.instance.objetivos_desarrollo:
            self.initial['objetivos_desarrollo'] = self.instance.objetivos_desarrollo.split(',')

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')
        if inicio and fin and fin < inicio:
            self.add_error('fecha_fin', _('La fecha de finalización no puede ser anterior a la fecha de inicio.'))
        return cleaned_data


# --- Pasos 3, 4 y 5: tablas dinámicas (filas agregadas/eliminadas por JS) ---

CELDA = 'w-full p-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none bg-white'


class ActividadForm(forms.ModelForm):
    class Meta:
        model = ActividadCronograma
        fields = ['tipo', 'nombre', 'responsable', 'fecha_inicio', 'fecha_fin', 'entregable']
        widgets = {
            'tipo': forms.Select(attrs={'class': CELDA}),
            'nombre': forms.TextInput(attrs={'class': CELDA, 'placeholder': _('Ej: Diagnóstico participativo')}),
            'responsable': forms.TextInput(attrs={'class': CELDA}),
            'fecha_inicio': forms.DateInput(attrs={'class': CELDA, 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'class': CELDA, 'type': 'date'}, format='%Y-%m-%d'),
            'entregable': forms.TextInput(attrs={'class': CELDA}),
        }

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')
        if inicio and fin and fin < inicio:
            self.add_error('fecha_fin', _('El fin de la actividad no puede ser anterior a su inicio.'))
        return cleaned_data


class RubroForm(forms.ModelForm):
    class Meta:
        model = RubroPresupuesto
        fields = ['rubro', 'descripcion', 'fuente', 'monto']
        widgets = {
            'rubro': forms.Select(attrs={'class': CELDA}),
            'descripcion': forms.TextInput(attrs={'class': CELDA, 'placeholder': _('Detalle del gasto')}),
            'fuente': forms.Select(attrs={'class': CELDA}),
            'monto': forms.NumberInput(attrs={'class': CELDA + ' text-right', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is not None and monto <= 0:
            raise ValidationError(_('El monto debe ser mayor que cero.'))
        return monto


class RiesgoForm(forms.ModelForm):
    class Meta:
        model = RiesgoProyecto
        fields = ['descripcion', 'tipo', 'probabilidad', 'impacto', 'mitigacion', 'responsable']
        widgets = {
            'descripcion': forms.TextInput(attrs={'class': CELDA, 'placeholder': _('Ej: Retraso en desembolsos')}),
            'tipo': forms.Select(attrs={'class': CELDA}),
            'probabilidad': forms.Select(attrs={'class': CELDA}),
            'impacto': forms.Select(attrs={'class': CELDA}),
            'mitigacion': forms.Textarea(attrs={'class': CELDA, 'rows': 2}),
            'responsable': forms.TextInput(attrs={'class': CELDA}),
        }


def _formset(form, **extra):
    return forms.inlineformset_factory(
        Proyecto, form._meta.model, form=form, extra=0, can_delete=True, **extra,
    )


ActividadFormSet = _formset(ActividadForm)
RubroFormSet = _formset(RubroForm)
RiesgoFormSet = _formset(RiesgoForm)
