from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Login y Registro
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('registrar/', views.registrar_usuario, name='register'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Rutas para recuperación de contraseña
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Vistas de la aplicación
    path('home/', views.home, name='home'),
    
    # RUTA ÚNICA PARA EL PROYECTO
    # He dejado solo 'crear_proyecto' que es la vista que unificamos
    # para manejar todos los pasos del wizard.
    path('crear-proyecto/', views.crear_proyecto, name='crear_proyecto'),
    path('api/leyes/', views.obtener_leyes_por_pais, name='obtener_leyes'),
    path('api/diagnostico/', views.buscar_diagnostico, name='buscar_diagnostico'),
]