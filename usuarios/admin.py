from django.contrib import admin
from .models import Perfil, Proyecto, DocumentoSoporte, ActividadCronograma, RubroPresupuesto, RiesgoProyecto

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


class DocumentoSoporteInline(admin.TabularInline):
    model = DocumentoSoporte
    extra = 0


class ActividadCronogramaInline(admin.TabularInline):
    model = ActividadCronograma
    extra = 0


class RubroPresupuestoInline(admin.TabularInline):
    model = RubroPresupuesto
    extra = 0


class RiesgoProyectoInline(admin.TabularInline):
    model = RiesgoProyecto
    extra = 0


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'categoria', 'pais', 'fecha_inicio', 'fecha_fin', 'presupuesto', 'fecha_creacion')
    list_filter = ('pais', 'categoria')
    search_fields = ('nombre', 'descripcion')
    inlines = [ActividadCronogramaInline, RubroPresupuestoInline, RiesgoProyectoInline, DocumentoSoporteInline]
