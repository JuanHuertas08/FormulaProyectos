from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    descripcion = models.TextField()
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

class DocumentoSoporte(models.Model):
    TIPO_CHOICES = [
        ('PLAN', 'Plan de desarrollo'),
        ('LINEAMIENTO', 'Lineamiento'),
        ('POLITICA', 'Política'),
        ('OTRO', 'Otro documento'),
    ]
    SECCION_CHOICES = [
        ('INT', 'Internacional'),
        ('NAC', 'Nacional'),
        ('REG', 'Regional'),
        ('MUN', 'Municipal'),
        ('INS', 'Institucional'),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to='soportes_estrategicos/')
    tipo_documento = models.CharField(max_length=20, choices=TIPO_CHOICES)
    seccion = models.CharField(max_length=5, choices=SECCION_CHOICES)