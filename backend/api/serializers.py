import base64
import binascii
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers

from recipes.constants import (
    MAX_AMOUNT, MAX_COOKING_TIME, MIN_AMOUNT, MIN_COOKING_TIME,
)
from recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient
from recipes.models import ShoppingCart, Tag
from users.models import Subscription

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """
    Поле для сериализации и десериализации изображений в формате Base64.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                header, encoded = data.split(';base64,', 1)
                extension = header.split('/')[-1]
                content = base64.b64decode(encoded)
            except (ValueError, binascii.Error):
                raise serializers.ValidationError(
                    'Некорректное изображение.'
                )
            data = ContentFile(content, name=f'{uuid.uuid4()}.{extension}')
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор используется для безопасного отображения информации
    о пользователях, включая проверку состояния подписки текущего
    авторизованного пользователя на просматриваемого автора.

    Attributes:
        is_subscribed (SerializerMethodField): Флаг подписки пользователя.
    """

    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'avatar',
        )
        read_only_fields = fields

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        # Один запрос на весь ответ: id авторов, на которых подписан юзер.
        subscribed_ids = self.context.get('subscribed_ids')
        if subscribed_ids is None:
            subscribed_ids = set(
                Subscription.objects.filter(
                    user=request.user
                ).values_list('author_id', flat=True)
            )
            self.context['subscribed_ids'] = subscribed_ids
        return obj.id in subscribed_ids


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации новых пользователей в системе.

    Attributes:
        password (CharField): Поле пароля, доступное только для записи.
    """

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name', 'password',
        )
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate(self, attrs):
        candidate = User(
            **{key: value for key, value in attrs.items() if key != 'password'}
        )
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {'password': list(error.messages)}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class SetPasswordSerializer(serializers.Serializer):
    """
    Сериализатор для изменения текущего пароля пользователя.
    """

    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Неверный текущий пароль.')
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages))
        return value


class AvatarSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления аватара пользователя.

    Attributes:
        avatar (Base64ImageField): Поле аватара,
        принимающее изображение в формате Base64.
    """

    avatar = Base64ImageField(required=True, allow_null=False)

    class Meta:
        model = User
        fields = ('avatar',)


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения тегов рецептов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор рецепта."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = fields


class UserWithRecipesSerializer(UserSerializer):
    """
    Расширенный сериализатор профиля пользователя,
    включающий список его рецептов.

    Attributes:
        recipes (SerializerMethodField): Список рецептов пользователя.
        recipes_count (SerializerMethodField): Общее число созданных рецептов.
    """

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')
        read_only_fields = fields

    def get_recipes(self, obj):
        recipes = obj.recipes.all()
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        if limit and limit.isdigit():
            recipes = recipes[:int(limit)]
        return RecipeMinifiedSerializer(
            recipes, many=True, context=self.context
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детального отображения ингредиента внутри рецепта.
    """

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    """
    Сериализатор для полного отображения информации о рецепте.

    Attributes:
        tags (TagSerializer):
            Полная информация о прикрепленных тегах.
        author (UserSerializer):
            Данные профиля создателя рецепта.
        ingredients (RecipeIngredientReadSerializer):
            Развернутый список ингредиентов.
        is_favorited (SerializerMethodField):
            Флаг нахождения рецепта в избранном.
        is_in_shopping_cart (SerializerMethodField):
            Флаг нахождения рецепта в корзине.
    """
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source='recipe_ingredients', many=True, read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time',
        )
        read_only_fields = fields

    def _check_relation(self, obj, attr, model):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        annotated = getattr(obj, attr, None)
        if annotated is not None:
            return annotated
        return model.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_favorited(self, obj):
        return self._check_relation(obj, 'is_favorited', Favorite)

    def get_is_in_shopping_cart(self, obj):
        return self._check_relation(obj, 'is_in_shopping_cart', ShoppingCart)


class RecipeIngredientWriteSerializer(serializers.Serializer):
    """
    Вложенный сериализатор для валидации ингредиентов при записи рецепта.

    Attributes:
        id (PrimaryKeyRelatedField): ID существующего в системе ингредиента.
        amount (IntegerField): Количество.
    """

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(
        min_value=MIN_AMOUNT, max_value=MAX_AMOUNT
    )


class RecipeWriteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания и обновления рецептов.

    Обрабатывает вложенную запись тегов, ингредиентов
    и декодирование изображения из Base64 строки.
    Валидирует время приготовления.

    Attributes:
        ingredients (RecipeIngredientWriteSerializer):
            Список добавляемых ингредиентов.
        tags (PrimaryKeyRelatedField):
            Список ID прикрепляемых тегов.
        image (Base64ImageField):
            Изображение блюда, закодированное в Base64.
        cooking_time (IntegerField):
            Время готовки.
    """

    ingredients = RecipeIngredientWriteSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME, max_value=MAX_COOKING_TIME
    )

    class Meta:
        model = Recipe
        fields = (
            'id', 'ingredients', 'tags', 'image', 'name', 'text',
            'cooking_time',
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                'Нужно указать хотя бы один ингредиент.'
            )
        for item in value:
            # При PATCH вложенные сериализаторы работают в partial-режиме.
            if 'id' not in item or 'amount' not in item:
                raise serializers.ValidationError(
                    'У каждого ингредиента должны быть id и amount.'
                )
        ids = [item['id'].id for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.'
            )
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError(
                'Нужно указать хотя бы один тег.'
            )
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Теги не должны повторяться.')
        return value

    def validate(self, attrs):
        if self.instance is not None:
            errors = {
                field: ['Обязательное поле.']
                for field in ('ingredients', 'tags') if field not in attrs
            }
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def _save_ingredients(recipe, ingredients):
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe, ingredient=item['id'], amount=item['amount']
            )
            for item in ingredients
        ])

    @transaction.atomic
    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self._save_ingredients(recipe, ingredients)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        instance = super().update(instance, validated_data)
        instance.tags.set(tags)
        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._save_ingredients(instance, ingredients)
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data
