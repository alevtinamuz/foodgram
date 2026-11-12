from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Recipe


def short_link_redirect(request, code):
    """Перенаправляет пользователя с короткого URL на полную страницу рецепта.

    Принимает шестнадцатеричный код, конвертирует его в целочисленный
    первичный ключ рецепта и выполняет HTTP-перенаправление.
    """

    try:
        recipe_id = int(code, 16)
    except ValueError:
        raise Http404
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    return HttpResponseRedirect(f'/recipes/{recipe.pk}')
