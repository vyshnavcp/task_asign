from django import template

register = template.Library()

@register.filter
def duration_format(value):
    """Converts a timedelta to 'Xh Ym Zs' format."""
    if not value:
        return "-"

    total_seconds = int(value.total_seconds())
    if total_seconds < 0:
        total_seconds = 0

    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60

    return f"{h}h {m:02d}m {s:02d}s"