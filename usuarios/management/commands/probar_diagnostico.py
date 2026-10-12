"""Prueba la búsqueda del diagnóstico del Paso 2 desde la consola y muestra
qué consultas hizo la IA, qué encontró y qué respondió.

Uso (en la Shell de Render, donde ya está ANTHROPIC_API_KEY):

    python manage.py probar_diagnostico --pais HND \
        --descripcion "Centro de atención para adultos mayores en Choluteca"

    # Misma búsqueda sin limitar los sitios, para comparar:
    python manage.py probar_diagnostico --pais HND --descripcion "..." --sin-restriccion
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from usuarios import diagnostico


class Command(BaseCommand):
    help = 'Ejecuta una búsqueda de diagnóstico de prueba y muestra el detalle.'

    def add_arguments(self, parser):
        parser.add_argument('--pais', required=True, choices=sorted(diagnostico.FUENTES_POR_PAIS))
        parser.add_argument('--descripcion', required=True)
        parser.add_argument('--nombre', default='Proyecto de prueba')
        parser.add_argument('--categoria', default='Público')
        parser.add_argument('--seccion', choices=sorted(diagnostico.SECCIONES))
        parser.add_argument(
            '--sin-restriccion', action='store_true',
            help='Busca en toda la web en lugar de solo los sitios oficiales configurados.',
        )

    def handle(self, *args, **opciones):
        if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
            raise CommandError('ANTHROPIC_API_KEY no está configurada en este entorno.')

        import anthropic

        pais, seccion = opciones['pais'], opciones['seccion']
        dominios = None if opciones['sin_restriccion'] else diagnostico.FUENTES_POR_PAIS[pais]
        self.stdout.write(f'Modelo: {diagnostico.MODEL}  ·  esfuerzo: {diagnostico.EFFORT}')
        self.stdout.write(f'Sitios permitidos: {", ".join(dominios) if dominios else "toda la web"}')

        ficha = diagnostico._contexto_proyecto(
            nombre=opciones['nombre'], categoria=opciones['categoria'], pais=pais,
            descripcion=opciones['descripcion'], contexto=None,
        )
        prompt = diagnostico._construir_prompt(ficha=ficha, pais=pais, seccion=seccion)
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0)

        try:
            contenido, stop_reason = diagnostico._llamar_api(
                client, prompt=prompt, dominios=dominios,
                max_busquedas=diagnostico.MAX_BUSQUEDAS_SECCION if seccion else diagnostico.MAX_BUSQUEDAS_COMPLETO,
            )
        except diagnostico.DiagnosticoError as exc:
            raise CommandError(f'Falló la llamada: {exc} (ver detalle arriba en los logs)')

        self.stdout.write(f'\nstop_reason final: {stop_reason}')
        self.stdout.write('\nBúsquedas:')
        for linea in diagnostico.resumen_busquedas(contenido):
            self.stdout.write(f'  - {linea}')

        texto = diagnostico._texto_final(contenido)
        self.stdout.write('\nRespuesta de la IA (primeros 1500 caracteres):')
        self.stdout.write(texto[:1500] or '(vacía)')

        try:
            data = diagnostico._extraer_json(texto)
        except (json.JSONDecodeError, ValueError):
            self.stdout.write(self.style.ERROR('\nLa respuesta no contiene un JSON válido.'))
            return

        self.stdout.write('\nSecciones:')
        for clave in ([seccion] if seccion else diagnostico.SECCIONES):
            valor = (data.get(clave) or '').strip()
            estado = self.style.SUCCESS(f'{len(valor)} caracteres') if valor else self.style.WARNING('VACÍA')
            self.stdout.write(f'  - {clave}: {estado}')
        self.stdout.write(f'Observaciones: {data.get("observaciones") or "-"}')
        self.stdout.write(f'Fuentes citadas: {len(data.get("fuentes") or [])}')
