import time

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.forms.util import ErrorDict
from django.utils.crypto import salted_hmac, constant_time_compare
from django.utils.hashcompat import sha_constructor
from django.conf import settings

from flag import settings as flag_settings


class SecurityForm(forms.Form):
    """
    Handles the security aspects (anti-spoofing) for comment forms.
    This form is the exact copy of
    django.contrib.comments.forms.CommentSecurityForm, but by copying it we
    avoid including the comments models
    """
    content_type = forms.CharField(widget=forms.HiddenInput)
    object_pk = forms.CharField(widget=forms.HiddenInput)
    timestamp = forms.IntegerField(widget=forms.HiddenInput)
    security_hash = forms.CharField(min_length=40,
                                    max_length=40,
                                    widget=forms.HiddenInput)

    def __init__(self, target_object, data=None, initial=None):
        self.target_object = target_object
        if initial is None:
            initial = {}
        initial.update(self.generate_security_data())
        super(SecurityForm, self).__init__(data=data, initial=initial)

    def security_errors(self):
        """Return just those errors associated with security"""
        errors = ErrorDict()
        for f in ["honeypot", "timestamp", "security_hash"]:
            if f in self.errors:
                errors[f] = self.errors[f]
        return errors

    def clean_security_hash(self):
        """Check the security hash."""
        security_hash_dict = {
            'content_type': self.data.get("content_type", ""),
            'object_pk': self.data.get("object_pk", ""),
            'timestamp': self.data.get("timestamp", ""),
        }
        expected_hash = self.generate_security_hash(**security_hash_dict)
        actual_hash = self.cleaned_data["security_hash"]
        if not constant_time_compare(expected_hash, actual_hash):
            # Fallback to Django 1.2 method for compatibility
            # PendingDeprecationWarning <- here to remind us to remove this
            # fallback in Django 1.5
            expected_hash_old = self._generate_security_hash_old(
                    **security_hash_dict)
            if not constant_time_compare(expected_hash_old, actual_hash):
                raise forms.ValidationError("Security hash check failed.")
        return actual_hash

    def clean_timestamp(self):
        """Make sure the timestamp isn't too far (> 2 hours) in the past."""
        ts = self.cleaned_data["timestamp"]
        if time.time() - ts > (2 * 60 * 60):
            raise forms.ValidationError("Timestamp check failed")
        return ts

    def generate_security_data(self):
        """Generate a dict of security data for "initial" data."""
        timestamp = int(time.time())
        security_dict = {
            'content_type': str(self.target_object._meta),
            'object_pk': str(self.target_object._get_pk_val()),
            'timestamp': str(timestamp),
            'security_hash': self.initial_security_hash(timestamp),
        }
        return security_dict

    def initial_security_hash(self, timestamp):
        """
        Generate the initial security hash from self.content_object
        and a (unix) timestamp.
        """

        initial_security_dict = {
            'content_type': str(self.target_object._meta),
            'object_pk': str(self.target_object._get_pk_val()),
            'timestamp': str(timestamp),
          }
        return self.generate_security_hash(**initial_security_dict)

    def generate_security_hash(self, content_type, object_pk, timestamp):
        """
        Generate a HMAC security hash from the provided info.
        """
        info = (content_type, object_pk, timestamp)
        key_salt = "flag.forms.SecurityForm"
        value = "-".join(info)
        return salted_hmac(key_salt, value).hexdigest()

    def _generate_security_hash_old(self, content_type, object_pk, timestamp):
        """Generate a (SHA1) security hash from the provided info."""
        # Django 1.2 compatibility
        info = (content_type, object_pk, timestamp, settings.SECRET_KEY)
        return sha_constructor("".join(info)).hexdigest()


class FlagForm(SecurityForm):
    """
    The form to be used by users for flagging objects.
    We use SecurityForm to add a security_hash, so the __init__ need
    the object to flag as the first (name `target_object`) parameter
    """
    comment = forms.CharField(widget=forms.Textarea(),
                              label=_(u'Comment'),
                              required=False)

    def clean(self):
        """
        Manage the `ALLOW_COMMENTS` settings
        """
        cleaned_data = super(FlagForm, self).clean()
        content_type = cleaned_data.get('content_type', None)

        if content_type is not None:
            allow_comments = flag_settings.get_for_model(content_type,
                                                         'ALLOW_COMMENTS')
            comment = cleaned_data.get('comment', None)

            if allow_comments and not comment:
                self._errors['comment'] = self.error_class(
                        [_('You must add a comment')])
            elif not allow_comments and comment:
                del cleaned_data['comment']
                raise forms.ValidationError(
                        _('You are not allowed to add a comment'))

        return cleaned_data


class FlagFormWithCreator(FlagForm):
    """
    With this form we can pass a field to get the creator of the
    object to be flagged.
    """
    creator_field = forms.CharField(widget=forms.HiddenInput)


class FlagFormWithStatusMixin(forms.Form):
    """
    This mixin will be used to augment the basic forms
    """
    status = forms.ChoiceField(choices=flag_settings.STATUS)


class FlagFormWithStatus(FlagForm, FlagFormWithStatusMixin):
    """
    A FlagForm with a status field
    """
    pass


class FlagFormWithCreatorAndStatus(FlagFormWithCreator,
                                   FlagFormWithStatusMixin):
    """
    A FlagFormWithCreator with a status field
    """
    pass


def get_default_form(content_object, creator_field=None, with_status=False):
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
        if with_status:
            form_class = FlagFormWithCreatorAndStatus
    elif with_status:
        form_class = FlagFormWithStatus

    return form_class(target_object=content_object, initial=initial)
