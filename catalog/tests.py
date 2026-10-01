from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Branch, Equipment, Rental


class CatalogAndRentalTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='cliente', password='ClaveSegura123!')
		self.equipment = Equipment.objects.first()
		self.branch = Branch.objects.first()
		self.start_date = timezone.localdate() + timedelta(days=3)
		self.end_date = self.start_date + timedelta(days=1)

	def test_catalog_displays_seeded_fleet_and_branches(self):
		response = self.client.get(reverse('catalog'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['equipment'].count(), 8)
		self.assertEqual(response.context['branches'].count(), 5)

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
