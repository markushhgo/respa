# Generated by Django 2.2.28 on 2022-11-22 11:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0013_auto_20220824_0932'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerGroupLoginMethod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('login_method_id', models.CharField(help_text='Login method id or amr given by authentication service such as Tunnistamo', max_length=200, unique=True, verbose_name='Login method id')),
            ],
            options={
                'verbose_name': 'Customer group login method',
                'verbose_name_plural': 'Customer group login methods',
            },
        ),
        migrations.AddField(
            model_name='customergroup',
            name='only_for_login_methods',
            field=models.ManyToManyField(blank=True, help_text='Having none selected means that all login methods are allowed.', related_name='customer_groups', to='payments.CustomerGroupLoginMethod', verbose_name='Only for login methods'),
        ),
    ]
