from django import template

from django.contrib.contenttypes.models import ContentType
from flag.forms import FlagForm, FlagFormWithCreator
from flag.views import get_next


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
