Documentación Proyecto Django ProjectApp
Proyecto: ProjectApp - Sistema de Usuarios Django

1.  Configuración del Entorno

  - Crear entorno virtual: python -m venv env
  - Activar: .\env\Scripts\activate (Windows)
  - Dependencias: pip install django

2.  Estructura de Datos (Modelos)

  - Se utiliza el modelo User de Django para autenticación.
  - Se creó un modelo Perfil en usuarios/models.py para datos extra (Teléfono, País, Ciudad, Fecha de Nacimiento).
  - Relación: OneToOneField con on_delete=models.CASCADE.

3.  Automatización (Signals)

  - Se configuró una Signal post_save para que cada vez que se cree un User, se genere automáticamente su Perfil.

4.  URLs y Vistas

  - Prefijo del proyecto: usuarios/.
  - Rutas: login/, logout/, registrar/, home/.
  - El Login redirige a home/ mediante LOGIN_REDIRECT_URL en settings.py.

5.  Errores Frecuentes Solucionados

  - NoReverseMatch: Falta el nombre en el path o el namespace.
  - OperationalError (no such table): Falta ejecutar makemigrations y migrate.
  - IndentationError: Revisar los espacios en archivos .py.
  - 404: Verificar si la URL lleva el prefijo /usuarios/.