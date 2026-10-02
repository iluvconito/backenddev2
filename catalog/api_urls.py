"""Rutas de la API REST bajo el prefijo /api/."""

from rest_framework.routers import DefaultRouter
from django.urls import path

from .api import (
    BranchViewSet,
    CheckoutAPIView,
    ContractStatusAPIView,
    EquipmentStockViewSet,
    EquipmentViewSet,
    MyContractsAPIView,
    RentalCartAPIView,
)

router = DefaultRouter()
router.register('maquinarias', EquipmentViewSet, basename='equipment')
router.register('sedes', BranchViewSet, basename='branch')
router.register('inventario', EquipmentStockViewSet, basename='stock')

urlpatterns = [
    path('carro-arriendo/', RentalCartAPIView.as_view(), name='rental-cart'),
    path('contratos/checkout/', CheckoutAPIView.as_view(), name='contract-checkout'),
    path('contratos/<int:pk>/estado/', ContractStatusAPIView.as_view(), name='contract-status'),
    path('mis-contratos/', MyContractsAPIView.as_view(), name='my-contracts'),
] + router.urls
