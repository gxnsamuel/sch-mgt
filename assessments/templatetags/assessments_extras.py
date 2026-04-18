from django import template
from django.utils.datastructures import MultiValueDictKeyError

register = template.Library()

@register.filter
def getitem(obj, key):
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError, MultiValueDictKeyError):
        return None

@register.simple_tag
def dict_get(obj, prefix, suffix):
    key = str(prefix) + str(suffix).lower()
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError, MultiValueDictKeyError):
        return None

@register.filter
def is_in(value, collection):
    return value in collection