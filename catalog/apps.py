"""Configuración de la aplicación Django de catálogo."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Registra la aplicación y su tipo de clave primaria predeterminado."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog'
