import io
import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag

User = get_user_model()

TEST_PASSWORD = os.getenv('TEST_USERS_PASSWORD', 'foodgram_test_password')

USERS = (
    ('ivan', 'ivan@example.com', 'Иван', 'Иванов'),
    ('maria', 'maria@example.com', 'Мария', 'Макарова'),
    ('petr', 'petr@example.com', 'Пётр', 'Кузнецов'),
)

# (автор, название, теги, минуты, цвет, описание, [(ингредиент, количество)])
RECIPES = (
    (
        'ivan', 'Картофельное пюре', ('lunch', 'dinner'), 40, (230, 190, 90),
        'Отварите картофель, разомните с молоком и маслом, посолите.',
        [
            ('картофель', 800), ('молоко', 150), ('сливочное масло', 50),
            ('соль', 5)
        ]
    ),
    (
        'ivan', 'Сырники', ('breakfast',), 30, (240, 210, 150),
        'Смешайте творог с яйцом и сахаром, сформируйте и обжарьте.',
        [
            ('творог', 500), ('яйца куриные', 100), ('сахар', 40)
        ]
    ),
    (
        'ivan', 'Овсяная каша с бананом', ('breakfast',), 15, (200, 170, 120),
        'Сварите хлопья на молоке, добавьте нарезанный банан.',
        [
            ('овсяные хлопья', 80), ('молоко', 250), ('бананы', 120)
        ]
    ),
    (
        'maria', 'Паста с сыром', ('lunch', 'dinner'), 25, (250, 200, 80),
        'Отварите макароны, посыпьте тёртым сыром и перемешайте.',
        [
            ('макароны', 300), ('сыр', 100), ('соль', 5)
        ]
    ),
    (
        'maria', 'Огуречный салат', ('lunch',), 10, (110, 170, 90),
        'Нарежьте огурцы и помидоры, заправьте сметаной.',
        [
            ('огурцы', 300), ('помидоры', 250), ('сметана', 60)
        ]
    ),
    (
        'maria', 'Рис с морковью', ('dinner',), 35, (230, 150, 60),
        'Обжарьте морковь с луком, добавьте рис и воду, варите до готовности.',
        [
            ('рис', 250), ('морковь', 150), ('лук репчатый', 80)
        ]
    ),
    (
        'petr', 'Куриное филе с чесноком', ('dinner',), 45, (200, 120, 90),
        'Замаринуйте филе с чесноком и запеките в духовке.',
        [
            ('куриное филе', 600), ('чеснок', 20), ('оливковое масло', 20)
        ]
    ),
    (
        'petr',
        'Говядина с картофелем', ('lunch', 'dinner'), 90, (150, 90, 70),
        'Обжарьте говядину, добавьте картофель и тушите до мягкости.',
        [
            ('говядина', 500), ('картофель', 600), ('соль', 5)
        ]
    ),
    (
        'petr', 'Кефирные оладьи', ('breakfast',), 30, (225, 205, 160),
        'Смешайте кефир, яйца и сахар, обжарьте на сковороде.',
        [
            ('кефир', 300), ('яйца куриные', 100), ('сахар', 30)
        ]
    ),
)


def make_image(color, title):
    image = Image.new('RGB', (600, 400), color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 50, 450, 350), outline=(255, 255, 255), width=8)
    draw.text(
        (20, 20), title.encode('ascii', 'ignore').decode() or 'Recipe',
        fill=(255, 255, 255)
    )
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue())


class Command(BaseCommand):
    help = (
        'Создаёт тестовые данные: пользователей, рецепты и (если заданы '
        'ADMIN_EMAIL и ADMIN_PASSWORD) администратора. Запуск идемпотентен.'
    )

    def handle(self, *args, **options):
        self.create_admin()
        users = self.create_users()
        created = self.create_recipes(users)
        self.stdout.write(
            self.style.SUCCESS(
                f'Тестовые данные готовы. Новых рецептов: {created}.'
            )
        )

    def create_admin(self):
        email = os.getenv('ADMIN_EMAIL')
        password = os.getenv('ADMIN_PASSWORD')
        if not email or not password:
            self.stdout.write(
                'ADMIN_EMAIL/ADMIN_PASSWORD не заданы — администратор '
                'не создаётся.'
            )
            return
        if User.objects.filter(email=email).exists():
            return
        User.objects.create_superuser(
            username=os.getenv('ADMIN_USERNAME', 'admin'),
            email=email,
            password=password,
            first_name='Админ',
            last_name='Фудграма',
        )
        self.stdout.write(f'Создан администратор {email}')

    def create_users(self):
        users = {}
        for username, email, first_name, last_name in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                },
            )
            if created:
                user.set_password(TEST_PASSWORD)
                user.save()
            users[username] = user
        return users

    def create_recipes(self, users):
        created_count = 0
        tags = {tag.slug: tag for tag in Tag.objects.all()}
        for (
            username, name, tag_slugs, minutes, color, text, ingredients
        ) in RECIPES:
            if Recipe.objects.filter(name=name).exists():
                continue
            recipe = Recipe(
                author=users[username], name=name, text=text,
                cooking_time=minutes,
            )
            recipe.image.save(
                f'{username}_{created_count}.png',
                make_image(color, name), save=False
            )
            recipe.save()
            recipe.tags.set([tags[slug] for slug in tag_slugs])
            for ingredient_name, amount in ingredients:
                ingredient = Ingredient.objects.filter(
                    name=ingredient_name
                ).first()
                if ingredient is None:
                    continue
                RecipeIngredient.objects.create(
                    recipe=recipe, ingredient=ingredient, amount=amount
                )
            created_count += 1
        return created_count
