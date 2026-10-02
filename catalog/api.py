"""Endpoints REST para maquinaria, inventario, carros y contratos."""

import django_filters
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import Branch, Equipment, EquipmentStock, Rental, RentalCart, RentalCartItem
from .permissions import IsConstructionCompany, IsExecutiveRole
from .serializers import (
    BranchSerializer,
    CheckoutSerializer,
    EquipmentSerializer,
    EquipmentStockSerializer,
    ManagedEquipmentSerializer,
    RentalCartItemSerializer,
    RentalCartSerializer,
    RentalSerializer,
    RentalStatusSerializer,
)
from .services import transition_rental_status


class ContractConflict(APIException):
    """Error HTTP 409 para operaciones que chocan con contratos existentes."""

    status_code = status.HTTP_409_CONFLICT
    default_code = 'contract_conflict'


class EquipmentFilter(django_filters.FilterSet):
    """Filtros de categoría, marca, disponibilidad y tarifa diaria."""

    min_daily_rate = django_filters.NumberFilter(field_name='daily_rate', lookup_expr='gte')
    max_daily_rate = django_filters.NumberFilter(field_name='daily_rate', lookup_expr='lte')

    class Meta:
        model = Equipment
        fields = ('category', 'brand', 'available', 'min_daily_rate', 'max_daily_rate')


class EquipmentViewSet(viewsets.ModelViewSet):
    """Expone catálogo público y operaciones de maquinaria para ejecutivos."""

    queryset = Equipment.objects.prefetch_related('stock_by_branch__branch').order_by('name')
    http_method_names = ('get', 'post', 'put', 'delete', 'head', 'options')
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = EquipmentFilter
    search_fields = ('name', 'brand', 'description')
    ordering_fields = ('name', 'daily_rate')
    ordering = ('name',)

    def get_serializer_class(self):
        """Usa serializer de escritura en POST/PUT y lectura en consultas."""
        if self.request.method in ('POST', 'PUT'):
            return ManagedEquipmentSerializer
        return EquipmentSerializer

    def get_permissions(self):
        """Permite lecturas públicas y exige rol ejecutivo para mutaciones."""
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [AllowAny()]
        return [IsExecutiveRole()]

    def perform_destroy(self, instance):
        """Impide borrar equipos referenciados por contratos históricos."""
        if Rental.objects.filter(equipment=instance).exists():
            raise ContractConflict('No se puede eliminar maquinaria asociada a contratos existentes.')
        instance.delete()


class BranchViewSet(viewsets.ReadOnlyModelViewSet):
    """Publica sedes con filtros de región, búsqueda y orden."""

    queryset = Branch.objects.order_by('name')
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ('region',)
    search_fields = ('name', 'region', 'address')
    ordering_fields = ('name', 'region')
    ordering = ('name',)
    permission_classes = (AllowAny,)


class EquipmentStockViewSet(viewsets.ReadOnlyModelViewSet):
    """Permite al ejecutivo consultar el inventario y disponibilidad por rango."""

    queryset = EquipmentStock.objects.select_related('equipment', 'branch').order_by(
        'equipment__name',
        'branch__name',
    )
    serializer_class = EquipmentStockSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ('equipment', 'branch')
    ordering_fields = ('quantity',)
    ordering = ('equipment__name', 'branch__name')
    permission_classes = (IsExecutiveRole,)


