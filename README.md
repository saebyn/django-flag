# django-flag

This app lets users of your site flag content as inappropriate or spam.

PS : the version 0.3 is a big rewrite, but with retrocompatibility kept in mind.

## Where's Wally ?

The original code is here : https://github.com/pinax/django-flag
This fork (by twidi) is here : https://github.com/twidi/django-flag

## Installation

*django-flag* has no requirements, except *django* (1.3) of course

`pip install git+git://github.com/twidi/django-flag.git#egg=django-flag`

## Settings

The behavior of *django-flag* can be tweaked with some settings :

### FLAG_ALLOW_COMMENTS

Set `FLAG_ALLOW_COMMENTS` to False to disallow users to add a comment when flagging an object.
Default to `True`.

### FLAG_LIMIT_SAME_OBJECT_FOR_USER

Set `FLAG_LIMIT_SAME_OBJECT_FOR_USER` to a number to limit the times a user can flag a single object.
If 0, there is no limit.
Default to `0`.

### FLAG_LIMIT_FOR_OBJECT

Set `FLAG_LIMIT_FOR_OBJECT` to a number to limit the times an object can be flagged.
If 0, there is no limit.
Default to `0`.

### FLAG_MODELS

Set `FLAG_MODELS` to a list/tuple of models to limit the models that can be flagged.
For each model, use a string like '*applabel.modelname*'.
If not set (`None`), all models can be flagged. If set to an empty list/tuple, no model can be flagged.
Default to `None`.

### FLAG_STATUSES

Set `FLAG_STATUSES` to a list of tuples to set the available statuses for each flagged content.
The default status used when a user flag an object is the first of this list.
Default to :

```python
FLAG_STATUSES = [
    ("1", _("flagged")),
    ("2", _("flag rejected by moderator")),
    ("3", _("creator notified")),
    ("4", _("content removed by creator")),
    ("5", _("content removed by moderator")),
]
```

### FLAG_SEND_MAILS
Set `FLAG_SEND_MAILS` to `True` if you want to have emails sent when object are flagged.
See others settings SEND_MAILS_* for more configuration
Default to `False`

### SEND_MAILS_TO
Set `FLAG_SEMD_MAILS_TO` to a list of email addresses to sent mails when an object is flagged.
Each entry can be either a single email address, or a tuple with (name, email address) but only the mail will be used.
Default to `settings.ADMINS`

### SEND_MAILS_FROM
Set `FLAG_SEND_MAILS_FROM` to an email address to use as the send of mails sent when an object is flagged.
Default to `settings.DEFAULT_FROM_EMAIL`

### SEND_MAILS_RULES
Set FLAG_SEND_MAILS_RULES to define when to send mails for flags.
This settings is a list of tuple, each line defining a rule.
A rule is a tuple with two entries, the first one is the minimum flag for an object for which this rule apply, and the second one is the frequency :
Example : `(4, 3)` = if an object is flagged 4 times or more, send a mail every 3 flags (4, 7 and 10)
If this rule is followed by `(10, 5)`, it will be used only when an object is flagged between 5 (included) and 10 times (not included), then the `10` rules will apply (10, 15, 20...)
A mail will be send if the LIMIT_FOR_OBJECT is reached, ignoring the rules.
Default to `[(1, 1)` : send a mail for each flag (if `FLAG_SEND_MAILS` is `True`)

Exemple:

```python
# mail will be send for 1, 2, 3, 4, 7, 10, 15, 20, 25...
FLAG_SEND_MAILS_RULES = [
    (1, 1),  # send a mail for every flag
    (4, 3),  # send a mail every 3 flags starting to the 5th flag
    (10, 5), # send a mail every 5 flags starting to the 10th flag
]
```

## Usage

* add `flag` to your INSTALLED_APPS
* add the urls to your urls : `url(r'^flag/', include('flag.urls')),`


*djang-flag* provides some usefull templatetags and filters to be included via `{% load flag_tags %}`.

There are two ways to use these templatetags to use *django-flag* :

### Only the flag form

On any page you can use the `flag` templatetag to add a form for flagging the object.
This form will or will not have a comment box, depending of your `FLAG_ALLOW_COMMENTS` settings.
This templatetag is an *inclusion_tag* calling the template `flag/flag_form.html`, so you can easily override it.

This default template is as simple as :

```html
<form method="POST" action="{% url flag %}">{% csrf_token %}
    {{ form.as_p }}
    {% if next %}<input type="hidden" name="next" value="{{ next }}{% endif %}" />
    <input type="submit" value="Submit Flag" /></td>
</form>
```

Usage:

```html
{% load flag_tags %}
{% flag an_object %}
```

### Flag via a confirmation page

If you want the form to be on an other page, which play the role of a confirmation page, you can use the `flag_confirm_url` template filter, which will insert the url of the confirm page for this object.
This url is linked to a view which will display the confirm form (with or without a comment box, depending of your `FLAG_ALLOW_COMMENTS` settings.) in a template `flag/confirm.html`.

This default template is as simple as :

```html
{% block flag_form %}
    {% include "flag/flag_form.html" %}
{% endblock %}
```

