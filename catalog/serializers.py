"""Representaciones API y validaciones de precios, fechas e inventario."""

from rest_framework import serializers
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import (
    Branch,
    Equipment,
    EquipmentStock,
    Rental,
    RentalCart,
    RentalCartItem,
)


class BranchSerializer(serializers.ModelSerializer):
    """Representa datos públicos de ubicación y contacto de una sede."""

    class Meta:
        model = Branch
        fields = ('id', 'name', 'region', 'address', 'phone')


class EquipmentStockSerializer(serializers.ModelSerializer):
    """Expone el stock por sede y descuenta reservas pendientes del rango."""

    branch = BranchSerializer(read_only=True)
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentStock
        fields = ('id', 'branch', 'quantity', 'available_quantity')

    def get_available_quantity(self, stock: EquipmentStock) -> int:
        """Calcula unidades disponibles para las fechas solicitadas en la API."""
        request = self.context.get('request')
        if request is None:
            return stock.quantity
        start_date = parse_date(request.query_params.get('start_date', ''))
        end_date = parse_date(request.query_params.get('end_date', ''))
        if not start_date or not end_date or end_date < start_date:
            return stock.quantity
        pending = Rental.objects.filter(
            equipment=stock.equipment,
            branch=stock.branch,
            status=Rental.Status.PENDING,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return max(stock.quantity - pending, 0)


class EquipmentSerializer(serializers.ModelSerializer):
    """Entrega datos públicos de equipo y su inventario por sede."""

    category_display = serializers.CharField(source='get_category_display', read_only=True)
    inventory = EquipmentStockSerializer(source='stock_by_branch', many=True, read_only=True)
    physical_units = serializers.IntegerField(read_only=True)
    available_units = serializers.IntegerField(read_only=True)

    class Meta:
        model = Equipment
        fields = (
            'id',
            'name',
            'brand',
            'category',
            'category_display',
            'image_url',
            'description',
            'daily_rate',
            'fixed_deposit',
            'available',
            'physical_units',
            'available_units',
            'inventory',
        )


class ManagedEquipmentSerializer(serializers.ModelSerializer):
    """Serializer de escritura para mantenimiento de maquinaria ejecutiva."""

    class Meta:
        model = Equipment
        fields = (
            'id',
            'name',
            'brand',
            'category',
            'image_url',
            'description',
            'daily_rate',
            'fixed_deposit',
            'available',
            'physical_units',
        )
        read_only_fields = ('id',)


class RentalCartItemSerializer(serializers.ModelSerializer):
    """Valida líneas del carro y calcula precio estimado al valor vigente."""

    equipment = EquipmentSerializer(read_only=True)
    equipment_id = serializers.PrimaryKeyRelatedField(
        source='equipment',
        queryset=Equipment.objects.filter(available=True),
        write_only=True,
        required=True,
    )
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        source='branch',
        queryset=Branch.objects.all(),
        write_only=True,
        required=True,
    )

    class Meta:
        model = RentalCartItem
        fields = (
            'id',
            'equipment',
            'equipment_id',
            'branch',
            'branch_id',
            'start_date',
            'end_date',
            'quantity',
            'estimated_total',
        )
        read_only_fields = ('id',)

    estimated_total = serializers.SerializerMethodField()

    def get_estimated_total(self, item: RentalCartItem) -> int:
        """Multiplica días por tarifa y agrega garantía para cada unidad."""
        days = (item.end_date - item.start_date).days + 1
        return item.quantity * (
            days * item.equipment.daily_rate + item.equipment.fixed_deposit
        )

    def validate(self, attrs):
        """Valida fechas futuras y stock físico de la sede seleccionada."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        equipment = attrs.get('equipment') or (self.instance.equipment if self.instance else None)
        branch = attrs.get('branch') or (self.instance.branch if self.instance else None)
        start_date = start_date or (self.instance.start_date if self.instance else None)
        end_date = end_date or (self.instance.end_date if self.instance else None)
        quantity = attrs.get('quantity', self.instance.quantity if self.instance else 1)

        if start_date and start_date < timezone.localdate():
            raise serializers.ValidationError({'start_date': 'La fecha debe ser hoy o posterior.'})
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'La fecha de término debe ser igual o posterior al inicio.'})

        if equipment and branch and start_date and end_date and quantity:
            stock = equipment.stock_by_branch.filter(branch=branch).first()
            if stock is None or quantity > stock.quantity:
                raise serializers.ValidationError({
                    'quantity': 'La cantidad supera el inventario físico registrado en esta sede.'
                })
        return attrs

    def create(self, validated_data):
        """Guarda la línea en el carro persistente del usuario autenticado."""
        cart, _ = RentalCart.objects.get_or_create(user=self.context['request'].user)
        return RentalCartItem.objects.create(
            cart=cart,
            **validated_data,
        )

    def update(self, instance, validated_data):
        """Actualiza solo los campos validados de la línea del carro."""
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class RentalCartSerializer(serializers.ModelSerializer):
    """Serializa carro y suma de estimaciones de todas sus líneas."""

    items = RentalCartItemSerializer(many=True, read_only=True)
    estimated_total = serializers.SerializerMethodField()

    class Meta:
        model = RentalCart
        fields = ('id', 'items', 'estimated_total', 'created_at', 'updated_at')

    def get_estimated_total(self, cart: RentalCart) -> int:
        """Suma el estimado vigente de cada equipo solicitado."""
        return sum(
            item.quantity
            * (
                ((item.end_date - item.start_date).days + 1) * item.equipment.daily_rate
                + item.equipment.fixed_deposit
            )
            for item in cart.items.all()
        )


class CheckoutSerializer(serializers.Serializer):
    """Valida que el carro no esté vacío y que el stock siga disponible."""

    customer_name = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs):
        """Carga las líneas y rechaza checkout con inventario insuficiente."""
        user = self.context['request'].user
        cart_items = list(
            RentalCartItem.objects.filter(cart__user=user).select_related('equipment', 'branch')
        )
        if not cart_items:
            raise serializers.ValidationError({'cart': 'El carrito está vacío.'})

        for item in cart_items:
            stock = item.equipment.stock_by_branch.filter(branch=item.branch).first()
            if stock is None or item.quantity > stock.quantity:
                raise serializers.ValidationError({
                    'cart': f'No hay inventario físico suficiente para {item.equipment.name} en {item.branch.name}.'
                })
        attrs['cart_items'] = cart_items
        return attrs


class RentalSerializer(serializers.ModelSerializer):
    """Expone contrato, estado legible y totales basados en precios congelados."""

    equipment = serializers.StringRelatedField()
    branch = BranchSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    rental_days = serializers.IntegerField(read_only=True)
    daily_rental_cost = serializers.IntegerField(read_only=True)
    total_price = serializers.IntegerField(read_only=True)

    class Meta:
        model = Rental
        fields = (
            'id',
            'equipment',
            'branch',
            'customer_name',
            'start_date',
            'end_date',
            'quantity',
            'daily_rate',
            'fixed_deposit',
            'status',
            'status_display',
            'rental_days',
            'total_price',
            'daily_rental_cost',
            'created_at',
        )


class RentalStatusSerializer(serializers.ModelSerializer):
    """Valida la forma del cambio de estado solicitado por el ejecutivo."""

    class Meta:
        model = Rental
        fields = ('id', 'status')
