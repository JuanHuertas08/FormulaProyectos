"""Genera el diagnóstico de contexto (Paso 2) buscando en fuentes oficiales
del país del proyecto y en organismos multilaterales de la región."""
import json
import logging
import time

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

# Instrucción común para cuando no hay datos: la sección vacía le permite a la
# pantalla avisar al usuario con un modal en lugar de mostrar un texto de relleno.
SIN_RESULTADOS = """No inventes datos. Si no encuentras información en las fuentes permitidas
para una sección, deja esa sección como cadena vacía "" (no escribas frases
como "no se encontró información"). En "observaciones" explica en una o dos
frases, para el usuario, qué buscaste y por qué no hubo resultados (o deja ""
si encontraste información para todo)."""

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

MODEL = 'claude-opus-5-5'
# Profundidad de razonamiento; en este modelo el valor por defecto es
# 'medium', se fija explícito para que no cambie entre versiones.
EFFORT = 'medium'
# El pensamiento del modelo consume del mismo límite que la respuesta: con
# 4096 la respuesta se cortaba antes de escribir el JSON.
MAX_TOKENS = 16000
# Si los filtros de seguridad del modelo declinan la solicitud, la API la
# reintenta en el modelo alternativo recomendado (server-side fallback).
BETAS = ['server-side-fallback-2026-07-01']

# Tiempo máximo total de la búsqueda (todas las continuaciones). Debe ser
# menor que el timeout de gunicorn (gunicorn.conf.py) para devolver un error
# controlado en vez de un 502.
TIMEOUT_SEGUNDOS = 240

# Con herramientas de servidor la API corre un ciclo interno de hasta 10
# iteraciones; si no termina devuelve stop_reason "pause_turn" y hay que
# reenviar el turno para que continúe.
MAX_CONTINUACIONES = 4

# Búsquedas web permitidas: el diagnóstico completo cubre tres temas; una
# sección sola puede profundizar más en uno.
MAX_BUSQUEDAS_COMPLETO = 10
MAX_BUSQUEDAS_SECCION = 6
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

{SIN_RESULTADOS}

Responde ÚNICAMENTE con un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:
{{"{seccion}": "...", "fuentes": ["url1", "url2"], "observaciones": "..."}}"""
    else:
        listado = '\n'.join(
            f'{i}. "{clave}": {texto}' for i, (clave, texto) in enumerate(SECCIONES.items(), 1)
        )
        tarea = f"""Redacta en español tres secciones, cada una como un párrafo
narrativo (no viñetas):

{listado}

{SIN_RESULTADOS}

