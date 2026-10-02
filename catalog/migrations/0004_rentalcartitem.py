from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalog', '0003_equipmentstock'),
    ]

    operations = [
        migrations.CreateModel(
            name='RentalCartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cart_items', to='catalog.branch')),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to='catalog.equipment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rental_cart_items', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='rentalcartitem',
            constraint=models.CheckConstraint(condition=models.Q(('end_date__gte', models.F('start_date'))), name='cart_end_on_or_after_start'),
        ),
        migrations.AddConstraint(
            model_name='rentalcartitem',
            constraint=models.CheckConstraint(condition=models.Q(('quantity__gte', 1)), name='cart_quantity_at_least_one'),
        ),
    ]
