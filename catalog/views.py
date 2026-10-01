from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RegistrationForm, RentalForm
from .models import Branch, Equipment, Rental


def catalog(request):
	equipment = Equipment.objects.filter(available=True)
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
	item = get_object_or_404(Equipment, pk=pk, available=True)
	return render(request, 'catalog/detail.html', {'item': item, 'branches': Branch.objects.all()})


@login_required
def rent_equipment(request, pk):
	item = get_object_or_404(Equipment, pk=pk, available=True)
	form = RentalForm(request.POST or None, initial={'equipment': item})
	if request.method == 'POST' and form.is_valid():
		rental = form.save(commit=False)
		rental.user = request.user
		rental.equipment = item
		rental.save()
		messages.success(request, 'Recibimos tu solicitud. Nuestro equipo se pondrá en contacto para confirmar.')
		return redirect('rental_success', pk=rental.pk)
	return render(request, 'catalog/rent.html', {'item': item, 'form': form})


@login_required
def rental_success(request, pk):
	rental = get_object_or_404(Rental, pk=pk, user=request.user)
	return render(request, 'catalog/success.html', {'rental': rental})


@login_required
def my_rentals(request):
	rentals = Rental.objects.filter(user=request.user).select_related('equipment', 'branch')
	return render(request, 'catalog/my_rentals.html', {'rentals': rentals})


def register(request):
	form = RegistrationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect('catalog')
	return render(request, 'registration/register.html', {'form': form})


@require_POST
def logout_user(request):
	logout(request)
	return redirect('catalog')