Responde ÚNICAMENTE con un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:
{{"cifras": "...", "antecedentes": "...", "necesidades": "...", "fuentes": ["url1", "url2"], "observaciones": "..."}}"""

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


def _resultados_busqueda(contenido):
    """Recorre los bloques de resultado de la búsqueda web: devuelve las URLs
    obtenidas y los códigos de error (los errores de la herramienta no lanzan
    excepción, llegan como un objeto en lugar de una lista)."""
    urls, errores = [], []
    for block in contenido:
        if getattr(block, 'type', None) != 'web_search_tool_result':
            continue
        resultado = getattr(block, 'content', None)
        if isinstance(resultado, list):
            for item in resultado:
                url = getattr(item, 'url', None)
                if url and url not in urls:
                    urls.append(url)
        else:
            errores.append(getattr(resultado, 'error_code', 'desconocido'))
    return urls, errores


def _texto_final(contenido):
    """Texto escrito después de la última búsqueda (donde va el JSON). Si no
    hay texto ahí, todo el texto de la respuesta."""
    ultimo = -1
    for i, block in enumerate(contenido):
        if getattr(block, 'type', None) in ('server_tool_use', 'web_search_tool_result'):
            ultimo = i
    textos = [b.text for b in contenido[ultimo + 1:] if getattr(b, 'type', None) == 'text']
    if not ''.join(textos).strip():
        textos = [b.text for b in contenido if getattr(b, 'type', None) == 'text']
    return ''.join(textos).strip()


def _llamar_api(client, *, prompt, max_busquedas, dominios):
    """Hace la llamada con búsqueda web y la reanuda mientras la API responda
    "pause_turn", dentro del plazo total. Devuelve los bloques acumulados del
    turno y el último stop_reason."""
    import anthropic

    tools = [{
        'type': 'web_search_20260209',
        'name': 'web_search',
        'max_uses': max_busquedas,
        'allowed_domains': dominios,
    }]
    limite = time.monotonic() + TIMEOUT_SEGUNDOS
    contenido = []
    response = None
    for intento in range(MAX_CONTINUACIONES + 1):
        restante = limite - time.monotonic()
        if restante < 10:
            break
        messages = [{'role': 'user', 'content': prompt}]
        if contenido:
            # Reenviar el turno pausado tal cual; la API retoma donde quedó
            messages.append({'role': 'assistant', 'content': list(contenido)})
        try:
            response = client.with_options(timeout=restante).beta.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                output_config={'effort': EFFORT},
                betas=BETAS,
                fallbacks='default',
                tools=tools,
                messages=messages,
            )
        except anthropic.APITimeoutError as exc:
            logger.warning('Diagnóstico: se superó el plazo de %s s (intento %s)', TIMEOUT_SEGUNDOS, intento + 1)
            raise DiagnosticoError(
                'La búsqueda tardó demasiado. Intenta de nuevo, prueba buscando una sola '
                'sección o completa el diagnóstico manualmente.'
            ) from exc
        except anthropic.APIStatusError as exc:
            logger.error(
                'Diagnóstico: error %s de la API (request_id=%s): %s',
                exc.status_code, getattr(exc, 'request_id', None), exc.message,
            )
            raise DiagnosticoError('No se pudo contactar el servicio de búsqueda. Intenta de nuevo.') from exc
        except anthropic.APIConnectionError as exc:
            logger.exception('Diagnóstico: error de conexión con la API')
            raise DiagnosticoError('No se pudo contactar el servicio de búsqueda. Intenta de nuevo.') from exc

        contenido.extend(response.content)
        logger.info(
            'Diagnóstico: intento %s, stop_reason=%s, request_id=%s',
            intento + 1, response.stop_reason, response._request_id,
        )
        if response.stop_reason != 'pause_turn':
            break

    if response is None:
        raise DiagnosticoError('La búsqueda tardó demasiado. Intenta de nuevo.')
    return contenido, response.stop_reason


def generar_diagnostico(*, pais, categoria, nombre, descripcion, contexto=None, seccion=None):
    """Busca y redacta el diagnóstico. Con `seccion` ('cifras', 'antecedentes'
    o 'necesidades') genera solo esa sección; sin ella, las tres.
    `contexto` es un dict opcional con más datos del proyecto (fechas, ODS,
    leyes, articulaciones) para orientar la búsqueda.

    Devuelve las secciones pedidas (vacías si no hubo información), las
    fuentes, las observaciones de la IA y `secciones_vacias`."""
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

    client = anthropic.Anthropic(api_key=api_key, max_retries=0)

    ficha = _contexto_proyecto(
        nombre=nombre, categoria=categoria, pais=pais, descripcion=descripcion, contexto=contexto,
    )
    prompt = _construir_prompt(ficha=ficha, pais=pais, seccion=seccion)

    contenido, stop_reason = _llamar_api(
        client,
        prompt=prompt,
        max_busquedas=MAX_BUSQUEDAS_SECCION if seccion else MAX_BUSQUEDAS_COMPLETO,
        dominios=dominios,
    )
    urls, errores_busqueda = _resultados_busqueda(contenido)
    if errores_busqueda:
        logger.warning('Diagnóstico: errores de la herramienta de búsqueda: %s', errores_busqueda)

    if stop_reason == 'refusal':
        raise DiagnosticoError('El servicio de búsqueda no pudo procesar esta solicitud. Revisa la descripción e intenta de nuevo.')

    texto = _texto_final(contenido)
    try:
        data = _extraer_json(texto)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error('Respuesta no parseable del diagnóstico (stop_reason=%s): %r', stop_reason, texto[:2000])
        if stop_reason in ('pause_turn', 'max_tokens'):
            raise DiagnosticoError(
                'La búsqueda no alcanzó a terminar. Intenta buscando una sola sección.'
            ) from exc
        raise DiagnosticoError('La respuesta del servicio de búsqueda no tuvo el formato esperado.') from exc

    # Fuentes: las que cita la IA; si no citó ninguna, las primeras que
    # devolvió el buscador, para que el usuario pueda verificar.
    fuentes = [u for u in data.get('fuentes', []) if isinstance(u, str) and u]
    if not fuentes:
        fuentes = urls[:MAX_FUENTES_RESPALDO]

    secciones = [seccion] if seccion else list(SECCIONES)
    resultado = {clave: (data.get(clave) or '').strip() for clave in secciones}
    vacias = [clave for clave in secciones if not resultado[clave]]
    observaciones = (data.get('observaciones') or '').strip()
    if vacias and not observaciones and errores_busqueda:
        observaciones = 'El servicio de búsqueda no pudo consultar algunas de las fuentes oficiales en este momento.'

    resultado.update({
        'fuentes': fuentes if len(vacias) < len(secciones) else [],
        'observaciones': observaciones,
        'secciones_vacias': vacias,
    })
    return resultado
