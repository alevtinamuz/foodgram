from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    - Безопасные методы (GET, HEAD, OPTIONS) разрешены всем пользователям.
    - Создание и изменение контента требует аутентификации.
    - Изменение и удаление конкретного объекта разрешено только владельцу.
    """

    def has_permission(self, request, view):
        return (
            request.method in permissions.SAFE_METHODS
            or request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        return (
            request.method in permissions.SAFE_METHODS
            or obj.author == request.user
        )
