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
    ESTADO_EN_PROCESO = 'EN_PROCESO'
    ESTADO_COMPLETO = 'COMPLETO'
    ESTADO_CHOICES = [
        (ESTADO_EN_PROCESO, _('En Proceso')),
        (ESTADO_COMPLETO, _('Completo')),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos', null=True, blank=True)
    nombre = models.CharField(max_length=255)
    # Descripción, fecha de inicio y categoría pueden quedar vacías (o la
    # descripción corta) mientras el proyecto está En Proceso; el formulario
    # las exige, con validar_descripcion_minima, al finalizarlo.
    descripcion = models.TextField(blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
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
    riesgos = models.TextField(blank=True)  # observaciones generales; la matriz vive en RiesgoProyecto
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_EN_PROCESO)
    # Último paso del wizard en el que se guardó (para retomar desde ahí)
    paso_actual = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['-fecha_actualizacion']

    def __str__(self):
        return self.nombre

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

class ActividadCronograma(models.Model):
    """Paso 3: actividad o hito del cronograma del proyecto."""
    TIPO_CHOICES = [
        ('ACTIVIDAD', _('Actividad')),
        ('HITO', _('Hito')),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='actividades')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='ACTIVIDAD')
    nombre = models.CharField(_('Actividad'), max_length=255)
    responsable = models.CharField(_('Responsable'), max_length=150, blank=True)
    fecha_inicio = models.DateField(_('Inicio'))
    fecha_fin = models.DateField(_('Fin'))
    entregable = models.CharField(_('Entregable'), max_length=255, blank=True)

    class Meta:
        ordering = ['fecha_inicio', 'id']

    def __str__(self):
        return self.nombre


class RubroPresupuesto(models.Model):
    """Paso 4: línea del presupuesto, por rubro y fuente de financiamiento."""
    RUBRO_CHOICES = [
        ('TALENTO', _('Talento humano')),
        ('EQUIPOS', _('Equipos y tecnología')),
        ('MATERIALES', _('Materiales e insumos')),
        ('SERVICIOS', _('Servicios y consultorías')),
        ('INFRA', _('Infraestructura y obras')),
        ('LOGISTICA', _('Viajes y logística')),
        ('ADMIN', _('Gastos administrativos')),
        ('OTRO', _('Otros')),
    ]
    FUENTE_CHOICES = [
        ('PROPIOS', _('Recursos propios')),
        ('PUBLICO', _('Presupuesto público')),
        ('COOPERACION', _('Cooperación internacional')),
        ('PRIVADO', _('Aporte privado')),
        ('CREDITO', _('Crédito / financiamiento')),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='rubros')
    rubro = models.CharField(_('Rubro'), max_length=20, choices=RUBRO_CHOICES)
    descripcion = models.CharField(_('Descripción'), max_length=255, blank=True)
    fuente = models.CharField(_('Fuente'), max_length=20, choices=FUENTE_CHOICES)
    monto = models.DecimalField(_('Monto (USD)'), max_digits=14, decimal_places=2)

    def __str__(self):
        return f'{self.get_rubro_display()} - {self.monto}'


class RiesgoProyecto(models.Model):
    """Paso 5: riesgo identificado, con su valoración probabilidad x impacto."""
    TIPO_CHOICES = [
        ('FINANCIERO', _('Financiero')),
        ('TECNICO', _('Técnico / operativo')),
        ('LEGAL', _('Legal / regulatorio')),
        ('SOCIAL', _('Social')),
        ('AMBIENTAL', _('Ambiental')),
        ('POLITICO', _('Político / institucional')),
    ]
    ESCALA_CHOICES = [
        (1, _('Baja')),
        (2, _('Media')),
        (3, _('Alta')),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='matriz_riesgos')
    descripcion = models.CharField(_('Riesgo'), max_length=255)
    tipo = models.CharField(_('Tipo'), max_length=20, choices=TIPO_CHOICES)
    probabilidad = models.PositiveSmallIntegerField(_('Probabilidad'), choices=ESCALA_CHOICES, default=2)
    impacto = models.PositiveSmallIntegerField(_('Impacto'), choices=ESCALA_CHOICES, default=2)
    mitigacion = models.TextField(_('Medida de mitigación'), blank=True)
    responsable = models.CharField(_('Responsable'), max_length=150, blank=True)

    @property
    def nivel(self):
        return self.probabilidad * self.impacto

    @property
    def nivel_label(self):
        if self.nivel >= 6:
            return _('Alto')
        if self.nivel >= 3:
            return _('Medio')
        return _('Bajo')

    def __str__(self):
        return self.descripcion
