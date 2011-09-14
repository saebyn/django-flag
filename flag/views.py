import urlparse

from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.db.models import get_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.contrib import messages
from django.utils.html import escape

from django.conf import settings

from flag import settings as flag_settings
from flag.forms import FlagForm, FlagFormWithCreator, get_default_form
from flag.models import FlaggedContent, FlagInstance
from flag.exceptions import FlagException


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
    Taken from
    https://github.com/ericflo/django-avatar/blob/master/avatar/views.py
    """
    next = getattr(request, 'POST', {}).get('next',
                getattr(request, 'GET', {}).get('next',
                    getattr(request, 'META', {}).get('HTTP_REFERER', None)))
    if next:
        next = _validate_next_parameter(request, next)
    if not next:
        next = getattr(request, 'path', None)
    return next


class FlagBadRequest(HttpResponseBadRequest):
    """
    (based on django.contrib.comments.views.comments.CommentPostBadRequest)
    Response returned when a flag get/post is invalid. If ``DEBUG`` is on a
    nice-ish error message will be displayed (for debugging purposes), but in
    production mode a simple opaque 400 page will be displayed.
    """
    def __init__(self, why):
        super(FlagBadRequest, self).__init__()
        if settings.DEBUG:
            self.content = render_to_string("flag/400-debug.html",
                                            {"why": why})


def get_confirm_url_for_object(content_object, creator_field=None):
    """
    Return the url to the flag confirm page for the given object
    TODO : raise if the object cannot be flaaged ?
    """
    url_params = dict(
            app_label=content_object._meta.app_label,
            object_name=content_object._meta.module_name,
            object_id=content_object.pk)

    if creator_field:
        url_params['creator_field'] = creator_field

    return reverse('flag_confirm', kwargs=url_params)


def get_content_object(ctype, object_pk):
    """
    Given a content type ("app_name.model_name") and an object's pk, try to
    return the mathcing object
    (based on django.contrib.comments.views.comments.post_comment)
    """
    if ctype is None or object_pk is None:
        return FlagBadRequest("Missing content_type or object_pk field.")
    try:
        model = get_model(*ctype.split(".", 1))
        FlaggedContent.objects.assert_model_can_be_flagged(model)
        return model._default_manager.get(pk=object_pk)
    except TypeError:
        return FlagBadRequest(
            "Invalid content_type value: %r" % escape(ctype))
    except AttributeError:
        return FlagBadRequest(
            "The given content-type %r does not resolve to a valid model." % \
                escape(ctype))
    except ObjectDoesNotExist:
        return FlagBadRequest(
            "No object matching content-type %r and object PK %r exists." % \
                (escape(ctype), escape(object_pk)))
    except (ValueError, ValidationError), e:
        return FlagBadRequest(
            "Attempting go get content-type %r and object PK %r exists "
                "raised %s" % \
                (escape(ctype), escape(object_pk), e.__class__.__name__))
    except FlagException, e:
        return FlagBadRequest(
            "Attempting to flag an unauthorized model (%r)" % \
                escape(ctype))


@login_required
def flag(request):
    """
    Validate the form and create the flag.
    In all cases, redirect to the `next` parameter.
    """

    if request.method == 'POST':
        post_data = request.POST.copy()

        object_pk = post_data.get('object_pk')
        content_object = get_content_object(post_data.get("content_type"),
                                            object_pk)

        if (isinstance(content_object, HttpResponseBadRequest)):
                return content_object

        content_type = ContentType.objects.get_for_model(content_object)

        # get the form class regrding if we have a creator_field
        form_class = FlagForm
        if 'creator_field' in post_data:
            form_class = FlagFormWithCreator

        form = form_class(target_object=content_object, data=post_data)

        if form.security_errors():
            return FlagBadRequest(
                "The flag form failed security verification: %s" % \
                    escape(str(form.security_errors())))

        if form.is_valid():

            # manage creator
            creator = None
            if form_class == FlagFormWithCreator:
                creator_field = form.cleaned_data['creator_field']
                if creator_field:
                    creator = getattr(content_object,
                                      creator_field,
                                      None)

            # manage comment
            if flag_settings.get_for_model(content_object, 'ALLOW_COMMENTS'):
                comment = form.cleaned_data['comment']
            else:
                comment = None

            # add the flag, but check the user can do it
            try:
                FlagInstance.objects.add(request.user, content_object,
                    creator, comment, send_signal=True, send_mails=True)
            except FlagException, e:
                messages.error(request, unicode(e))
            else:
                messages.success(request, _("You have added a flag. A "
                        "moderator will review your submission shortly."))

        else:
            # form not valid, we return to the confirm page

            return confirm(request,
                app_label=content_type.app_label,
                object_name=content_type.model,
                object_id=object_pk,
                creator_field=post_data.get('creator_field', None),
                form=form)

    else:
        return FlagBadRequest("Invalid access")

    # try to always redirect to next
    next = get_next(request)
    if next:
        return redirect(next)
    else:
        raise Http404


@login_required
def confirm(request,
            app_label,
            object_name,
            object_id,
            creator_field=None,
            form=None):
    """
    Display a confirmation page for the flagging, with the comment form
    The template rendered is flag/confirm.html but it can be overrided for
    each model by defining a template flag/confirm_applabel_modelname.html
    """
    content_object = get_content_object('%s.%s' % (app_label, object_name),
                                        object_id)
    if (isinstance(content_object, HttpResponseBadRequest)):
            return content_object

    # where to go when finished, also used on error
    next = get_next(request)

    # get the flagged_content, and test if it can be flagged by the user
    try:
        flagged_content = FlaggedContent.objects.get_for_object(content_object)
        try:
            flagged_content.assert_can_be_flagged_by_user(request.user)
        except FlagException, e:
            messages.error(request, unicode(e))
            return redirect(next)
    except ObjectDoesNotExist:
        # if the FlaggedContent does not exists, the object was never flagged
        # so we know that we can continue
        pass

    # define the form
    form = form or get_default_form(content_object, creator_field)

    # ready to render
    context = dict(
        content_object=content_object,
        form=form,
        next=next)

    templates = ['flag/confirm_%s_%s.html' % (app_label, object_name),
                 'flag/confirm.html']

    return render(request, templates, context)
