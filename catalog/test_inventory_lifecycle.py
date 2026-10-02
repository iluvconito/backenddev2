"""Pruebas de transiciones contractuales, precios snapshot y stock físico."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from .models import Branch, Equipment, EquipmentStock, Rental, RentalCart, RentalCartItem
from .services import transition_rental_status
from .views import equipment_with_availability


class RentalInventoryLifecycleTests(TestCase):
    """Valida los efectos de cada etapa del contrato sobre el inventario."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='ciclo-cliente', password='ClaveSegura123!')
        cls.equipment = Equipment.objects.first()
        cls.branch = Branch.objects.first()
        cls.stock = EquipmentStock.objects.get(equipment=cls.equipment, branch=cls.branch)
        cls.physical_total = EquipmentStock.objects.filter(
            equipment=cls.equipment,
        ).aggregate(total=Sum('quantity'))['total']
        cls.today = timezone.localdate()

    def make_contract(self, **overrides):
        """Crea un contrato pendiente de prueba con precios actuales por defecto."""
        defaults = {
            'user': self.user,
            'equipment': self.equipment,
            'branch': self.branch,
            'customer_name': 'Empresa de prueba',
            'start_date': self.today + timedelta(days=3),
            'end_date': self.today + timedelta(days=4),
            'quantity': 1,
            'daily_rate': self.equipment.daily_rate,
            'fixed_deposit': self.equipment.fixed_deposit,
        }
        defaults.update(overrides)
        return Rental.objects.create(**defaults)

    def test_pending_contract_does_not_consume_physical_stock(self):
        original_quantity = self.stock.quantity
        contract = self.make_contract(quantity=1)

        self.assertEqual(self.stock.refresh_from_db(), None)
        self.assertEqual(self.stock.quantity, original_quantity)
        self.assertFalse(contract.has_consumed_stock)

    def test_paid_contract_atomically_consumes_its_quantity(self):
        original_quantity = self.stock.quantity
        contract = self.make_contract(quantity=1)

        paid = transition_rental_status(contract.pk, Rental.Status.PAID)

        self.stock.refresh_from_db()
        self.assertEqual(paid.status, Rental.Status.PAID)
        self.assertEqual(self.stock.quantity, original_quantity - 1)
        self.assertEqual(self.equipment.refresh_from_db(), None)
        self.assertEqual(self.equipment.physical_units, self.physical_total)
        self.assertEqual(
            equipment_with_availability(self.today).get(pk=self.equipment.pk).available_quantity,
            self.physical_total - 1,
        )

    def test_completing_a_delivered_contract_returns_its_quantity(self):
        original_quantity = self.stock.quantity
        contract = self.make_contract(quantity=1)
        transition_rental_status(contract.pk, Rental.Status.PAID)
        transition_rental_status(contract.pk, Rental.Status.DELIVERED)

        completed = transition_rental_status(contract.pk, Rental.Status.COMPLETED)

        self.stock.refresh_from_db()
        self.assertEqual(completed.status, Rental.Status.COMPLETED)
        self.assertEqual(self.stock.quantity, original_quantity)
        self.assertEqual(self.equipment.physical_units, self.physical_total)

    def test_cancelling_a_paid_contract_returns_its_quantity_only_once(self):
        original_quantity = self.stock.quantity
        contract = self.make_contract(quantity=1)
        transition_rental_status(contract.pk, Rental.Status.PAID)

        cancelled = transition_rental_status(contract.pk, Rental.Status.CANCELLED)

        self.stock.refresh_from_db()
        self.assertEqual(cancelled.status, Rental.Status.CANCELLED)
        self.assertEqual(self.stock.quantity, original_quantity)
        with self.assertRaises(ValidationError):
            transition_rental_status(contract.pk, Rental.Status.COMPLETED)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, original_quantity)

    def test_pending_cancellation_does_not_change_stock(self):
        original_quantity = self.stock.quantity
        contract = self.make_contract(quantity=1)

        transition_rental_status(contract.pk, Rental.Status.CANCELLED)

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, original_quantity)

    def test_payment_fails_without_stock_and_leaves_contract_pending(self):
        contract = self.make_contract(quantity=self.stock.quantity + 1)

        with self.assertRaises(ValidationError):
            transition_rental_status(contract.pk, Rental.Status.PAID)

        contract.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(contract.status, Rental.Status.PENDING)
        self.assertEqual(self.stock.quantity, 1)

    def test_contract_price_uses_snapshots_quantity_days_and_fixed_deposit(self):
        self.equipment.daily_rate = 100
        self.equipment.fixed_deposit = 500
        self.equipment.save(update_fields=('daily_rate', 'fixed_deposit'))
        contract = self.make_contract(
            quantity=2,
            daily_rate=100,
            fixed_deposit=500,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
        )

        self.equipment.daily_rate = 999
        self.equipment.fixed_deposit = 999
        self.equipment.save(update_fields=('daily_rate', 'fixed_deposit'))

        contract.refresh_from_db()
        self.assertEqual(contract.daily_rental_cost, 600)
        self.assertEqual(contract.deposit_total, 1000)
        self.assertEqual(contract.total_price, 1600)

    def test_contract_without_explicit_snapshots_uses_current_equipment_prices(self):
        self.equipment.daily_rate = 100
        self.equipment.fixed_deposit = 500
        self.equipment.save(update_fields=('daily_rate', 'fixed_deposit'))

        contract = self.make_contract(daily_rate=0, fixed_deposit=0)

        self.assertEqual(contract.daily_rate, 100)
        self.assertEqual(contract.fixed_deposit, 500)

    def test_cart_persists_as_one_cart_per_user_without_consuming_stock(self):
        cart, created = RentalCart.objects.get_or_create(user=self.user)
        RentalCartItem.objects.create(
            cart=cart,
            equipment=self.equipment,
            branch=self.branch,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=2),
            quantity=1,
        )
        original_quantity = self.stock.quantity

        second_cart, second_created = RentalCart.objects.get_or_create(user=self.user)
        self.stock.refresh_from_db()

        self.assertTrue(created)
        self.assertFalse(second_created)
        self.assertEqual(second_cart.pk, cart.pk)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(self.stock.quantity, original_quantity)
