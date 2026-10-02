"""Vistas HTML del catálogo, solicitudes y gestión administrativa de inventario."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import InventoryEquipmentForm, InventoryStockForm, RegistrationForm, RentalForm
from .models import Branch, Equipment, EquipmentStock, Rental, equipment_availability


class PortalLoginView(LoginView):
	"""Redirige a superusuarios al panel de inventario después del login."""

	template_name = 'registration/login.html'

	def get_default_redirect_url(self):
		"""Prioriza el dashboard de inventario cuando el usuario es superusuario."""
		if self.request.user.is_superuser and not self.get_redirect_url():
			return reverse('inventory_management')
		return super().get_default_redirect_url()


def equipment_with_availability(on_date):
	"""Anota stock físico y reservas pendientes para el listado del catálogo."""
	stock_total = (
		EquipmentStock.objects
		.filter(equipment_id=OuterRef('pk'))
		.values('equipment_id')
		.annotate(total=Sum('quantity'))
		.values('total')[:1]
	)
	checked_out_total = (
		Rental.objects.filter(
			equipment_id=OuterRef('pk'),
			status__in=(Rental.Status.PAID, Rental.Status.DELIVERED),
		)
		.values('equipment_id')
		.annotate(total=Sum('quantity'))
		.values('total')[:1]
	)
	reserved_total = (
		Rental.objects.filter(
			equipment_id=OuterRef('pk'),
			start_date__lte=on_date,
			end_date__gte=on_date,
			status=Rental.Status.PENDING,
		)
		.values('equipment_id')
		.annotate(total=Sum('quantity'))
		.values('total')[:1]
	)
	return Equipment.objects.annotate(
		stock_on_hand=Coalesce(Subquery(stock_total), Value(0), output_field=IntegerField()),
		checked_out_units=Coalesce(Subquery(checked_out_total), Value(0), output_field=IntegerField()),
		reserved_units=Coalesce(Subquery(reserved_total), Value(0), output_field=IntegerField()),
	).annotate(
		total_stock=F('stock_on_hand') + F('checked_out_units'),
		available_quantity=F('stock_on_hand') - F('reserved_units'),
	)


def catalog(request):
	"""Renderiza el catálogo filtrado por disponibilidad, categoría y búsqueda."""
	equipment = equipment_with_availability(timezone.localdate()).filter(
		available=True,
		available_quantity__gt=0,
	)
	has_available_equipment = equipment.exists()
	category = request.GET.get('categoria', '')
	query = request.GET.get('q', '').strip()
	if category:
		equipment = equipment.filter(category=category)
	if query:
		equipment = equipment.filter(Q(name__icontains=query) | Q(brand__icontains=query))
	return render(request, 'catalog/index.html', {
		'equipment': equipment,
		'has_available_equipment': has_available_equipment,
		'branches': Branch.objects.all(),
		'categories': Equipment.Category.choices,
		'active_category': category,
		'search_query': query,
	})


def equipment_detail(request, pk):
	"""Muestra los detalles del equipo seleccionado si está habilitado."""
	item = get_object_or_404(
		equipment_with_availability(timezone.localdate()),
		pk=pk,
		available=True,
	)
	return render(request, 'catalog/detail.html', {'item': item, 'branches': Branch.objects.all()})


@login_required
def rent_equipment(request, pk):
	"""Consulta disponibilidad por rango o registra una solicitud pendiente."""
	item = get_object_or_404(Equipment, pk=pk, available=True)
	if request.method == 'GET' and request.GET.get('availability') == '1':
		start_date = parse_date(request.GET.get('start_date', ''))
		end_date = parse_date(request.GET.get('end_date', ''))
		if not start_date or not end_date or end_date < start_date:
			return JsonResponse({'error': 'Selecciona un rango de fechas válido.'}, status=400)
		availability = equipment_availability(item, start_date, end_date)
		return JsonResponse({
			'total': sum(entry['quantity'] for entry in availability),
			'branches': [
				{
					'id': entry['branch'].pk,
					'name': entry['branch'].name,
					'region': entry['branch'].region,
					'address': entry['branch'].address,
					'quantity': entry['quantity'],
				}
				for entry in availability
			],
		})

	today = timezone.localdate()
	start_date = parse_date(request.POST.get('start_date', '')) if request.method == 'POST' else None
	end_date = parse_date(request.POST.get('end_date', '')) if request.method == 'POST' else None
	start_date = start_date or today
	end_date = end_date or start_date
	if end_date < start_date:
		end_date = start_date
	availability = equipment_availability(item, start_date, end_date)
	form = RentalForm(request.POST or None, equipment=item)
	if request.method == 'POST' and form.is_valid():
		rental = form.save(commit=False)
		rental.user = request.user
		rental.equipment = item
		rental.quantity = 1
		rental.daily_rate = item.daily_rate
		rental.fixed_deposit = item.fixed_deposit
		rental.save()
		messages.success(request, 'Recibimos tu solicitud. Nuestro equipo se pondrá en contacto para confirmar.')
		return redirect('rental_success', pk=rental.pk)
	return render(request, 'catalog/rent.html', {
		'item': item,
		'form': form,
		'availability': availability,
		'total_available': sum(entry['quantity'] for entry in availability),
		'availability_start_date': start_date,
		'availability_end_date': end_date,
	})


@login_required
def rental_success(request, pk):
	"""Muestra el comprobante solo al usuario dueño de la solicitud."""
	rental = get_object_or_404(Rental, pk=pk, user=request.user)
	return render(request, 'catalog/success.html', {'rental': rental})


@login_required
def my_rentals(request):
	"""Lista los contratos del usuario autenticado."""
	rentals = Rental.objects.filter(user=request.user).select_related('equipment', 'branch')
	return render(request, 'catalog/my_rentals.html', {'rentals': rentals})


@login_required
def inventory_management(request):
	"""Permite a superusuarios crear maquinaria y actualizar stock por sede."""
	if not request.user.is_superuser:
		return HttpResponseForbidden('Solo los superadministradores pueden gestionar el inventario.')

	action = request.POST.get('action') if request.method == 'POST' else None
	equipment_form = InventoryEquipmentForm(
		request.POST if action == 'add-equipment' else None,
	)
	stock_form = InventoryStockForm(
		request.POST if action == 'update-stock' else None,
	)
	if request.method == 'POST' and action == 'add-equipment' and equipment_form.is_valid():
		with transaction.atomic():
			equipment = equipment_form.save()
			EquipmentStock.objects.create(
				equipment=equipment,
				branch=equipment_form.cleaned_data['branch'],
				quantity=equipment_form.cleaned_data['quantity'],
			)
		messages.success(request, 'Maquinaria e inventario inicial agregados correctamente.')
		return redirect('inventory_management')

	if request.method == 'POST' and action == 'update-stock' and stock_form.is_valid():
		EquipmentStock.objects.update_or_create(
			equipment=stock_form.cleaned_data['equipment'],
			branch=stock_form.cleaned_data['branch'],
			defaults={'quantity': stock_form.cleaned_data['quantity']},
		)
		messages.success(request, 'Inventario actualizado correctamente.')
		return redirect('inventory_management')

	return render(request, 'catalog/inventory.html', {
		'equipment_form': equipment_form,
		'stock_form': stock_form,
		'branches': Branch.objects.all(),
		'stock_items': EquipmentStock.objects.select_related('equipment', 'branch'),
		'equipment_count': Equipment.objects.count(),
		'branch_count': Branch.objects.count(),
		'inventory_count': EquipmentStock.objects.count(),
	})


def register(request):
	"""Crea la cuenta del cliente y abre su sesión tras el registro."""
	form = RegistrationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect('catalog')
	return render(request, 'registration/register.html', {'form': form})


@require_POST
def logout_user(request):
	"""Cierra la sesión web y devuelve al usuario al catálogo."""
	logout(request)
	return redirect('catalog')
