set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
# Crea o restablece el superusuario si están las variables DJANGO_SUPERUSER_*
python manage.py asegurar_superusuario
