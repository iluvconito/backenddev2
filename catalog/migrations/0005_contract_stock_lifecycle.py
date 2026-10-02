from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_contract_status_and_prices(apps, schema_editor):
    """Congela precios históricos y migra contratos aprobados a pagados, descontando su stock."""
    EquipmentStock = apps.get_model('catalog', 'EquipmentStock')
    Rental = apps.get_model('catalog', 'Rental')
    database = schema_editor.connection.alias

    for rental in Rental.objects.using(database).select_related('equipment').iterator():
        rental.daily_rate = rental.equipment.daily_rate
        rental.fixed_deposit = rental.equipment.fixed_deposit
        if rental.status == 'approved':
            stock = EquipmentStock.objects.using(database).filter(
                equipment_id=rental.equipment_id,
                branch_id=rental.branch_id,
            ).first()
            if stock is None or stock.quantity < rental.quantity:
                raise RuntimeError(
                    f'No hay inventario suficiente para migrar el contrato aprobado {rental.pk}.'
                )
            stock.quantity -= rental.quantity
            stock.save(using=database, update_fields=('quantity',))
            rental.status = 'paid'
        rental.save(
            using=database,
            update_fields=('daily_rate', 'fixed_deposit', 'quantity', 'status'),
        )


def migrate_existing_carts(apps, schema_editor):
    """Agrupa las líneas antiguas bajo un carro persistente por usuario."""
    RentalCart = apps.get_model('catalog', 'RentalCart')
    RentalCartItem = apps.get_model('catalog', 'RentalCartItem')
    database = schema_editor.connection.alias

    for item in RentalCartItem.objects.using(database).all().iterator():
        cart, _ = RentalCart.objects.using(database).get_or_create(user_id=item.user_id)
        item.cart_id = cart.pk
        item.save(using=database, update_fields=('cart',))


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalog', '0004_rentalcartitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipment',
            name='fixed_deposit',
            field=models.PositiveIntegerField(default=0, verbose_name='Garantía fija'),
        ),
        migrations.AddField(
            model_name='rental',
            name='daily_rate',
            field=models.PositiveIntegerField(default=0, verbose_name='Tarifa diaria acordada'),
        ),
        migrations.AddField(
            model_name='rental',
            name='fixed_deposit',
            field=models.PositiveIntegerField(default=0, verbose_name='Garantía fija acordada'),
        ),
        migrations.AddField(
            model_name='rental',
            name='quantity',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.CreateModel(
            name='RentalCart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='rental_cart', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='rentalcartitem',
            name='cart',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='catalog.rentalcart'),
        ),
        migrations.RunPython(migrate_existing_carts, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='rentalcartitem',
            name='user',
        ),
        migrations.AlterField(
            model_name='rentalcartitem',
            name='cart',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='catalog.rentalcart'),
        ),
        migrations.RunPython(migrate_contract_status_and_prices, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='rental',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendiente'),
                    ('paid', 'Pagado'),
                    ('delivered', 'Entregado'),
                    ('completed', 'Completado'),
                    ('cancelled', 'Cancelado'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
    ]
