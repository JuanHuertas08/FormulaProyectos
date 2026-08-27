"""Genera el diagnóstico de contexto (Paso 2) buscando en fuentes oficiales
de planeación y estadística del país del proyecto."""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Fuentes oficiales por país soportado: el organismo de planeación, el
# instituto nacional de estadística, y CEPAL como respaldo regional cuando
# la fuente nacional no tiene indexado el dato buscado.
FUENTES_POR_PAIS = {
    'COL': ['dnp.gov.co', 'dane.gov.co', 'datos.gov.co', 'cepal.org'],
    'SLV': ['presidencia.gob.sv', 'digestyc.gob.sv', 'cepal.org'],
    'HND': ['spe.gob.hn', 'ine.gob.hn', 'cepal.org'],
}

MODEL = 'claude-opus-5'


class DiagnosticoError(Exception):
    """Error controlado al generar el diagnóstico (clave no configurada, IA no
    encontró información, error de red, respuesta inesperada, etc.)."""


def generar_diagnostico(*, pais, categoria, nombre, descripcion):
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        raise DiagnosticoError(
            'La búsqueda automática no está configurada (falta ANTHROPIC_API_KEY).'
        )

    dominios = FUENTES_POR_PAIS.get(pais)
    if not dominios:
        raise DiagnosticoError('No hay fuentes oficiales configuradas para ese país.')

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Eres un analista de planeación pública. Investiga en las fuentes
oficiales permitidas de {pais} (el organismo nacional de planeación, el
instituto nacional de estadística, el portal de datos abiertos si existe, y
CEPAL como respaldo regional) para construir el diagnóstico de contexto de
este proyecto. Consulta varias de esas fuentes, no te quedes con la primera
que encuentres, y prioriza cifras oficiales recientes:

- Nombre del proyecto: {nombre}
- Categoría: {categoria}
- País de ejecución: {pais}
- Descripción: {descripcion}

Busca y redacta tres secciones en español, cada una como un párrafo narrativo
(no viñetas), basándote en lo que encuentres en esas fuentes oficiales:

1. "cifras": Cifras y datos estadísticos relacionados con la naturaleza de este
   proyecto (población afectada, indicadores relevantes, series recientes, etc.)
2. "antecedentes": Antecedentes sociales, políticos, culturales, legales,
   ambientales y económicos de los últimos 5 años relacionados con la
   naturaleza de este proyecto.
3. "necesidades": Necesidades y desafíos del lugar/población relacionados con
   la naturaleza de este proyecto.

Si no encuentras información suficiente en las fuentes permitidas para alguna
sección, dilo explícitamente en el texto de esa sección en vez de inventar datos.

Responde ÚNICAMENTE con un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:
{{"cifras": "...", "antecedentes": "...", "necesidades": "...", "fuentes": ["url1", "url2"]}}
"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[{
                'type': 'web_search_20260209',
                'name': 'web_search',
                'max_uses': 10,
                'allowed_domains': dominios,
            }],
            messages=[{'role': 'user', 'content': prompt}],
        )
    except anthropic.APIError as exc:
        logger.exception('Error llamando a la API de Anthropic para el diagnóstico')
        raise DiagnosticoError('No se pudo contactar el servicio de búsqueda. Intenta de nuevo.') from exc

    texto = ''.join(
        block.text for block in response.content if getattr(block, 'type', None) == 'text'
    ).strip()

    if texto.startswith('```'):
        texto = texto.strip('`')
        if texto.startswith('json'):
            texto = texto[4:]
        texto = texto.strip()

    try:
        data = json.loads(texto)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error('Respuesta no parseable del diagnóstico: %r', texto)
        raise DiagnosticoError('La respuesta del servicio de búsqueda no tuvo el formato esperado.') from exc

    return {
        'cifras': data.get('cifras', ''),
        'antecedentes': data.get('antecedentes', ''),
        'necesidades': data.get('necesidades', ''),
        'fuentes': data.get('fuentes', []),
    }
