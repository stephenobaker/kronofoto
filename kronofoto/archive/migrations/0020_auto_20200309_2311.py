# Generated by Django 2.2.10 on 2020-03-09 23:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0019_auto_20200309_2307'),
    ]

    operations = [
        migrations.RenameField(
            model_name='photovote',
            old_name='user',
            new_name='voter',
        ),
    ]