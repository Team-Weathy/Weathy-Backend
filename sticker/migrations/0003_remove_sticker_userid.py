# Generated by Django 5.1.4 on 2025-01-15 16:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sticker', '0002_sticker_userid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sticker',
            name='userId',
        ),
    ]
