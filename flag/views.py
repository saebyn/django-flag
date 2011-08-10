import urlparse

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.contrib import messages

from flag.settings import ALLOW_COMMENTS
from flag.forms import FlagForm, FlagFormWithCreator
from flag.models import add_flag, FlagException

def _validate_next_parameter(request, next):
    """
    Validate the next url and return the path if ok, else None
    """
    parsed = urlparse.urlparse(next)
    if parsed and parsed.path:
        return parsed.path
    return None

def get_next(request):
    """
    Find the next url to redirect the user to
    Taken from https://github.com/ericflo/django-avatar/blob/master/avatar/views.py
    """
    next = request.POST.get('next', request.GET.get('next', request.META.get('HTTP_REFERER', None)))
    if next:
        next = _validate_next_parameter(request, next)
    if not next:
        next = request.path
    return next

@login_required
def flag(request):
    """
    Validate the form and create the flag.
    In all cases, redirect to the `next` parameter.
    """

    if request.method == 'POST':

        # get the form class regrding if we have a creator_field
        form_class = FlagForm
        if 'creator_field' in request.POST:
            form_class = FlagFormWithCreator

        form = form_class(request.POST)
        if form.is_valid():

            # get object to flag
            object_pk = form.cleaned_data['object_pk']
            content_type = get_object_or_404(ContentType, id = int(form.cleaned_data['content_type']))

            # manage creator
            creator = None
            if form_class == FlagFormWithCreator:
                creator_field = form.cleaned_data['creator_field']
                if creator_field:
                    creator = getattr(
                            content_type.get_object_for_this_type(id=object_pk),
                            creator_field,
                            None
                        )

            # manage comment
            if ALLOW_COMMENTS:
                comment = form.cleaned_data['comment']
            else:
                comment = None

            # add the flag, but check the user can do it
            try:
                add_flag(request.user, content_type, object_pk, creator, comment)
            except FlagException, e:
                messages.error(request, unicode(e))
            else:
                messages.success(request, _("You have added a flag. A moderator will review your "
                        "submission shortly."))

    # try to always redirect to next
    next = get_next(request)
    if next:
        return redirect(next)
    else:
        return Http404
