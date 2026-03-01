

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esto une el prefijo 'usuarios/' con lo que haya en usuarios.urls
    path('usuarios/', include('usuarios.urls')), 
]