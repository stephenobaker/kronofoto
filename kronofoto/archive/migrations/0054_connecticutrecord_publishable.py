# Generated by Django 3.2.17 on 2023-03-14 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0053_auto_20230309_2352'),
    ]

    operations = [
        migrations.AddField(
            model_name='connecticutrecord',
            name='publishable',
            field=models.BooleanField(default=False),
        ),
    ]
