from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from flag.settings import ALLOW_COMMENTS

class FlagForm(forms.Form):
    """
    The form to be used by users for flagging objects
    """
    content_type  = forms.CharField(widget=forms.HiddenInput)
    object_pk     = forms.CharField(widget=forms.HiddenInput)

    if ALLOW_COMMENTS:
        comment = forms.CharField(widget=forms.Textarea(), label=_(u'Comment'))

class FlagFormWithCreator(FlagForm):
    """
    With this form we can pass a field to get the creator of the
    object to be flagged.
    """
    creator_field = forms.CharField(widget=forms.HiddenInput)

def get_default_form(content_object, creator_field=None):
    """
    Helper to get a form from the right class, with initial parameters set
    """
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

    return form_class(initial=initial)

