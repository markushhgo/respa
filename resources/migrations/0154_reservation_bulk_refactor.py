# Generated by Django 3.2.23 on 2024-02-22 06:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0153_change_resource_equipment_data_field_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reservationbulk',
            name='bucket',
        ),
        migrations.AddField(
            model_name='reservation',
            name='bulk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reservations', to='resources.reservationbulk'),
        ),
    ]
