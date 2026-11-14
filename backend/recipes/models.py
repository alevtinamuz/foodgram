from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .constants import (
    MAX_AMOUNT, MAX_COOKING_TIME, MIN_AMOUNT, MIN_COOKING_TIME,
)


class Tag(models.Model):
    """
    Модель тега для классификации рецептов (например: Завтрак, Обед).

    Attributes:
        name (CharField): Уникальное текстовое название тега.
        slug (SlugField): Уникальный буквенно-цифровой идентификатор для URL.
    """

    name = models.CharField('Название', max_length=32, unique=True)
    slug = models.SlugField('Слаг', max_length=32, unique=True)

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """
    Модель ингредиента, используемого в рецептах.

    Attributes:
        name (CharField): Название ингредиента (например: Томаты).
        measurement_unit (CharField): Единица измерения (например: г, мл, шт).
    """

    name = models.CharField('Название', max_length=128)
    measurement_unit = models.CharField('Единица измерения', max_length=64)

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'measurement_unit'),
                name='unique_ingredient',
            ),
        ]

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}'


class Recipe(models.Model):
    """
    Модель кулинарного рецепта.

    Attributes:
        author (ForeignKey): Ссылка на создателя рецепта.
        name (CharField): Название рецепта.
        image (ImageField): Изображение готового блюда.
        text (TextField): Текстовое описание процесса приготовления.
        ingredients (ManyToManyField): Связь с моделью Ingredient.
        tags (ManyToManyField): Связь с моделью Tag.
        cooking_time (PositiveSmallIntegerField): Время приготовления в мин.
        pub_date (DateTimeField): Дата и время публикации.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Автор',
    )
    name = models.CharField('Название', max_length=256)
    image = models.ImageField('Картинка', upload_to='recipes/images/')
    text = models.TextField('Описание')
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        verbose_name='Ингредиенты',
    )
    tags = models.ManyToManyField(
        Tag, verbose_name='Теги'
    )
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления (мин)',
        validators=[
            MinValueValidator(MIN_COOKING_TIME),
            MaxValueValidator(MAX_COOKING_TIME),
        ],
    )
    pub_date = models.DateTimeField(
        'Дата публикации', auto_now_add=True, db_index=True
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-pub_date', '-id')
        default_related_name = 'recipes'

    def __str__(self):
        return self.name

    @property
    def short_code(self):
        """Стабильный короткий код: id рецепта в шестнадцатеричном виде."""
        return format(self.pk, 'x')


class RecipeIngredient(models.Model):
    """
    Промежуточная модель связи для фиксации количества ингредиента
    в конкретном рецепте.

    Attributes:
        recipe (ForeignKey): Ссылка на модель рецепта.
        ingredient (ForeignKey): Ссылка на модель ингредиента.
        amount (PositiveSmallIntegerField): Количество ингредиента.
    """

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='ingredient_recipes',
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        'Количество',
        validators=[
            MinValueValidator(MIN_AMOUNT),
            MaxValueValidator(MAX_AMOUNT),
        ],
    )

    class Meta:
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'
        ordering = ('recipe__name', 'ingredient__name')
        constraints = [
            models.UniqueConstraint(
                fields=('recipe', 'ingredient'),
                name='unique_recipe_ingredient',
            ),
        ]

    def __str__(self):
        return f'{self.ingredient.name} — {self.amount}'


class UserRecipeRelation(models.Model):
    """
    Абстрактная модель связи пользователя с рецептом.
    Базовый класс для избранного и списка покупок.

    Attributes:
        user (ForeignKey): Пользователь.
        recipe (ForeignKey): Рецепт.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True
        ordering = ('user__username', 'recipe__name')

    def __str__(self):
        return f'{self.user} → {self.recipe}'


class Favorite(UserRecipeRelation):
    """
    Модель добавления рецепта в «Избранное».

    Attributes:
        user (ForeignKey): Пользователь, добавивший рецепт в избранное.
        recipe (ForeignKey): Рецепт, который добавили в избранное.
    """

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        default_related_name = 'favorites'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'), name='unique_favorite'
            ),
        ]


class ShoppingCart(UserRecipeRelation):
    """
    Модель списка покупок пользователя.

    Attributes:
        user (ForeignKey): Пользователь, формирующий свой список покупок.
        recipe (ForeignKey): Рецепт, добавленный в корзину для расчета
        ингредиентов.
    """

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'
        default_related_name = 'shopping_carts'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'), name='unique_shopping_cart'
            ),
        ]
