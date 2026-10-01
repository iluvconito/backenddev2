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
	available = models.BooleanField(default=True)

	class Meta:
		ordering = ['category', 'name']
		verbose_name_plural = 'equipment'

	def __str__(self):
		return self.name


class Rental(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Solicitud recibida'
		APPROVED = 'approved', 'Confirmada'
		CANCELLED = 'cancelled', 'Cancelada'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
	equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='rentals')
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='rentals')
	customer_name = models.CharField(max_length=120)
	start_date = models.DateField()
	end_date = models.DateField()
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='rental_end_on_or_after_start'),
		]

	def __str__(self):
		return f'{self.equipment} · {self.start_date}–{self.end_date}'

	@property
	def rental_days(self):
		return (self.end_date - self.start_date).days + 1

	@property
	def total_price(self):
		return self.rental_days * self.equipment.daily_rate
