# Generated by Django 3.2.18 on 2023-02-23 05:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0142_resource_universal_field'),
    ]

    operations = [
        migrations.AlterField(
            model_name='day',
            name='closed',
            field=models.BooleanField(default=False, null=True, verbose_name='Closed'),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='universal_data',
            field=models.JSONField(blank=True, null=True, verbose_name='Data'),
        ),
        migrations.AlterField(
            model_name='resourceuniversalfield',
            name='data',
            field=models.JSONField(blank=True, null=True, verbose_name='Data'),
        ),
        migrations.AlterField(
            model_name='universalformfieldtype',
            name='type',
            field=models.CharField(choices=[('Select', 'Select')], max_length=200, verbose_name='Type'),
        ),
    ]
