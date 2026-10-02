from django.conf import settings
from django.db import models


class Branch(models.Model):
	name = models.CharField(max_length=80, unique=True)
	region = models.CharField(max_length=100)
	address = models.CharField(max_length=160)
	phone = models.CharField(max_length=30)

	class Meta:
		ordering = ['region']
		verbose_name_plural = 'branches'

	def __str__(self):
		return f'{self.name} · {self.region}'


class Equipment(models.Model):
	class Category(models.TextChoices):
		MOVIMIENTO_TIERRA = 'movimiento-tierra', 'Movimiento de tierra'
		ELEVACION = 'elevacion', 'Elevación'
		TRANSPORTE = 'transporte', 'Transporte'
		SERVICIOS = 'servicios', 'Servicios'

	name = models.CharField(max_length=120)
	brand = models.CharField(max_length=60)
	category = models.CharField(max_length=30, choices=Category.choices)
	image_url = models.URLField()
	description = models.TextField()
	daily_rate = models.PositiveIntegerField()
	fixed_deposit = models.PositiveIntegerField(default=0, verbose_name='Garantía fija')
	available = models.BooleanField(default=True)

	class Meta:
		ordering = ['category', 'name']
		verbose_name_plural = 'equipment'

	def __str__(self):
		return self.name

	@property
	def physical_units(self) -> int:
		on_hand = self.stock_by_branch.aggregate(total=models.Sum('quantity'))['total'] or 0
		rented = self.rentals.filter(
			status__in=(Rental.Status.PAID, Rental.Status.DELIVERED),
		).aggregate(total=models.Sum('quantity'))['total'] or 0
		return on_hand + rented

	@property
	def available_units(self) -> int:
		return self.stock_by_branch.aggregate(total=models.Sum('quantity'))['total'] or 0


class EquipmentStock(models.Model):
	equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='stock_by_branch')
	branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='equipment_stock')
	quantity = models.PositiveIntegerField(default=0, verbose_name='Cantidad de unidades')

	class Meta:
		ordering = ['branch__name', 'equipment__name']
		constraints = [
			models.UniqueConstraint(fields=['equipment', 'branch'], name='unique_equipment_stock_per_branch'),
		]
		verbose_name = 'inventario de maquinaria'
		verbose_name_plural = 'inventario de maquinaria'

	def __str__(self):
		return f'{self.equipment} · {self.branch}: {self.quantity}'


class RentalCart(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rental_cart')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f'Carro de {self.user}'


class RentalCartItem(models.Model):
	cart = models.ForeignKey(RentalCart, on_delete=models.CASCADE, related_name='items')
	equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='cart_items')
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='cart_items')
	start_date = models.DateField()
	end_date = models.DateField()
	quantity = models.PositiveIntegerField(default=1)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']
		constraints = [
			models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='cart_end_on_or_after_start'),
			models.CheckConstraint(condition=models.Q(quantity__gte=1), name='cart_quantity_at_least_one'),
		]

	def __str__(self):
		return f'{self.quantity} × {self.equipment} · {self.branch}'


class Rental(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pendiente'
		PAID = 'paid', 'Pagado'
		DELIVERED = 'delivered', 'Entregado'
		COMPLETED = 'completed', 'Completado'
		CANCELLED = 'cancelled', 'Cancelado'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
	equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='rentals')
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='rentals')
	customer_name = models.CharField(max_length=120)
	start_date = models.DateField()
	end_date = models.DateField()
	quantity = models.PositiveIntegerField(default=1)
	daily_rate = models.PositiveIntegerField(default=0, verbose_name='Tarifa diaria acordada')
	fixed_deposit = models.PositiveIntegerField(default=0, verbose_name='Garantía fija acordada')
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='rental_end_on_or_after_start'),
			models.CheckConstraint(condition=models.Q(quantity__gte=1), name='rental_quantity_at_least_one'),
		]

	def __str__(self):
		"""Resume el equipo y las fechas del contrato."""
		return f'{self.equipment} · {self.start_date}–{self.end_date}'

	def save(self, *args, **kwargs):
		"""Inicializa snapshots de precio al crear contratos sin valores explícitos."""
		if self._state.adding and self.equipment_id:
			equipment = self.equipment
			if self.daily_rate == 0:
				self.daily_rate = equipment.daily_rate
			if self.fixed_deposit == 0:
				self.fixed_deposit = equipment.fixed_deposit
		super().save(*args, **kwargs)

	@property
	def rental_days(self):
		"""Cuenta ambos extremos del rango de arriendo como días facturables."""
		return (self.end_date - self.start_date).days + 1

	@property
	def daily_rental_cost(self):
		"""Calcula tarifa diaria por días y cantidad contratada."""
		return self.rental_days * self.daily_rate * self.quantity

	@property
	def deposit_total(self):
		"""Calcula la garantía fija total según las unidades contratadas."""
		return self.fixed_deposit * self.quantity

	@property
	def total_price(self):
		"""Suma el costo de arriendo y la garantía total."""
		return self.daily_rental_cost + self.deposit_total

	@property
	def has_consumed_stock(self):
		"""Indica si el contrato ya retiró unidades del inventario de la sede."""
		return self.status in (self.Status.PAID, self.Status.DELIVERED)


def equipment_availability(equipment, start_date, end_date):
	"""Resta solicitudes pendientes superpuestas al stock de cada sede."""
	stock_by_branch = {
		stock.branch_id: stock.quantity
		for stock in EquipmentStock.objects.filter(equipment=equipment)
	}
	pending_by_branch = {
		entry['branch_id']: entry['total']
		for entry in Rental.objects.filter(
			equipment=equipment,
			start_date__lte=end_date,
			end_date__gte=start_date,
			status=Rental.Status.PENDING,
		).values('branch_id').annotate(total=models.Sum('quantity'))
	}
	return [
		{
			'branch': branch,
			'quantity': max(
				stock_by_branch.get(branch.pk, 0) - pending_by_branch.get(branch.pk, 0),
				0,
			),
		}
		for branch in Branch.objects.all()
	]
