"""Personalización de claims incluidos en los tokens de acceso y renovación."""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .permissions import CONSTRUCTION_COMPANY_ROLE, EXECUTIVE_ROLE


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Emite un claim de rol para aplicar permisos en endpoints API."""

    @classmethod
    def get_token(cls, user):
        """Asigna ejecutivo al personal staff y cliente al resto de usuarios."""
        token = super().get_token(user)
        token['role'] = EXECUTIVE_ROLE if user.is_staff else CONSTRUCTION_COMPANY_ROLE
        return token
