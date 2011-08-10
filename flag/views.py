import urlparse

from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import get_model
from django.core.urlresolvers import reverse

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.contrib import messages

from flag.settings import ALLOW_COMMENTS
from flag.forms import FlagForm, FlagFormWithCreator, get_default_form
from flag.models import add_flag, FlagException, FlaggedContent

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

def get_confirm_url_for_object(content_object, creator_field=None):
    """
    Return the url to the flag confirm page for the given object
    """
    url_params = dict(
            app_label = content_object._meta.app_label,
            object_name = content_object._meta.module_name,
            object_id = content_object.pk
        )

    if creator_field:
        url_params['creator_field'] = creator_field

    return reverse('flag_confirm', kwargs=url_params)

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

        else:
            # form not valid, we return to the confirm page

            # try to get something from post params
            object_pk = request.POST['object_pk']
            content_type = get_object_or_404(ContentType, id = int(request.POST['content_type']))

            return confirm(request,
                app_label = content_type.app_label,
                object_name = content_type.model,
                object_id = object_pk,
                creator_field = request.POST.get('creator_field', None),
                form = form
            )

    # try to always redirect to next
    next = get_next(request)
    if next:
        return redirect(next)
    else:
        return Http404


@login_required
def confirm(request, app_label, object_name, object_id, creator_field=None, form=None):
    """
    Display a confirmation page for the flagging, with the comment form
    The template rendered is flag/confirm.html but it can be overrided for
    each model by defining a template flag/confirm_applabel_modelname.html
    """
    # get the object to flag from parameters
    # https://github.com/liberation/django-favorites/blob/master/favorites/utils.py
    model = get_model(app_label, object_name)
    try:
        content_type = ContentType.objects.get_for_model(model)
    except AttributeError: # there no such model
        return HttpResponseBadRequest()
    else:
        try:
            content_object = content_type.get_object_for_this_type(pk=object_id)
        except model.DoesNotExist: # there no such object:
            return HttpResponseBadRequest()

    # where to go when finished, also used on error
    next = get_next(request)

    # get the flagged_content, and test if it can be flagged by the user
    flagged_content = FlaggedContent.objects.get_for_object(content_object)
    try:
        flagged_content.assert_can_be_flagged_by_user(request.user)
    except FlagException, e:
        messages.error(request, unicode(e))
        return redirect(next)

    # define the form
    form = form or get_default_form(content_object, creator_field)

    # ready to render
    context = dict(
        content_object = content_object,
        form = form,
        next = next,
    )

    templates = [
        'flag/confirm_%s_%s.html' % (app_label, object_name),
        'flag/confirm.html'
    ]

    return render(request, templates, context)

