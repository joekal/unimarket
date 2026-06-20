from django import template

register = template.Library()


@register.filter
def initial(value):
    """Return the first letter (uppercase) for a user/profile/name.

    Accepts:
    - a string (name)
    - a User or StudentProfile-like object (will try to extract a readable name)
    """
    if not value:
        return ""

    # If passed a profile-like or user-like object, try to extract a name
    name = None
    try:
        # StudentProfile has .user
        if hasattr(value, 'user'):
            user = value.user
            # try get_full_name() if present
            if hasattr(user, 'get_full_name'):
                name = user.get_full_name() or user.username
            else:
                name = getattr(user, 'username', '')
        # User-like object
        elif hasattr(value, 'get_full_name'):
            name = value.get_full_name() or getattr(value, 'username', '')
        else:
            name = str(value)
    except Exception:
        name = str(value)

    name = (name or '').strip()
    if not name:
        return ""

    # First letter of first word
    try:
        first = name.split()[0][0]
        return first.upper()
    except Exception:
        return name[0].upper()
