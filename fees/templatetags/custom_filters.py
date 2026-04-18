from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Safely get value from dictionary using key.
    Works with session dictionaries.
    """

    if dictionary is None:
        return None

    return dictionary.get(str(key))