You can override the template used by this view by two ways :

* create your own `flag/confirm.html` template
* create, for each model that can be flagged and for which you want a specific template, a template `flag/confirm_applabel_modelname.html` (by replacing *app_label* and *model_name* by the good values, ex. `auth` and `user` for the `User` model in `django.contrib.auth`).

Usage of the filter:

```html
{% load flag_tags %}
<a href="{{ anobject|flag_confirm_url }}">flag</a>
```

### Signal

When an object is flagged, a signal `content_flagged` is sent, with the `flagged_content` and `flagged_instance` objects (`flagged_instance` should be called `flag_instance` but this is kept for retrocompatibility).

```python
from flag.signals import content_flagged

def something_was_flagged(sender, signal, flagged_content, flagged_instance):
    # do something here

content_flagged.connect(something_was_flagged)
```

This signal is sent only when a *new* flag is created, not when the add fail and not when a flag is updated. And only when it is created via the form. When saved in admin or in a shell, the signal is not sent. In the shell you must pass a `send_signal` parameter (`True`) to the `save` or `add` methods. If you want a signal sent for *every* save of a flag, you can use the django `post_save` one.

### Mails

When an object is flagged, and if the `FLAG_SEND_MAILS` setting is `True`, the `SEND_MAILS_RULES` rules will be analyzed and if one matching the current count of flags for this object, a mail is send to recipients defined in `SEND_MAILS_TO`.

The subjet and body of the sent mail are stored in templates `flag/mail_alert_subject.txt` and `flag/mail_alert_body.txt`.

You can override these temlates by two ways :

* create your own `flag/mail_alert_subject.txt` and/or `flag/mail_alert_body.txt` templates
* create, for each model that can be flagged and for which you want a specific template, `flag/mail_alert_subject_applabel_modelname.txt` and/or `flag/mail_alert_body_applabel_modelname.txt` (by replacing *app_label* and *model_name* by the good values, ex. `auth` and `user` for the `User` model in `django.contrib.auth`).

## Other things you would want to know

### More template filters

*django-flag* provides 3 more filters to use in your application :

* `{{ an_object|can_be_flagged_by:request.user }}` Will return *True* or *False* depending if the user can flag this object or not, regarding all the flag settings
* `{{ an_object|flag_count }}` : Will return the number of flag for this object
* `{{ an_object|flag_status }}` : Will return the current flag status for this object (see the `FLAG_STATUSES` settings above for more informations about status)

### Creator

*django-flag* can save the *creator* of the flagged objects in its own model.
This can be used to retrieve all flagged objects of one user :

```python
flagged_objects = user.flagged_content.all()
```

To set the creator, it's as easy as adding the name of the creator field of the flagged object as a parameter to the `flag` templatetag or the `flag_confirm_url` filter.
Then django-flag will check it and save a reference into its model.
Example, with `an_object` having a `author` field as a *ForeignKey* to the `User` model :

```html
{% flag an_object 'author' %}
<a href="{{ anobject|flag_confirm_url:'author' }}">flag</a>
```

### Tests

*django-flag* is fully tester. Just run `manage.py test flag` in your project.
If `django-nose` is installed, it is used to run tests. You can see a coverage of 98%. Admin and some weird `next` parameters are not tested.

*django-flag* also provide a test project, where you can flag users (no other model included).

### Admin

The admin interface for *django-flag* has been improved a bit : better list and change form with for this one, links to flagged objects and their authors.


## Internal

### Models

There is two models in *django-flag*, `FlaggedContent` and `FlagInstance`, described below.
When an object is flagged for the first time, a `FlaggedContent` is created, and each flag add a `FlagInstance` object.
The `status` and `count` fields of the `FlaggedContent` object are updated on each flag.

#### FlaggedContent

This model keeps a reference to the flagged object, store its current status, the flags count, the last moderator, and, eventually, its creator (the user who created the flagged object)

#### FlagInstance

Each flag is stored in this model, which store the user/flagger, the flagged content, an optional comment, and the date of the flag

You can add a flag programmatically with :

```python
FlagInstance.objects.add(flagging_user, object_to_flag, 'creator field (or None)', 'a comment')
```

In previous version, a `add_flag` (in `models.py`) function was the way to add a flag. It is always here, for retrocompatibility, but with a simple call to `FlagInstance.objects.add`.

### Views and urls

*django-flag* has two urls and views :

* one to display the confirm page, (url `flag_confirm`, view `confirm`), with some parameters : `app_label`, `object_name`, `object_id`, `creator_field` (the last one is optionnal)
* one to flag (only POST allowed) (url `flag`, view `flag`), without any parameter

### Security

The form used by *django-flag* is based on a the `CommentSecurityForm` provided by `django.contrib.comments.forms`.
It provides a security_hash to limit spoofing (we don't directly use `CommentSecurityForm`, but a duplicate, because we don't want to import the comments models)

When something forbidden is done (bad security hash, object the user can't flag...), a `FlagBadRequest` (based on `HttpResponseBadRequest`) is returned.
While in debug mode, this `FlagBadRequest` doesn't return a HTTP error (400), but render a template with more information.


