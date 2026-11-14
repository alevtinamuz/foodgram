from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Sum
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag,
)
from users.models import Subscription

from .filters import IngredientFilter, RecipeFilter
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    AvatarSerializer, FavoriteSerializer, IngredientSerializer,
    RecipeReadSerializer, RecipeWriteSerializer, SetPasswordSerializer,
    ShoppingCartSerializer, SubscriptionSerializer, TagSerializer,
    UserCreateSerializer, UserSerializer, UserWithRecipesSerializer,
)

User = get_user_model()


def delete_relation(relation, related_model, pk, message):
    """
    Удаляет связь (подписку, избранное, покупку).
    204 — удалено; 404 — связанного объекта нет вовсе; 400 — связи не было.
    """
    deleted, _ = relation.delete()
    if deleted:
        return Response(status=status.HTTP_204_NO_CONTENT)
    if not related_model.objects.filter(pk=pk).exists():
        raise NotFound
    return Response({'errors': message}, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Вьюсет для управления пользователями и их подписками."""

    queryset = User.objects.all()
    lookup_value_regex = r'\d+'

    def get_queryset(self):
        if self.action in ('subscriptions', 'subscribe'):
            return User.objects.annotate(
                recipes_count=Count('recipes', distinct=True)
            )
        return super().get_queryset()

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'create'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action == 'set_password':
            return SetPasswordSerializer
        if self.action == 'subscriptions':
            return UserWithRecipesSerializer
        return UserSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def set_password(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar')
    def avatar(self, request):
        user = request.user
        if request.method == 'PUT':
            serializer = AvatarSerializer(
                user, data=request.data, context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({'avatar': serializer.data['avatar']})
        if user.avatar:
            user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        authors = self.get_queryset().filter(subscribers__user=request.user)
        page = self.paginate_queryset(authors)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, pk=None):
        author = get_object_or_404(self.get_queryset(), pk=pk)
        context = self.get_serializer_context()
        serializer = SubscriptionSerializer(
            data={'author': author.pk}, context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            UserWithRecipesSerializer(author, context=context).data,
            status=status.HTTP_201_CREATED,
        )

    @subscribe.mapping.delete
    def unsubscribe(self, request, pk=None):
        return delete_relation(
            Subscription.objects.filter(user=request.user, author_id=pk),
            User, pk, 'Вы не подписаны на этого автора.',
        )


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра доступных тегов."""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра и поиска ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет для управления рецептами."""

    permission_classes = (IsAuthorOrReadOnly,)
    filterset_class = RecipeFilter
    http_method_names = ('get', 'post', 'patch', 'delete')
    lookup_value_regex = r'\d+'

    def get_queryset(self):
        queryset = Recipe.objects.select_related('author').prefetch_related(
            'tags', 'recipe_ingredients__ingredient'
        )
        user = self.request.user
        if user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=user, recipe=OuterRef('pk')
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(
                        user=user, recipe=OuterRef('pk')
                    )
                ),
            )
        return queryset

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update', 'update'):
            return RecipeWriteSerializer
        return RecipeReadSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True, methods=['get'], url_path='get-link',
        permission_classes=[AllowAny],
    )
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        link = request.build_absolute_uri(f'/s/{recipe.short_code}')
        return Response({'short-link': link})

    def _add_relation(self, request, pk, serializer_class):
        serializer = serializer_class(
            data={'recipe': pk}, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=['post'], permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        return self._add_relation(request, pk, FavoriteSerializer)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return delete_relation(
            Favorite.objects.filter(user=request.user, recipe_id=pk),
            Recipe, pk, 'Рецепта не было в избранном.',
        )

    @action(
        detail=True, methods=['post'], permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        return self._add_relation(request, pk, ShoppingCartSerializer)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return delete_relation(
            ShoppingCart.objects.filter(user=request.user, recipe_id=pk),
            Recipe, pk, 'Рецепта не было в списке покупок.',
        )

    @action(
        detail=False, methods=['get'], permission_classes=[IsAuthenticated],
    )
    def download_shopping_cart(self, request):
        ingredients = RecipeIngredient.objects.filter(
            recipe__shopping_carts__user=request.user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(total=Sum('amount')).order_by('ingredient__name')
        recipe_names = Recipe.objects.filter(
            shopping_carts__user=request.user
        ).values_list('name', flat=True)

        lines = [
            f'Список покупок Foodgram от {date.today():%d.%m.%Y}',
            '',
            'Ингредиенты:',
        ]
        lines += [
            f'{item["ingredient__name"].capitalize()} '
            f'({item["ingredient__measurement_unit"]}) — {item["total"]}'
            for item in ingredients
        ]
        lines += ['', 'Рецепты:']
        lines += [f'- {name}' for name in recipe_names]

        response = HttpResponse(
            '\n'.join(lines) + '\n',
            content_type='text/plain; charset=utf-8',
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
