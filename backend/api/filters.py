from django_filters import rest_framework as filters

from recipes.models import Ingredient, Recipe, Tag


class IngredientFilter(filters.FilterSet):
    """Поиск ингредиентов по началу названия без учёта регистра."""

    name = filters.CharFilter(field_name='name', lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name',)


class RecipeFilter(filters.FilterSet):
    """
    Фильтр для поиска и отбора рецептов.

    Позволяет фильтровать рецепты по нескольким тегам,
    конкретному автору, а также отбирать рецепты,
    добавленные текущим пользователем в избранное или в список покупок.

    Attributes:
        tags (ModelMultipleChoiceFilter):
            Фильтрация по слагу одного или нескольких тегов.
        author (NumberFilter):
            Фильтрация рецептов по числовому ID автора.
        is_favorited (NumberFilter):
            Флаг-фильтр для отбора рецептов из «Избранного».
        is_in_shopping_cart (NumberFilter):
            Флаг-фильтр для отбора рецептов из «Списка покупок».
    """

    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )
    author = filters.NumberFilter(field_name='author_id')
    is_favorited = filters.NumberFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.NumberFilter(
        method='filter_is_in_shopping_cart'
    )

    class Meta:
        model = Recipe
        fields = ('tags', 'author', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if value != 1:
            return queryset
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(favorites__user=user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value != 1:
            return queryset
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(shopping_carts__user=user)
