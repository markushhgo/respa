# Generated by Django 3.2.23 on 2024-01-30 14:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0152_create_resource_publish_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resourceequipment',
            name='data',
            field=models.JSONField(blank=True, null=True, verbose_name='Data'),
        ),
    ]
