"""Rutas de las pantallas HTML del catálogo y las cuentas."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('maquinaria/<int:pk>/', views.equipment_detail, name='equipment_detail'),
    path('arriendo/<int:pk>/', views.rent_equipment, name='rent_equipment'),
    path('solicitud/<int:pk>/recibida/', views.rental_success, name='rental_success'),
    path('mis-arriendos/', views.my_rentals, name='my_rentals'),
    path('gestion/inventario/', views.inventory_management, name='inventory_management'),
    path('cuenta/ingresar/', views.PortalLoginView.as_view(), name='login'),
    path('cuenta/crear/', views.register, name='register'),
    path('cuenta/salir/', views.logout_user, name='logout'),
]
