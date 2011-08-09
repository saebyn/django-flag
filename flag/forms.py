from django import forms
from flag.settings import ALLOW_COMMENTS

class FlagForm(forms.Form):
    """
    The form to be used by users for flagging objects
    """
    content_type  = forms.CharField(widget=forms.HiddenInput)
    object_pk     = forms.CharField(widget=forms.HiddenInput)

    if ALLOW_COMMENTS:
        comment = forms.CharField(widget=forms.Textarea())

class FlagFormWithCreator(FlagForm):
    """
    With this form we can pass a field to get the creator of the
    object to be flagged.
    """
    creator_field = forms.CharField(widget=forms.HiddenInput)

