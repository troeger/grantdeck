from decimal import Decimal

from django import template


register = template.Library()


def _decimal_text(value):
    text = f'{value:.1f}'.rstrip('0').rstrip('.')
    return text.replace('.', ',')


@register.filter
def token_number(value):
    """Format token counts with grouped and compact German-style values."""
    if value is None:
        return 'Unavailable'

    number = Decimal(str(value))
    absolute = abs(number)
    if absolute >= Decimal('1000000000000'):
        return f'{_decimal_text(number / Decimal("1000000000000"))} Trillion'
    if absolute >= Decimal('1000000000'):
        return f'{_decimal_text(number / Decimal("1000000000"))} Billion'
    if absolute >= Decimal('1000000'):
        return f'{_decimal_text(number / Decimal("1000000"))} Million'

    return f'{int(number):,}'.replace(',', '.')


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    return mapping.get(key, [])