@extend_schema(
    methods=['GET'],
    responses=RentalCartSerializer,
    tags=['Carro de arriendo'],
)
@extend_schema(
    methods=['POST'],
    request=RentalCartItemSerializer,
    responses={201: RentalCartItemSerializer},
    tags=['Carro de arriendo'],
)
class RentalCartAPIView(APIView):
    """Gestiona el carro persistente propio de una empresa constructora."""

    permission_classes = (IsConstructionCompany,)

    def get(self, request):
        """Devuelve el carro del usuario y sus líneas enriquecidas."""
        cart, _ = RentalCart.objects.get_or_create(user=request.user)
        cart = RentalCart.objects.prefetch_related(
            'items__equipment__stock_by_branch__branch',
            'items__branch',
        ).get(pk=cart.pk)
        return Response(RentalCartSerializer(cart).data)

    def post(self, request):
        """Valida y agrega una línea sin descontar inventario físico."""
        serializer = RentalCartItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            cart, _ = RentalCart.objects.get_or_create(user=request.user)
            RentalCart.objects.select_for_update().get(pk=cart.pk)
            item = serializer.save()
        return Response(
            RentalCartItemSerializer(item, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={204: None},
        description='Envía item_id para eliminar una línea. Sin item_id, vacía el carrito propio.',
        tags=['Carro de arriendo'],
    )
    def delete(self, request):
        """Elimina una línea indicada o vacía el carro propio."""
        item_id = request.query_params.get('item_id') or request.data.get('item_id')
        items = RentalCartItem.objects.filter(cart__user=request.user)
        if item_id:
            item = get_object_or_404(items, pk=item_id)
            item.delete()
        else:
            items.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=CheckoutSerializer,
    responses={201: RentalSerializer(many=True)},
    tags=['Contratos'],
)
class CheckoutAPIView(APIView):
    """Convierte líneas del carro en contratos pendientes de forma atómica."""

    permission_classes = (IsConstructionCompany,)

    def post(self, request):
        """Bloquea carro e inventario, valida disponibilidad y genera contratos."""
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            cart = RentalCart.objects.get_or_create(user=request.user)[0]
            RentalCart.objects.select_for_update().get(pk=cart.pk)
            cart_items = list(
                RentalCartItem.objects.select_for_update()
                .filter(cart__user=request.user)
                .select_related('equipment', 'branch')
            )
            stock_rows = Q(pk__in=[])
            for item in cart_items:
                stock_rows |= Q(equipment_id=item.equipment_id, branch_id=item.branch_id)
            list(
                EquipmentStock.objects.select_for_update().filter(stock_rows)
            )

            serializer = CheckoutSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            validated = serializer.validated_data
            customer_name = (
                validated.get('customer_name')
                or request.user.get_full_name()
                or request.user.get_username()
            )
            contracts = [
                Rental(
                    user=request.user,
                    equipment=item.equipment,
                    branch=item.branch,
                    customer_name=customer_name,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    quantity=item.quantity,
                    daily_rate=item.equipment.daily_rate,
                    fixed_deposit=item.equipment.fixed_deposit,
                    status=Rental.Status.PENDING,
                )
                for item in validated['cart_items']
            ]
            Rental.objects.bulk_create(contracts)
            RentalCartItem.objects.filter(cart__user=request.user).delete()

        return Response(
            RentalSerializer(contracts, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class MyContractsAPIView(ListAPIView):
    """Lista únicamente los contratos de la empresa autenticada."""

    queryset = Rental.objects.none()
    serializer_class = RentalSerializer
    permission_classes = (IsConstructionCompany,)

    def get_queryset(self):
        """Limita el resultado al usuario autenticado para evitar filtraciones."""
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return Rental.objects.filter(user=self.request.user).select_related(
            'equipment',
            'branch',
        )


class ContractStatusAPIView(APIView):
    """Actualiza el estado del contrato y delega la lógica de stock al servicio."""

    permission_classes = (IsExecutiveRole,)

    @extend_schema(
        request=RentalStatusSerializer,
        responses=RentalSerializer,
        tags=['Contratos'],
    )
    def patch(self, request, pk):
        """Valida el estado solicitado y traduce errores de negocio a HTTP 400."""
        contract = get_object_or_404(Rental.objects.select_related('equipment', 'branch'), pk=pk)
        serializer = RentalStatusSerializer(contract, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            contract = transition_rental_status(contract.pk, serializer.validated_data['status'])
        except DjangoValidationError as error:
            raise ValidationError({'status': error.messages}) from error
        return Response(RentalSerializer(contract).data)
