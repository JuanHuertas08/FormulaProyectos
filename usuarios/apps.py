import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class UsuariosConfig(AppConfig):
    name = 'usuarios'

    def ready(self):
        # Deja en los logs de cada arranque qué configuración de correo está
        # activa (p. ej. para confirmar en Render que BREVO_API_KEY se leyó).
        from django.conf import settings

        logger.info(
            'Correo: backend=%s, remitente=%s, clave Brevo configurada=%s',
            settings.EMAIL_BACKEND, settings.DEFAULT_FROM_EMAIL, bool(getattr(settings, 'BREVO_API_KEY', '')),
        )
