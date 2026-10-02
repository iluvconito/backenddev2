from django.db import migrations, models
import django.db.models.deletion


def create_sample_inventory(apps, schema_editor):
    Branch = apps.get_model('catalog', 'Branch')
    Equipment = apps.get_model('catalog', 'Equipment')
    EquipmentStock = apps.get_model('catalog', 'EquipmentStock')
    database = schema_editor.connection.alias

    EquipmentStock.objects.using(database).bulk_create([
        EquipmentStock(equipment_id=equipment.pk, branch_id=branch.pk, quantity=1)
        for equipment in Equipment.objects.using(database).all()
        for branch in Branch.objects.using(database).all()
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_fix_backhoe_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquipmentStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=0, verbose_name='Cantidad de unidades')),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equipment_stock', to='catalog.branch')),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_by_branch', to='catalog.equipment')),
            ],
            options={
                'verbose_name': 'inventario de maquinaria',
                'verbose_name_plural': 'inventario de maquinaria',
                'ordering': ['branch__name', 'equipment__name'],
            },
        ),
        migrations.AddConstraint(
            model_name='equipmentstock',
            constraint=models.UniqueConstraint(fields=('equipment', 'branch'), name='unique_equipment_stock_per_branch'),
        ),
        migrations.RunPython(create_sample_inventory, migrations.RunPython.noop),
    ]
