"""Pruebas del portal HTML, disponibilidad y administración de inventario."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Branch, Equipment, EquipmentStock, Rental, equipment_availability


class CatalogAndRentalTests(TestCase):
	"""Verifica los recorridos web de clientes y superadministradores."""

	def setUp(self):
		self.user = User.objects.create_user(username='cliente', password='ClaveSegura123!')
		self.equipment = Equipment.objects.first()
		self.branch = Branch.objects.first()
		self.start_date = timezone.localdate() + timedelta(days=3)
		self.end_date = self.start_date + timedelta(days=1)

	def test_superuser_login_redirects_to_inventory_management(self):
		User.objects.create_superuser(
			username='admin-inventario',
			password='ClaveSegura123!',
			email='admin@example.com',
		)

		response = self.client.post(reverse('login'), {
			'username': 'admin-inventario',
			'password': 'ClaveSegura123!',
		})

		self.assertRedirects(response, reverse('inventory_management'), fetch_redirect_response=False)

	def test_superuser_can_open_inventory_dashboard_from_admin(self):
		admin_user = User.objects.create_superuser(
			username='admin-inventario',
			password='ClaveSegura123!',
			email='admin@example.com',
		)
		self.client.force_login(admin_user)

		inventory_response = self.client.get(reverse('inventory_management'))
		admin_response = self.client.get('/admin/')

		self.assertEqual(inventory_response.status_code, 200)
		self.assertContains(inventory_response, 'GESTIÓN DE INVENTARIO')
		self.assertEqual(admin_response.status_code, 200)
		self.assertContains(admin_response, 'Administrar maquinaria y cantidades por sede')

	def test_inventory_list_offers_branch_and_name_filters(self):
		admin_user = User.objects.create_superuser(
			username='admin-inventario',
			password='ClaveSegura123!',
			email='admin@example.com',
		)
		self.client.force_login(admin_user)

		response = self.client.get(reverse('inventory_management'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.context['stock_items'].count(),
			EquipmentStock.objects.count(),
		)
		self.assertContains(response, 'Filtrar por sede')
		self.assertContains(response, f'<option value="{self.branch.pk}">', html=False)
		self.assertContains(response, 'Buscar maquinaria por nombre')
		self.assertContains(
			response,
			'id="inventory-equipment-filter" type="search" placeholder="Ej. Excavadora"',
		)
		self.assertContains(response, 'site.js?v=2')
		self.assertContains(
			response,
			f'data-branch-id="{self.branch.pk}" data-equipment-name="{self.equipment.name}"',
			html=False,
		)
		self.assertContains(response, 'Selecciona una sede para consultar su inventario.')

	def test_admin_rejects_invalid_rental_status_transition_in_form(self):
		admin_user = User.objects.create_superuser(
			username='admin-contratos',
			password='ClaveSegura123!',
			email='admin-contratos@example.com',
		)
		rental = Rental.objects.create(
			user=self.user,
			equipment=self.equipment,
			branch=self.branch,
			customer_name='Empresa de prueba',
			start_date=self.start_date,
			end_date=self.end_date,
		)
		self.client.force_login(admin_user)

		response = self.client.post(
			reverse('admin:catalog_rental_change', args=[rental.pk]),
			{
				'user': self.user.pk,
				'equipment': self.equipment.pk,
				'branch': self.branch.pk,
				'customer_name': rental.customer_name,
				'start_date': self.start_date.isoformat(),
				'end_date': self.end_date.isoformat(),
				'quantity': 1,
				'status': Rental.Status.DELIVERED,
				'_save': 'Guardar',
			},
		)

		rental.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'No se puede cambiar el contrato de Pendiente a Entregado.')
		self.assertEqual(rental.status, Rental.Status.PENDING)

	def test_non_superuser_cannot_manage_inventory(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('inventory_management'))

		self.assertEqual(response.status_code, 403)

	def test_superuser_can_add_equipment_with_initial_branch_stock(self):
		admin_user = User.objects.create_superuser(
			username='admin-inventario',
			password='ClaveSegura123!',
			email='admin@example.com',
		)
		self.client.force_login(admin_user)

		response = self.client.post(reverse('inventory_management'), {
			'action': 'add-equipment',
			'name': 'Manipulador telescópico',
			'brand': 'JLG',
			'category': Equipment.Category.ELEVACION,
			'image_url': 'https://example.com/manipulador.jpg',
			'description': 'Equipo de elevación para obra.',
			'daily_rate': 125000,
			'fixed_deposit': 0,
			'available': 'on',
			'branch': self.branch.pk,
			'quantity': 3,
		})

		self.assertRedirects(response, reverse('inventory_management'), fetch_redirect_response=False)
		new_equipment = Equipment.objects.get(name='Manipulador telescópico')
		self.assertEqual(
			EquipmentStock.objects.get(equipment=new_equipment, branch=self.branch).quantity,
			3,
		)

	def test_superuser_can_update_stock_for_equipment_and_branch(self):
		admin_user = User.objects.create_superuser(
			username='admin-inventario',
			password='ClaveSegura123!',
			email='admin@example.com',
		)
		self.client.force_login(admin_user)

		response = self.client.post(reverse('inventory_management'), {
			'action': 'update-stock',
			'equipment': self.equipment.pk,
			'branch': self.branch.pk,
			'quantity': 4,
		})

		self.assertRedirects(response, reverse('inventory_management'), fetch_redirect_response=False)
		self.assertEqual(
			EquipmentStock.objects.get(equipment=self.equipment, branch=self.branch).quantity,
			4,
		)

	def test_catalog_displays_seeded_fleet_and_branches(self):
		response = self.client.get(reverse('catalog'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['equipment'].count(), 8)
		self.assertEqual(response.context['branches'].count(), 5)

	def test_catalog_shows_rental_guidance_maintenance_tips_and_faq(self):
		response = self.client.get(reverse('catalog'))

		self.assertContains(response, 'Cómo arrendar maquinaria')
		self.assertContains(response, 'MANTENCIÓN EN TERRENO')
		self.assertContains(response, 'PREGUNTAS')
		self.assertContains(response, 'Teléfono: +56 9 0000 0000')
		self.assertNotContains(response, 'Teléfono de ejemplo')
		self.assertNotContains(response, 'tel:')

	def test_shared_html_footer_displays_student_identification_and_year(self):
		response = self.client.get(reverse('catalog'))

		self.assertContains(response, 'Constanza Bravo')
		self.assertContains(response, 'Sección TI3041')
		self.assertContains(response, '2026')

	def test_equipment_stock_is_seeded_for_each_branch(self):
		self.assertEqual(
			EquipmentStock.objects.filter(equipment=self.equipment).count(),
			Branch.objects.count(),
		)

	def test_catalog_shows_remaining_inventory_after_rental_request(self):
		self.client.force_login(self.user)
		today = timezone.localdate()
		rental_response = self.client.post(reverse('rent_equipment', args=[self.equipment.pk]), {
			'customer_name': 'Reserva de hoy',
			'branch': self.branch.pk,
			'start_date': today.isoformat(),
			'end_date': today.isoformat(),
		})

		self.assertEqual(rental_response.status_code, 302)
		response = self.client.get(reverse('catalog'))

		listed_equipment = next(item for item in response.context['equipment'] if item.pk == self.equipment.pk)
		self.assertEqual(listed_equipment.available_quantity, Branch.objects.count() - 1)
		self.assertContains(response, f'{Branch.objects.count() - 1} disponibles ahora')

	def test_catalog_shows_no_available_equipment_when_all_stock_is_rented(self):
		today = timezone.localdate()
		for equipment in Equipment.objects.all():
			for stock in EquipmentStock.objects.filter(equipment=equipment):
				for _ in range(stock.quantity):
					Rental.objects.create(
						user=self.user,
						equipment=equipment,
						branch=stock.branch,
						customer_name='Reserva de hoy',
						start_date=today,
						end_date=today,
					)

		response = self.client.get(reverse('catalog'))

		self.assertEqual(response.context['equipment'].count(), 0)
		self.assertContains(response, 'Por ahora no hay maquinaria disponible')

	def test_availability_is_counted_per_branch_for_requested_dates(self):
		Rental.objects.create(
			user=self.user,
			equipment=self.equipment,
			branch=self.branch,
			customer_name='Reserva existente',
			start_date=self.start_date,
			end_date=self.end_date,
		)

		availability = equipment_availability(self.equipment, self.start_date, self.end_date)
		quantities = {entry['branch'].pk: entry['quantity'] for entry in availability}

		self.assertEqual(quantities[self.branch.pk], 0)
		other_branch = Branch.objects.exclude(pk=self.branch.pk).first()
		self.assertEqual(quantities[other_branch.pk], 1)

	def test_rental_page_shows_inventory_for_each_branch(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('rent_equipment', args=[self.equipment.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Disponibilidad por sede')
		self.assertContains(response, self.branch.name)
		self.assertContains(response, '1 disponible')

	def test_availability_endpoint_returns_counts_for_selected_dates(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse('rent_equipment', args=[self.equipment.pk]), {
			'availability': '1',
			'start_date': self.start_date.isoformat(),
			'end_date': self.end_date.isoformat(),
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['total'], Branch.objects.count())
		self.assertTrue(all(entry['quantity'] == 1 for entry in response.json()['branches']))

	def test_backhoe_uses_updated_image(self):
		backhoe = Equipment.objects.get(name='Retroexcavadora 4x4')

		self.assertEqual(
			backhoe.image_url,
			'https://images.unsplash.com/photo-1580901368919-7738efb0f87e?auto=format&fit=crop&w=1200&q=82',
		)

	def test_category_filter_only_returns_matching_equipment(self):
		response = self.client.get(reverse('catalog'), {'categoria': Equipment.Category.ELEVACION})

		self.assertEqual(response.status_code, 200)
		self.assertGreater(response.context['equipment'].count(), 0)
		self.assertTrue(all(item.category == Equipment.Category.ELEVACION for item in response.context['equipment']))

		combined = self.client.get(reverse('catalog'), {
			'categoria': Equipment.Category.ELEVACION,
			'q': 'Toyota',
		})
		self.assertEqual(list(combined.context['equipment'].values_list('brand', flat=True)), ['Toyota'])

	def test_empty_catalog_shows_no_equipment_available_notice(self):
		Equipment.objects.update(available=False)

		response = self.client.get(reverse('catalog'))

		self.assertContains(response, 'Por ahora no hay maquinaria disponible')

	def test_anonymous_users_are_redirected_before_renting(self):
		response = self.client.get(reverse('rent_equipment', args=[self.equipment.pk]))

		self.assertRedirects(
			response,
			f'{reverse("login")}?next={reverse("rent_equipment", args=[self.equipment.pk])}',
			fetch_redirect_response=False,
		)

	def test_authenticated_user_can_submit_rental(self):
		self.client.force_login(self.user)

		response = self.client.post(reverse('rent_equipment', args=[self.equipment.pk]), {
			'customer_name': 'Camila Rojas',
			'branch': self.branch.pk,
			'start_date': self.start_date.isoformat(),
			'end_date': self.end_date.isoformat(),
		})

		rental = Rental.objects.get(user=self.user)
		self.assertRedirects(response, reverse('rental_success', args=[rental.pk]), fetch_redirect_response=False)
		self.assertEqual(rental.equipment, self.equipment)
		self.assertEqual(rental.status, Rental.Status.PENDING)

	def test_equipment_cannot_be_requested_for_overlapping_dates(self):
		Rental.objects.create(
			user=self.user,
			equipment=self.equipment,
			branch=self.branch,
			customer_name='Reserva existente',
			start_date=self.start_date,
			end_date=self.end_date,
		)
		self.client.force_login(self.user)

		response = self.client.post(reverse('rent_equipment', args=[self.equipment.pk]), {
			'customer_name': 'Camila Rojas',
			'branch': self.branch.pk,
			'start_date': self.start_date.isoformat(),
			'end_date': self.end_date.isoformat(),
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Rental.objects.count(), 1)
		self.assertContains(response, 'ya está reservada')

	def test_overlapping_rental_at_another_branch_does_not_block_request(self):
		other_branch = Branch.objects.exclude(pk=self.branch.pk).first()
		Rental.objects.create(
			user=self.user,
			equipment=self.equipment,
			branch=self.branch,
			customer_name='Reserva existente',
			start_date=self.start_date,
			end_date=self.end_date,
		)
		self.client.force_login(self.user)

		response = self.client.post(reverse('rent_equipment', args=[self.equipment.pk]), {
			'customer_name': 'Camila Rojas',
			'branch': other_branch.pk,
			'start_date': self.start_date.isoformat(),
			'end_date': self.end_date.isoformat(),
		})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Rental.objects.count(), 2)
		self.assertEqual(Rental.objects.latest('created_at').branch, other_branch)
