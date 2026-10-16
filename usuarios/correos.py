"""Correos que envía la aplicación (vía Brevo en producción; ver EMAIL_BACKEND
en config/settings.py)."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def enviar_bienvenida(request, usuario):
    """Envía el correo de bienvenida al crear la cuenta, en el idioma con el
    que el usuario se registró. Si el envío falla no interrumpe el registro:
    devuelve False y deja el error en los logs."""
    if not usuario.email:
        logger.warning('Correo de bienvenida no enviado: %s no tiene correo', usuario.username)
        return False

    idioma = getattr(request, 'LANGUAGE_CODE', None) or settings.LANGUAGE_CODE
    contexto = {
        'idioma': idioma,
        'nombre': usuario.first_name or usuario.username,
        'usuario': usuario.username,
        'url_login': request.build_absolute_uri(reverse('login')),
    }
    with translation.override(idioma):
        asunto = _('Bienvenido a InvestProject')
        texto = render_to_string('emails/bienvenida.txt', contexto)
        html = render_to_string('emails/bienvenida.html', contexto)

    correo = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [usuario.email])
    correo.attach_alternative(html, 'text/html')
    logger.info('Enviando correo de bienvenida a %s (%s)', usuario.username, settings.EMAIL_BACKEND)
    try:
        correo.send()
    except Exception:
        # Proveedor caído, remitente no verificado, clave inválida, etc.
        logger.exception('No se pudo enviar el correo de bienvenida a %s', usuario.username)
        return False
    logger.info('Correo de bienvenida enviado a %s', usuario.username)
    return True


def enmascarar_correo(email):
    """'ana.perez@gmail.com' -> 'a***@gmail.com' (para logs sin datos personales completos)."""
    usuario, _sep, dominio = (email or '').partition('@')
    return f'{usuario[:1]}***@{dominio}' if dominio else '***'
