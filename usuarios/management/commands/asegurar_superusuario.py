"""Crea el superusuario, o le restablece la contraseña si ya existe, a partir
de variables de entorno. Se ejecuta en cada deploy (buid.sh) porque el plan
gratuito de Render no tiene Shell para correr `createsuperuser`.

Variables (si falta alguna, el comando no hace nada):
    DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD

Recomendación: después de entrar al admin la primera vez, borrar
DJANGO_SUPERUSER_PASSWORD de Render para no dejar la contraseña guardada.
"""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crea o actualiza el superusuario desde DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD.'

    def handle(self, *args, **opciones):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        if not (username and email and password):
            self.stdout.write('Superusuario: variables DJANGO_SUPERUSER_* no configuradas; se omite.')
            return

        User = get_user_model()
        usuario = User.objects.filter(username__iexact=username).first() or User(username=username)
        try:
            validate_password(password, usuario)
        except ValidationError as exc:
            # No se detiene el deploy: el sitio sigue funcionando sin el cambio
            self.stderr.write(self.style.ERROR(
                'Superusuario: la contraseña no cumple las reglas de seguridad; no se aplicó. '
                + ' '.join(exc.messages)
            ))
            return

        creado = usuario.pk is None
        usuario.email = email
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.is_active = True
        usuario.set_password(password)
        usuario.save()
        accion = 'creado' if creado else 'actualizado (contraseña restablecida)'
        self.stdout.write(self.style.SUCCESS(f'Superusuario "{usuario.username}" {accion}.'))
