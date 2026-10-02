"""Configuración de pruebas que evita depender de credenciales PostgreSQL."""

from .settings import *


DATABASES = {
    # La base efímera mantiene la suite aislada del servicio PostgreSQL.
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
