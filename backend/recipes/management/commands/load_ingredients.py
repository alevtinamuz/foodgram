import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загружает ингредиенты из JSON-файла.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default=str(settings.BASE_DIR / 'data' / 'ingredients.json'),
            help='Путь к файлу ingredients.json',
        )

    def handle(self, *args, **options):
        try:
            with open(options['path'], encoding='utf-8') as file:
                items = json.load(file)
        except (OSError, ValueError) as error:
            raise CommandError(f'Не удалось прочитать файл: {error}')

        before = Ingredient.objects.count()
        Ingredient.objects.bulk_create(
            [
                Ingredient(
                    name=item['name'],
                    measurement_unit=item['measurement_unit'],
                )
                for item in items
            ],
            ignore_conflicts=True,
        )
        added = Ingredient.objects.count() - before
        self.stdout.write(
            self.style.SUCCESS(f'Ингредиентов добавлено: {added}')
        )
