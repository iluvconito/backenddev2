"""Pruebas de permisos, filtros y flujos API del arriendo de maquinaria."""

import yaml
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Branch, Equipment, EquipmentStock, Rental, RentalCart, RentalCartItem
from .permissions import (
    CONSTRUCTION_COMPANY_ROLE,
    EXECUTIVE_ROLE,
)


class CatalogApiTests(APITestCase):
    """Comprueba que la API respete roles y mantenga el inventario consistente."""

    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.first()
        cls.equipment = Equipment.objects.first()
        cls.client_user = User.objects.create_user(
            username='api-cliente',
            password='ClaveSegura123!',
        )
        cls.executive_user = User.objects.create_superuser(
            username='api-ejecutivo',
            password='ClaveSegura123!',
            email='api-ejecutivo@example.com',
        )

    def test_equipment_endpoint_includes_inventory_by_branch(self):
        self.authenticate_as(self.client_user)
        response = self.client.get(reverse('api:equipment-detail', args=[self.equipment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.equipment.pk)
        self.assertIn('inventory', response.data)
        self.assertIn(
            self.branch.pk,
            [item['branch']['id'] for item in response.data['inventory']],
        )

    def test_equipment_endpoint_supports_filters_search_and_ordering(self):
        self.authenticate_as(self.client_user)
        response = self.client.get(reverse('api:equipment-list'), {
            'category': self.equipment.category,
            'brand': self.equipment.brand,
            'search': self.equipment.name,
            'min_daily_rate': 1,
            'max_daily_rate': self.equipment.daily_rate,
            'ordering': '-daily_rate',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.equipment.pk)

    def test_equipment_list_is_public(self):
        response = self.client.get(reverse('api:equipment-list'))

        self.assertEqual(response.status_code, 200)

    def test_branch_endpoint_can_filter_by_region_and_search(self):
        self.authenticate_as(self.client_user)
        response = self.client.get(reverse('api:branch-list'), {
            'region': self.branch.region,
            'search': self.branch.name,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(branch['region'] == self.branch.region for branch in response.data))
        self.assertTrue(any(branch['id'] == self.branch.pk for branch in response.data))

    def test_inventory_endpoint_can_filter_by_branch_and_equipment(self):
        self.authenticate_as(self.executive_user)
        response = self.client.get(reverse('api:stock-list'), {
            'branch': self.branch.pk,
            'equipment': self.equipment.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['quantity'], EquipmentStock.objects.get(
            branch=self.branch,
            equipment=self.equipment,
        ).quantity)

    def test_inventory_endpoint_reports_date_range_availability(self):
        start_date = timezone.localdate() + timedelta(days=5)
        end_date = start_date + timezone.timedelta(days=2)
        Rental.objects.create(
            user=self.client_user,
            equipment=self.equipment,
            branch=self.branch,
            customer_name='Solicitud pendiente',
            start_date=start_date,
            end_date=end_date,
            quantity=1,
            daily_rate=self.equipment.daily_rate,
            status=Rental.Status.PENDING,
        )
        self.authenticate_as(self.executive_user)

        response = self.client.get(reverse('api:stock-list'), {
            'branch': self.branch.pk,
            'equipment': self.equipment.pk,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['quantity'], 1)
        self.assertEqual(response.data[0]['available_quantity'], 0)

    def test_catalog_endpoints_require_jwt(self):
        response = self.client.get(reverse('api:stock-list'))

        self.assertEqual(response.status_code, 401)

    def test_client_role_cannot_read_inventory_endpoint(self):
        self.authenticate_as(self.client_user)

        response = self.client.get(reverse('api:stock-list'))

        self.assertEqual(response.status_code, 403)

    def test_jwt_pair_contains_role_claim_and_refresh_token(self):
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': self.client_user.username,
            'password': 'ClaveSegura123!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        self.assertEqual(AccessToken(response.data['access'])['role'], CONSTRUCTION_COMPANY_ROLE)
        self.assertEqual(RefreshToken(response.data['refresh'])['role'], CONSTRUCTION_COMPANY_ROLE)

    def test_executive_role_can_read_inventory_endpoint(self):
        self.authenticate_as(self.executive_user)

        response = self.client.get(reverse('api:stock-list'))

        self.assertEqual(response.status_code, 200)

    def test_refresh_token_preserves_role_claim_on_new_access_token(self):
        token_response = self.client.post(reverse('token_obtain_pair'), {
            'username': self.executive_user.username,
            'password': 'ClaveSegura123!',
        })
        refresh_response = self.client.post(reverse('token_refresh'), {
            'refresh': token_response.data['refresh'],
        })

        self.assertEqual(refresh_response.status_code, 200)

        self.assertEqual(AccessToken(refresh_response.data['access'])['role'], EXECUTIVE_ROLE)

    def test_openapi_schema_and_swagger_docs_are_available(self):
        schema_response = self.client.get(reverse('schema'))
        docs_response = self.client.get(reverse('swagger-ui'))

        self.assertEqual(schema_response.status_code, 200)
        schema = yaml.safe_load(schema_response.content)
        self.assertIn('/api/maquinarias/', schema['paths'])
        self.assertIn('/api/sedes/', schema['paths'])
        self.assertIn('/api/inventario/', schema['paths'])
        self.assertIn('/api/carro-arriendo/', schema['paths'])
        self.assertIn('/api/contratos/checkout/', schema['paths'])
        self.assertIn('/api/mis-contratos/', schema['paths'])
        self.assertIn('/api/contratos/{id}/estado/', schema['paths'])
        self.assertIn('/api/token/', schema['paths'])
        self.assertIn('/api/token/refresh/', schema['paths'])
        self.assertIn(
            {'jwtAuth': []},
            schema['paths']['/api/maquinarias/']['get']['security'],
        )
        self.assertNotIn('security', schema['paths']['/api/token/']['post'])
        self.assertNotIn('security', schema['paths']['/api/token/refresh/']['post'])
        self.assertIn('jwtAuth', schema['components']['securitySchemes'])
        self.assertEqual(docs_response.status_code, 200)
        self.assertContains(docs_response, 'SwaggerUIBundle')

    def test_company_can_create_list_and_delete_own_cart_items(self):
        self.authenticate_as(self.client_user)
        payload = self.cart_payload()

        add_response = self.client.post(reverse('api:rental-cart'), payload, format='json')
        list_response = self.client.get(reverse('api:rental-cart'))

        self.assertEqual(add_response.status_code, 201)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data['items']), 1)
        self.assertEqual(list_response.data['items'][0]['quantity'], 1)

        delete_response = self.client.delete(
            reverse('api:rental-cart'),
            {'item_id': add_response.data['id']},
            format='json',
        )

        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(RentalCartItem.objects.filter(cart__user=self.client_user).exists())

    def test_company_can_empty_own_cart_without_affecting_other_users(self):
        other_user = User.objects.create_user(username='otra-empresa', password='ClaveSegura123!')
        own_item = RentalCartItem.objects.create(
            cart=RentalCart.objects.create(user=self.client_user),
            equipment=self.equipment,
            branch=self.branch,
            start_date=self.future_date(),
            end_date=self.future_date(),
        )
        other_item = RentalCartItem.objects.create(
            cart=RentalCart.objects.create(user=other_user),
            equipment=self.equipment,
            branch=self.branch,
            start_date=self.future_date(),
            end_date=self.future_date(),
        )
        self.authenticate_as(self.client_user)

        response = self.client.delete(reverse('api:rental-cart'))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(RentalCartItem.objects.filter(pk=own_item.pk).exists())
        self.assertTrue(RentalCartItem.objects.filter(pk=other_item.pk).exists())

    def test_company_cannot_add_more_units_than_branch_stock(self):
        self.authenticate_as(self.client_user)
        response = self.client.post(
            reverse('api:rental-cart'),
            {**self.cart_payload(), 'quantity': 2},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RentalCartItem.objects.filter(cart__user=self.client_user).exists())

    def test_company_can_checkout_cart_and_view_own_contracts(self):
        self.authenticate_as(self.client_user)
        self.client.post(reverse('api:rental-cart'), self.cart_payload(), format='json')
        stock_before = EquipmentStock.objects.get(
            equipment=self.equipment,
            branch=self.branch,
        ).quantity

        checkout_response = self.client.post(
            reverse('api:contract-checkout'),
            {'customer_name': 'Empresa Demo'},
            format='json',
        )
        contracts_response = self.client.get(reverse('api:my-contracts'))

        self.assertEqual(checkout_response.status_code, 201)
        self.assertEqual(len(checkout_response.data), 1)
        self.assertEqual(checkout_response.data[0]['status'], Rental.Status.PENDING)
        self.assertEqual(checkout_response.data[0]['customer_name'], 'Empresa Demo')
        self.assertFalse(RentalCartItem.objects.filter(cart__user=self.client_user).exists())
        self.assertEqual(len(contracts_response.data), 1)
        self.assertEqual(checkout_response.data[0]['daily_rate'], self.equipment.daily_rate)
        self.assertEqual(
            EquipmentStock.objects.get(equipment=self.equipment, branch=self.branch).quantity,
            stock_before,
        )

    def test_checkout_rejects_empty_cart(self):
        self.authenticate_as(self.client_user)

        response = self.client.post(reverse('api:contract-checkout'), {}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('cart', response.data)

    def test_company_cannot_see_other_users_contracts(self):
        Rental.objects.create(
            user=self.executive_user,
            equipment=self.equipment,
            branch=self.branch,
            customer_name='Contrato privado',
            start_date=self.future_date(),
            end_date=self.future_date(),
        )
        self.authenticate_as(self.client_user)

        response = self.client.get(reverse('api:my-contracts'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_executive_can_patch_contract_status_but_company_cannot(self):
        contract = Rental.objects.create(
            user=self.client_user,
            equipment=self.equipment,
            branch=self.branch,
            customer_name='Empresa Demo',
            start_date=self.future_date(),
            end_date=self.future_date(),
        )
        self.authenticate_as(self.client_user)
        forbidden_response = self.client.patch(
            reverse('api:contract-status', args=[contract.pk]),
            {'status': Rental.Status.PAID},
            format='json',
        )
        self.assertEqual(forbidden_response.status_code, 403)

        self.authenticate_as(self.executive_user)
        response = self.client.patch(
            reverse('api:contract-status', args=[contract.pk]),
            {'status': Rental.Status.PAID},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], Rental.Status.PAID)
        self.assertEqual(
            EquipmentStock.objects.get(equipment=self.equipment, branch=self.branch).quantity,
            0,
        )

    def test_company_cannot_manage_equipment(self):
        self.authenticate_as(self.client_user)

        response = self.client.post(reverse('api:equipment-list'), {
            'name': 'Equipo no autorizado',
            'brand': 'Demo',
            'category': self.equipment.category,
            'image_url': 'https://example.com/equipo.jpg',
            'description': 'No debería crearse.',
            'daily_rate': 1000,
            'available': True,
        }, format='json')

        self.assertEqual(response.status_code, 403)

    def test_executive_can_create_update_and_delete_equipment(self):
        self.authenticate_as(self.executive_user)
        payload = {
            'name': 'Equipo API',
            'brand': 'Demo',
            'category': self.equipment.category,
            'image_url': 'https://example.com/equipo-api.jpg',
            'description': 'Equipo creado para validar permisos.',
            'daily_rate': 200000,
            'available': True,
        }

        create_response = self.client.post(
            reverse('api:equipment-list'),
            payload,
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)
        equipment_id = create_response.data['id']

        update_response = self.client.put(
            reverse('api:equipment-detail', args=[equipment_id]),
            {**payload, 'name': 'Equipo API actualizado'},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['name'], 'Equipo API actualizado')

        delete_response = self.client.delete(
            reverse('api:equipment-detail', args=[equipment_id]),
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Equipment.objects.filter(pk=equipment_id).exists())

    def future_date(self):
        from datetime import timedelta
        from django.utils import timezone

        return timezone.localdate() + timedelta(days=7)

    def cart_payload(self):
        date = self.future_date().isoformat()
        return {
            'equipment_id': self.equipment.pk,
            'branch_id': self.branch.pk,
            'start_date': date,
            'end_date': date,
            'quantity': 1,
        }

    def authenticate_as(self, user):
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': user.username,
            'password': 'ClaveSegura123!',
        })
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
