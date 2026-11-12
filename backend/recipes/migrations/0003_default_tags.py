from django.db import migrations

DEFAULT_TAGS = (
    ('Завтрак', 'breakfast'),
    ('Обед', 'lunch'),
    ('Ужин', 'dinner'),
)


def create_tags(apps, schema_editor):
    Tag = apps.get_model('recipes', 'Tag')
    for name, slug in DEFAULT_TAGS:
        Tag.objects.get_or_create(slug=slug, defaults={'name': name})


def remove_tags(apps, schema_editor):
    Tag = apps.get_model('recipes', 'Tag')
    Tag.objects.filter(slug__in=[slug for _, slug in DEFAULT_TAGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(create_tags, remove_tags),
    ]