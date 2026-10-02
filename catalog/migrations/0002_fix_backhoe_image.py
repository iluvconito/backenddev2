from django.db import migrations


OLD_IMAGE_URL = 'https://images.unsplash.com/photo-1504307651254-35680f356e8d?auto=format&fit=crop&w=1200&q=82'
NEW_IMAGE_URL = 'https://images.unsplash.com/photo-1580901368919-7738efb0f87e?auto=format&fit=crop&w=1200&q=82'


def update_backhoe_image(apps, schema_editor):
    Equipment = apps.get_model('catalog', 'Equipment')
    Equipment.objects.using(schema_editor.connection.alias).filter(
        name='Retroexcavadora 4x4',
        image_url=OLD_IMAGE_URL,
    ).update(image_url=NEW_IMAGE_URL)


def restore_backhoe_image(apps, schema_editor):
    Equipment = apps.get_model('catalog', 'Equipment')
    Equipment.objects.using(schema_editor.connection.alias).filter(
        name='Retroexcavadora 4x4',
        image_url=NEW_IMAGE_URL,
    ).update(image_url=OLD_IMAGE_URL)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_backhoe_image, restore_backhoe_image),
    ]
