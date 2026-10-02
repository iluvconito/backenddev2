"""Permisos API basados en los roles incluidos en el JWT autenticado."""

from rest_framework.permissions import BasePermission, IsAuthenticated


EXECUTIVE_ROLE = 'Ejecutivo de Arriendos'
CONSTRUCTION_COMPANY_ROLE = 'Empresa Constructora'


class IsExecutiveRole(IsAuthenticated):
    """Autoriza operaciones reservadas al personal de arriendos."""

    message = 'Solo el rol Ejecutivo de Arriendos puede consultar el inventario.'

    def has_permission(self, request, view):
        """Exige sesión JWT válida y claim de ejecutivo."""
        return (
            super().has_permission(request, view)
            and request.auth.get('role') == EXECUTIVE_ROLE
        )


class IsConstructionCompany(IsAuthenticated):
    """Autoriza operaciones privadas de la empresa cliente."""

    message = 'Este endpoint está disponible para el rol Empresa Constructora.'

    def has_permission(self, request, view):
        """Exige sesión JWT válida y claim de empresa constructora."""
        return (
            super().has_permission(request, view)
            and request.auth.get('role') == CONSTRUCTION_COMPANY_ROLE
        )
