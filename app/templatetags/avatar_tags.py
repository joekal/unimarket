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


@register.filter
def media_or_default(image_field, default_url='/static/img/bg-img/10.jpg'):
    """Return the image URL, or a safe fallback URL when the file is missing."""
    if not image_field:
        return default_url

    try:
        if hasattr(image_field, 'storage') and hasattr(image_field, 'name') and image_field.name:
            if image_field.storage.exists(image_field.name):
                return image_field.url
        if hasattr(image_field, 'url'):
            return image_field.url
    except Exception:
        pass

    return default_url
