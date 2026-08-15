

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esto une el prefijo 'usuarios/' con lo que haya en usuarios.urls
    path('usuarios/', include('usuarios.urls')),
    # Vista set_language para el selector de idioma
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)