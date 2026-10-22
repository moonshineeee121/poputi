from django import template

register = template.Library()


@register.filter
def rubles(value):
    if value is None:
        return "—"
    number = f"{value:,.0f}".replace(",", "\u00a0")
    return f"{number} ₽"


@register.simple_tag(takes_context=True)
def query_update(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"?{encoded}#tours" if encoded else "/#tours"
