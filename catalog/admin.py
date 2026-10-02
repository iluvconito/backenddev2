"""Configuración del admin y validación del ciclo de contratos."""

from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms

from .models import Branch, Equipment, EquipmentStock, Rental
from .services import ALLOWED_STATUS_TRANSITIONS, transition_rental_status


class RentalAdminForm(forms.ModelForm):
	"""Valida transiciones y stock antes de que el admin acepte el formulario."""

	class Meta:
		model = Rental
		fields = '__all__'

	def clean_status(self):
		"""Rechaza saltos de estado y pagos sin unidades suficientes."""
		status = self.cleaned_data['status']
		if not self.instance.pk:
			if status != Rental.Status.PENDING:
				raise forms.ValidationError('Los contratos nuevos deben comenzar pendientes.')
			return status

		current_status = Rental.objects.only('status').get(pk=self.instance.pk).status
		if status == current_status:
			return status
		if status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
			raise forms.ValidationError(
				f'No se puede cambiar el contrato de {Rental.Status(current_status).label} '
				f'a {Rental.Status(status).label}.'
			)

		quantity = self.cleaned_data.get('quantity', self.instance.quantity)
		if status == Rental.Status.PAID:
			stock = EquipmentStock.objects.filter(
				equipment=self.instance.equipment,
				branch=self.instance.branch,
			).first()
			if stock is None:
				raise forms.ValidationError(
					'No existe inventario registrado para esta maquinaria y sede.'
				)
			if stock.quantity < quantity:
				raise forms.ValidationError(
					f'Inventario insuficiente en {self.instance.branch.name}: '
					f'{stock.quantity} unidad(es) disponible(s), {quantity} solicitada(s).'
				)
		return status


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
	"""Organiza las sedes para búsqueda y consulta administrativa."""

	list_display = ('name', 'region', 'phone')
	search_fields = ('name', 'region')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
	"""Muestra tarifas, garantías y unidades físicas en el listado de equipos."""

	list_display = ('name', 'brand', 'category', 'daily_rate', 'fixed_deposit', 'physical_units', 'available')
	list_filter = ('category', 'available')
	search_fields = ('name', 'brand')


@admin.register(EquipmentStock)
class EquipmentStockAdmin(admin.ModelAdmin):
	"""Facilita mantener cantidades por equipo y sede."""

	list_display = ('equipment', 'branch', 'quantity')
	list_filter = ('branch', 'equipment__category')
	search_fields = ('equipment__name', 'branch__name')


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
	"""Gestiona contratos delegando transiciones al servicio transaccional."""

	form = RentalAdminForm
	list_display = ('equipment', 'customer_name', 'branch', 'start_date', 'end_date', 'quantity', 'total_price', 'status')
	list_filter = ('status', 'branch')
	search_fields = ('customer_name', 'user__username', 'equipment__name')
	readonly_fields = ('daily_rate', 'fixed_deposit')

	def get_readonly_fields(self, request, obj=None):
		"""Fija equipo, sede y cantidad una vez creado el contrato."""
		if obj is not None:
			return self.readonly_fields + ('equipment', 'branch', 'quantity')
		return self.readonly_fields

	def save_model(self, request, obj, form, change):
		"""Persiste datos y ejecuta el servicio para las transiciones solicitadas."""
		target_status = obj.status
		if change:
			current_status = Rental.objects.only('status').get(pk=obj.pk).status
			obj.status = current_status
			super().save_model(request, obj, form, change)
			if target_status != current_status:
				try:
					updated = transition_rental_status(obj.pk, target_status)
				except ValidationError as error:
					raise ValidationError({'status': error.messages}) from error
				obj.status = updated.status
			return
		obj.daily_rate = obj.equipment.daily_rate
		obj.fixed_deposit = obj.equipment.fixed_deposit
		super().save_model(request, obj, form, change)
