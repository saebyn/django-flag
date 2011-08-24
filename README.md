# django-flag

This app lets users of your site flag content as inappropriate or spam.

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
* create, for each model that can be flagged, a template `flag/confirm_applabel_modelname.html` (by replacing *app_label* and *model_name* by the good values).

Usage of the filter:

```html
{% load flag_tags %}
<a href="{{ anobject|flag_confirm_url }}">flag</a>
```

## Other things

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

### Views and urls

*django-flag* has two urls and views : 

* one to display the confirm page, (url `flag_confirm`, view `confirm`), with some parameters : `app_label`, `object_name`, `object_id`, `creator_field` (the last one is optionnal)
* one to flag (only POST allowed) (url `flag`, view `flag`), without any parameter

### Security

The form used by *django-flag* is based on a the `CommentSecurityForm` provided by `django.contrib.comments.forms`.
It provides a security_hash to limit spoofing (we don't directly use `CommentSecurityForm`, but a duplicate, because we don't want to import the comments models)

When something forbidden is done (bad security hash, object the user can't flag...), a `FlagBadRequest` (based on `HttpResponseBadRequest`) is returned.
While in debug mode, this `FlagBadRequest` doesn't return a HTTP error (400), but render a template with more information.

### Tests

*django-flag* is fully tester. Just run `manage.py test flag` in your project.
If `django-nose` is installed, it is used to run tests. You can see a coverage of 98%. Admin and some weird `next` parameters are not tested.

*django-flag* also provide a test project, where you can flag users (no other model included).


