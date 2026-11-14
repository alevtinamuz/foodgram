from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count

from .models import Subscription, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'id', 'username', 'email', 'first_name', 'last_name', 'is_staff',
        'subscribers_count', 'recipes_count',
    )
    search_fields = ('email', 'username')
    ordering = ('username',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Аватар', {'fields': ('avatar',)}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email', 'username', 'first_name', 'last_name',
                    'password1', 'password2',
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _subscribers_count=Count('subscribers', distinct=True),
            _recipes_count=Count('recipes', distinct=True),
        )

    @admin.display(description='Подписчиков', ordering='_subscribers_count')
    def subscribers_count(self, obj):
        return obj._subscribers_count

    @admin.display(description='Рецептов', ordering='_recipes_count')
    def recipes_count(self, obj):
        return obj._recipes_count


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'author')
    search_fields = ('user__username', 'user__email', 'author__username')
