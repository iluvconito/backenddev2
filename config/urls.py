"""
Rutas raíz del sitio web, administración, autenticación y documentación API.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from catalog.jwt_serializers import RoleTokenObtainPairSerializer


@extend_schema(auth=[], tags=['Autenticación'])
class RoleTokenObtainPairView(TokenObtainPairView):
    """Entrega JWT con el rol del usuario agregado en el payload."""

    serializer_class = RoleTokenObtainPairSerializer


@extend_schema(auth=[], tags=['Autenticación'])
class PublicTokenRefreshView(TokenRefreshView):
    """Renueva un access token usando un refresh token válido."""


urlpatterns = [
    # Publica admin, endpoints de OpenAPI/JWT y rutas de sitio/API.
    path('admin/', admin.site.urls),
    path(
        'api/schema/',
        SpectacularAPIView.as_view(permission_classes=[]),
        name='schema',
    ),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[]),
        name='swagger-ui',
    ),
    path('api/token/', RoleTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', PublicTokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include(('catalog.api_urls', 'api'), namespace='api')),
    path('', include('catalog.urls')),
]
