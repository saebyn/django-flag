from django import template

from django.contrib.contenttypes.models import ContentType
from flag.forms import FlagForm, FlagFormWithCreator
from flag.views import get_next
from flag.models import FlaggedContent

register = template.Library()


@register.inclusion_tag("flag/flag_form.html", takes_context=True)
def flag(context, content_object, creator_field=None):

    request = context['request']

    # get the content type for the given object
    content_type = ContentType.objects.get(
        app_label = content_object._meta.app_label,
        model = content_object._meta.module_name
    )

    # initial data for the form
    initial=dict(
        content_type = content_type.id,
        object_pk = content_object.pk,
    )

    # by default, a class without creator_field
    form_class = FlagForm

    # we have a creator field ? add it to a better form class
    if creator_field:
        form_class = FlagFormWithCreator
        initial['creator_field'] = creator_field

    form = form_class(initial=initial)

    return dict(
            form = form,
            next = get_next(request)
        )

@register.filter
def flag_count(content_object):
    """
    This filter will return the number of flags for the given object
    Usage : {{ some_object|flag_count }}
    """
    try:
        return FlaggedContent.objects.get_for_object(content_object).count
    except:
        return 0

@register.filter
def flag_status(content_object):
    """
    This filter will return the flag's status for the given object
    Usage : {{ some_object|flag_status }}
    """
    try:
        return FlaggedContent.objects.get_for_object(content_object).status
    except:
        return None

@register.filter
def can_be_flagged_by(content_object, user):
    """
    This filter will return True if the given user can flag the given object.
    We check that the user is authenticated, but also that the
    LIMIT_SAME_OBJECT_FOR_USER is not raised
    """
    if not (user and user.is_active and user.is_authenticated()):
        return False
    try:
        flagged_content = FlaggedContent.objects.get_for_object(content_object)
        return flagged_content.can_be_flagged_by_user(user)
    except:
        return False
