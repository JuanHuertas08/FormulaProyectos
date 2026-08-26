from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


def validar_descripcion_minima(valor):
    """La descripción debe tener contenido real: al menos 50 caracteres sin contar
    espacios en blanco al inicio/fin (evita 'satisfacer' el mínimo solo con relleno)."""
    if len(valor.strip()) < 50:
        raise ValidationError(
            _('La descripción debe tener al menos 50 caracteres.')
        )

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True, null=True)
    ciudad = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f'Perfil de {self.usuario.username}'
    
    # Esta función se ejecuta cada vez que se guarda un Usuario
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.get_or_create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    # Asegura que el perfil se guarde si el usuario se actualiza
    if hasattr(instance, 'perfil'):
        instance.perfil.save()



class Proyecto(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos', null=True, blank=True)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(validators=[validar_descripcion_minima])
    fecha_inicio = models.DateField()
    categoria = models.CharField(max_length=100)
    pais = models.CharField(max_length=10, blank=True)
    # Campos de texto para articulaciones
    articulacion_nacional = models.TextField(blank=True)
    articulacion_regional = models.TextField(blank=True)
    articulacion_municipal = models.TextField(blank=True)
    articulacion_institucional = models.TextField(blank=True)
    descripcion_detallada = models.TextField(null=True, blank=True)
    # Paso 1: Objetivos de Desarrollo Sostenible seleccionados (códigos separados por coma)
    objetivos_desarrollo = models.CharField(max_length=255, blank=True)
    # Paso 2: Normas legales seleccionadas (nombres separados por coma)
    leyes = models.TextField(blank=True)
    # Paso 3: Cronograma
    fecha_fin = models.DateField(null=True, blank=True)
    # Paso 4: Recursos
    presupuesto = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # Paso 5: Riesgos
    riesgos = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # Paso 2: Diagnóstico del contexto (autocompletado por IA + editable por el usuario)
    diagnostico_cifras = models.TextField(
        blank=True,
        verbose_name=_('Cifras y datos estadísticos'),
    )
    diagnostico_antecedentes = models.TextField(
        blank=True,
        verbose_name=_('Antecedentes (últimos 5 años)'),
    )
    diagnostico_necesidades = models.TextField(
        blank=True,
        verbose_name=_('Necesidades y desafíos'),
    )
    diagnostico_fuentes = models.TextField(
        blank=True,
        verbose_name=_('Fuentes consultadas'),
        help_text=_('URLs de las fuentes oficiales usadas para generar el diagnóstico.'),
    )

class DocumentoSoporte(models.Model):
    TIPO_CHOICES = [
        ('PLAN', _('Plan de desarrollo')),
        ('LINEAMIENTO', _('Lineamiento')),
        ('POLITICA', _('Política')),
        ('OTRO', _('Otro documento')),
    ]
    SECCION_CHOICES = [
        ('INT', _('Internacional')),
        ('NAC', _('Nacional')),
        ('REG', _('Regional')),
        ('MUN', _('Municipal')),
        ('INS', _('Institucional')),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to='soportes_estrategicos/')
    tipo_documento = models.CharField(max_length=20, choices=TIPO_CHOICES)
    seccion = models.CharField(max_length=5, choices=SECCION_CHOICES)