# Generated by Django 5.1.4 on 2025-01-15 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='created_at',
            new_name='createdAt',
        ),
        migrations.RenameField(
            model_name='user',
            old_name='is_deleted',
            new_name='isDeleted',
        ),
        migrations.RenameField(
            model_name='user',
            old_name='updated_at',
            new_name='updatedAt',
        ),
        migrations.RenameField(
            model_name='user',
            old_name='user_id',
            new_name='userId',
        ),
        migrations.AddField(
            model_name='user',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last login'),
        ),
        migrations.AlterField(
            model_name='user',
            name='password',
            field=models.CharField(max_length=128),
        ),
    ]
