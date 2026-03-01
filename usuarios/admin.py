from django.contrib import admin
from .models import Perfil

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    # Usamos nombres de funciones en lugar de campos directos
    list_display = ('usuario', 'get_nombre', 'get_apellido', 'telefono', 'pais')

    # Definimos qué debe mostrar la columna 'get_nombre'
    def get_nombre(self, obj):
        return obj.usuario.first_name
    get_nombre.short_description = 'Nombre' # Título de la columna

    # Definimos qué debe mostrar la columna 'get_apellido'
    def get_apellido(self, obj):
        return obj.usuario.last_name
    get_apellido.short_description = 'Apellido'