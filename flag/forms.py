from django import forms
from django.utils.translation import ugettext_lazy as _
from flag.settings import ALLOW_COMMENTS
from django.contrib.comments.forms import CommentSecurityForm

class FlagForm(CommentSecurityForm):
    """
    The form to be used by users for flagging objects.
    We use CommentSecurityForm to add a security_hash, so the __init__ need
    the object to flag as the first (name `target_object`) parameter
    """
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
    # initial data for the form (content_type and object_pk automaticaly set)
    initial = {}

    # by default, a class without creator_field
    form_class = FlagForm

    # we have a creator field ? add it to a better form class
    if creator_field:
        form_class = FlagFormWithCreator
        initial['creator_field'] = creator_field

    return form_class(target_object=content_object, initial=initial)

