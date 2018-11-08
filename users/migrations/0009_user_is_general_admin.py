# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-09-17 09:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0008_support_for_django_2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(
                default=False, verbose_name="staff status",
                help_text=(
                    "Designates whether the user can log into "
                    "Django Admin or Respa Admin sites."),
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='is_general_admin',
            field=models.BooleanField(
                default=False, verbose_name='general administrator status',
                help_text=(
                    "Designates whether the user is a General Administrator "
                    "with special permissions to many objects within Respa. "
                    "This is almost as powerful as superuser."),
            ),
        ),
    ]
