from django.db import models
from django.contrib.auth.models import User

class Proyecto(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    # Paso 1: Información Básica
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    # Paso 2: Fechas y Presupuesto
    fecha_inicio = models.DateField(null=True, blank=True)
    presupuesto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # ... Añade aquí el resto de campos para los 6 pasos
    paso_actual = models.IntegerField(default=1) # Para saber dónde quedó el usuario