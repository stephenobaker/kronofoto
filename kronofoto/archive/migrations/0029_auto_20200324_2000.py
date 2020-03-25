# Generated by Django 2.2.10 on 2020-03-24 20:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0028_auto_20200320_0454'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.CharField(max_length=64)),
            ],
        ),
        migrations.AlterField(
            model_name='collection',
            name='total_photos',
            field=models.SmallIntegerField(default=0, editable=False, verbose_name='photos'),
        ),
        migrations.AddField(
            model_name='photo',
            name='acceptedtags',
            field=models.ManyToManyField(related_name='acceptedtags', to='archive.Tag'),
        ),
        migrations.AddField(
            model_name='photo',
            name='proposedtags',
            field=models.ManyToManyField(related_name='proposedtags', to='archive.Tag'),
        ),
    ]
