"""Genera el diagnóstico de contexto (Paso 2) buscando en fuentes oficiales
del país del proyecto y en organismos multilaterales de la región."""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Fuentes nacionales por país: planeación, estadística, datos abiertos y
# ministerios sectoriales (salud, educación, vivienda, desarrollo social...).
# Los subdominios quedan incluidos (bcr.gob.sv cubre onec.bcr.gob.sv).
FUENTES_NACIONALES = {
    'COL': {
        'nombre': 'Colombia',
        'dominios': [
            'dnp.gov.co', 'dane.gov.co', 'datos.gov.co',
            'minsalud.gov.co', 'mineducacion.gov.co', 'minvivienda.gov.co',
            'minagricultura.gov.co', 'prosperidadsocial.gov.co',
        ],
        'descripcion': 'DNP (planeación), DANE (estadística), Datos Abiertos, '
                       'y los ministerios de Salud, Educación, Vivienda, Agricultura '
                       'y Prosperidad Social',
    },
    'HND': {
        'nombre': 'Honduras',
        'dominios': ['spe.gob.hn', 'ine.gob.hn', 'salud.gob.hn', 'se.gob.hn', 'sedesol.gob.hn'],
        'descripcion': 'SPE (planificación), INE (estadística), y las secretarías '
                       'de Salud, Educación y Desarrollo Social (SEDESOL)',
    },
    'SLV': {
        'nombre': 'El Salvador',
        'dominios': ['presidencia.gob.sv', 'bcr.gob.sv', 'salud.gob.sv', 'mined.gob.sv'],
        'descripcion': 'Presidencia, Banco Central de Reserva (incluye la ONEC, '
                       'antigua DIGESTYC, con la estadística oficial), y los '
                       'ministerios de Salud y Educación',
    },
}

# Respaldo regional común a todos los países: CEPAL, Banco Mundial, BID y PNUD.
FUENTES_REGIONALES = ['cepal.org', 'worldbank.org', 'iadb.org', 'undp.org']

FUENTES_POR_PAIS = {
    codigo: datos['dominios'] + FUENTES_REGIONALES
    for codigo, datos in FUENTES_NACIONALES.items()
}

# Secciones del diagnóstico y qué debe contener cada una
SECCIONES = {
    'cifras': 'Cifras y datos estadísticos relacionados con la naturaleza de este '
              'proyecto: población afectada u objetivo, indicadores relevantes y '
              'series recientes, idealmente desagregados para el territorio del proyecto.',
    'antecedentes': 'Antecedentes sociales, políticos, culturales, legales, ambientales '
                    'y económicos de los últimos 5 años relacionados con la naturaleza '
                    'de este proyecto.',
    'necesidades': 'Necesidades y desafíos del lugar y de la población relacionados '
                   'con la naturaleza de este proyecto.',
}

MODEL = 'claude-opus-5'

# Tiempo máximo de la llamada a la IA. Debe ser menor que el timeout de
# gunicorn (gunicorn.conf.py) para devolver un error controlado en vez de un 502.
TIMEOUT_SEGUNDOS = 180

# Búsquedas web permitidas: el diagnóstico completo cubre tres temas; una
# sección sola puede profundizar más en uno.
MAX_BUSQUEDAS_COMPLETO = 12
MAX_BUSQUEDAS_SECCION = 8
MAX_FUENTES_RESPALDO = 10


class DiagnosticoError(Exception):
    """Error controlado al generar el diagnóstico (clave no configurada, IA no
    encontró información, error de red, respuesta inesperada, etc.)."""


def _contexto_proyecto(*, nombre, categoria, pais, descripcion, contexto):
    """Arma la ficha del proyecto que recibe la IA, incluyendo solo los datos
    que el usuario haya diligenciado."""
    lineas = [
        f'- Nombre del proyecto: {nombre}',
        f'- Categoría: {categoria or "no indicada"}',
        f'- País de ejecución: {FUENTES_NACIONALES[pais]["nombre"]}',
        f'- Descripción: {descripcion}',
    ]
    etiquetas = {
        'fecha_inicio': 'Fecha de inicio',
        'fecha_fin': 'Fecha de finalización',
        'ods': 'Objetivos de Desarrollo Sostenible relacionados',
        'leyes': 'Marco legal seleccionado',
        'articulacion_nacional': 'Articulación con planes nacionales',
        'articulacion_regional': 'Articulación con planes departamentales/regionales',
        'articulacion_municipal': 'Articulación con planes municipales',
        'articulacion_institucional': 'Articulación institucional o social',
        'descripcion_detallada': 'Notas sobre el marco legal',
    }
    for clave, etiqueta in etiquetas.items():
        valor = (contexto or {}).get(clave)
        if isinstance(valor, (list, tuple)):
            valor = '; '.join(v for v in valor if v)
        if valor:
            lineas.append(f'- {etiqueta}: {valor}')
    return '\n'.join(lineas)


