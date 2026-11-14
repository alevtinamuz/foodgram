from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q

from .constants import (
    EMAIL_MAX_LENGTH, FIRST_NAME_MAX_LENGTH, LAST_NAME_MAX_LENGTH,
)


class User(AbstractUser):
    """
    Модель пользователя системы с авторизацией по email.

    Attributes:
        email (EmailField): Уникальный адрес электронной почты.
        first_name (CharField): Имя пользователя.
        last_name (CharField): Фамилия пользователя.
        avatar (ImageField): Изображение профиля,в директории 'users/'.
    """

    email = models.EmailField(
        'Адрес электронной почты', max_length=EMAIL_MAX_LENGTH, unique=True
    )
    first_name = models.CharField('Имя', max_length=FIRST_NAME_MAX_LENGTH)
    last_name = models.CharField('Фамилия', max_length=LAST_NAME_MAX_LENGTH)
    avatar = models.ImageField(
        'Аватар', upload_to='users/', null=True, blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username',)

    def __str__(self):
        return self.username


class Subscription(models.Model):
    """
    Модель подписки одного пользователя на другого.

    Attributes:
        user (ForeignKey): Ссылка на пользователя, который оформляет подписку.
        author (ForeignKey): Ссылка на пользователя, на которого подписываются.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Подписчик',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscribers',
        verbose_name='Автор',
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering = ('user__username', 'author__username')
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'author'), name='unique_subscription'
            ),
            models.CheckConstraint(
                condition=~Q(user=F('author')),
                name='prevent_self_subscription',
            ),
        ]

    def __str__(self):
        return f'{self.user} подписан на {self.author}'
