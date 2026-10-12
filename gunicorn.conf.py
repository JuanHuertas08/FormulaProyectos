# Configuración de gunicorn (se carga automáticamente desde el directorio de
# trabajo al ejecutar `gunicorn config.wsgi:application` en Render).

# La búsqueda del diagnóstico del Paso 2 (IA + búsqueda web) puede tardar
# varios minutos; con el timeout por defecto (30 s) el worker se reiniciaba y
# el navegador recibía un 502. Debe ser mayor que TIMEOUT_SEGUNDOS de
# usuarios/diagnostico.py.
timeout = 200

# Hilos para que una búsqueda larga no bloquee al resto de usuarios
# (en el plan free solo hay un proceso).
worker_class = 'gthread'
workers = 1
threads = 4