def _construir_prompt(*, ficha, pais, seccion):
    fuentes = FUENTES_NACIONALES[pais]['descripcion']
    instrucciones_busqueda = f"""Investiga primero en las fuentes oficiales de
{FUENTES_NACIONALES[pais]['nombre']} ({fuentes}) y usa CEPAL, Banco Mundial, BID y
PNUD como respaldo cuando la fuente nacional no tenga el dato. Consulta varias
fuentes, no te quedes con la primera. Prioriza cifras oficiales recientes y,
si la ficha menciona un departamento o municipio, busca primero datos de ese
territorio y luego los nacionales como referencia. Indica en el texto el año y
la fuente de cada cifra. Usa los ODS, el marco legal y las articulaciones de
la ficha para orientar la búsqueda hacia el sector correcto."""

    if seccion:
        tarea = f"""Redacta en español UNA sola sección del diagnóstico de contexto,
en uno o dos párrafos narrativos (no viñetas):

"{seccion}": {SECCIONES[seccion]}

Si no encuentras información suficiente en las fuentes permitidas, dilo
explícitamente en el texto en vez de inventar datos.

Responde ÚNICAMENTE con un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:
{{"{seccion}": "...", "fuentes": ["url1", "url2"]}}"""
    else:
        listado = '\n'.join(
            f'{i}. "{clave}": {texto}' for i, (clave, texto) in enumerate(SECCIONES.items(), 1)
        )
        tarea = f"""Redacta en español tres secciones, cada una como un párrafo
narrativo (no viñetas):

{listado}

Si no encuentras información suficiente en las fuentes permitidas para alguna
sección, dilo explícitamente en el texto de esa sección en vez de inventar datos.

Responde ÚNICAMENTE con un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:
{{"cifras": "...", "antecedentes": "...", "necesidades": "...", "fuentes": ["url1", "url2"]}}"""

    return f"""Eres un analista de planeación pública que prepara el diagnóstico de
contexto para la formulación de un proyecto. Esta es la ficha del proyecto:

{ficha}

{instrucciones_busqueda}

{tarea}
"""


def _extraer_json(texto):
    """Extrae el objeto JSON de la respuesta, aunque la IA haya escrito texto
    antes o después (por ejemplo, comentarios entre búsquedas)."""
    inicio, fin = texto.find('{'), texto.rfind('}')
    if inicio == -1 or fin <= inicio:
        raise ValueError('sin objeto JSON')
    return json.loads(texto[inicio:fin + 1])


def _urls_consultadas(response):
    """URLs de los resultados que devolvió la herramienta de búsqueda web."""
    urls = []
    for block in response.content:
        if getattr(block, 'type', None) != 'web_search_tool_result':
            continue
        contenido = getattr(block, 'content', None)
        if not isinstance(contenido, list):
            continue  # error de búsqueda
        for resultado in contenido:
            url = getattr(resultado, 'url', None)
            if url and url not in urls:
                urls.append(url)
    return urls


def generar_diagnostico(*, pais, categoria, nombre, descripcion, contexto=None, seccion=None):
    """Busca y redacta el diagnóstico. Con `seccion` ('cifras', 'antecedentes'
    o 'necesidades') genera solo esa sección; sin ella, las tres.
    `contexto` es un dict opcional con más datos del proyecto (fechas, ODS,
    leyes, articulaciones) para orientar la búsqueda."""
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        raise DiagnosticoError(
            'La búsqueda automática no está configurada (falta ANTHROPIC_API_KEY).'
        )

    dominios = FUENTES_POR_PAIS.get(pais)
    if not dominios:
        raise DiagnosticoError('No hay fuentes oficiales configuradas para ese país.')
    if seccion and seccion not in SECCIONES:
        raise DiagnosticoError('Sección del diagnóstico no válida.')

    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SEGUNDOS, max_retries=0)

    ficha = _contexto_proyecto(
        nombre=nombre, categoria=categoria, pais=pais, descripcion=descripcion, contexto=contexto,
    )
    prompt = _construir_prompt(ficha=ficha, pais=pais, seccion=seccion)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[{
                'type': 'web_search_20260209',
                'name': 'web_search',
                'max_uses': MAX_BUSQUEDAS_SECCION if seccion else MAX_BUSQUEDAS_COMPLETO,
                'allowed_domains': dominios,
            }],
            messages=[{'role': 'user', 'content': prompt}],
        )
    except anthropic.APITimeoutError as exc:
        logger.warning('La búsqueda del diagnóstico superó %s s', TIMEOUT_SEGUNDOS)
        raise DiagnosticoError(
            'La búsqueda tardó demasiado. Intenta de nuevo, prueba buscando una sola '
            'sección o completa el diagnóstico manualmente.'
        ) from exc
    except anthropic.APIError as exc:
        logger.exception('Error llamando a la API de Anthropic para el diagnóstico')
        raise DiagnosticoError('No se pudo contactar el servicio de búsqueda. Intenta de nuevo.') from exc

    texto = ''.join(
        block.text for block in response.content if getattr(block, 'type', None) == 'text'
    ).strip()

    try:
        data = _extraer_json(texto)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error('Respuesta no parseable del diagnóstico: %r', texto)
        raise DiagnosticoError('La respuesta del servicio de búsqueda no tuvo el formato esperado.') from exc

    # Fuentes: las que cita la IA; si no citó ninguna, las primeras que
    # devolvió el buscador, para que el usuario pueda verificar.
    fuentes = [u for u in data.get('fuentes', []) if isinstance(u, str) and u]
    if not fuentes:
        fuentes = _urls_consultadas(response)[:MAX_FUENTES_RESPALDO]

    secciones = [seccion] if seccion else list(SECCIONES)
    resultado = {clave: data.get(clave, '') for clave in secciones}
    resultado['fuentes'] = fuentes
    return resultado
