# Generated by Django 2.2.10 on 2021-01-11 22:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0013_auto_20210111_2053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='csvrecord',
            name='circa',
            field=models.BooleanField(null=True),
        ),
    ]
