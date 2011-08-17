from django import conf
from django.utils.translation import ugettext_lazy as _

__all__ = ('ALLOW_COMMENTS', 'LIMIT_SAME_OBJECT_FOR_USER', 'LIMIT_FOR_OBJECT', 'MODELS', 'STATUS')

# Set FLAG_ALLOW_COMMENTS to False in settings to not allow users to
# comment their flags (True by default)
ALLOW_COMMENTS = getattr(conf.settings, 'FLAG_ALLOW_COMMENTS', True)

# Set FLAG_LIMIT_SAME_OBJECT_FOR_USER to a number in settings to limit the times
# a user can flag a single object
LIMIT_SAME_OBJECT_FOR_USER = getattr(conf.settings, 'FLAG_LIMIT_SAME_OBJECT_FOR_USER', 0)

# Set FLAG_LIMIT_FOR_OBJECT to a number in settings to limit the times an
# object can be flagged
LIMIT_FOR_OBJECT = getattr(conf.settings, 'FLAG_LIMIT_FOR_OBJECT', 0)

# Set FLAG_MODELS to a list/tuple of models in your settings to limit the
# models that can be flagged. The syntax to use is a string for each model :
# FLAG_MODELS = ('myapp.mymodel', 'otherapp.othermodel',)
MODELS = getattr(conf.settings, 'FLAG_MODELS', None)

# Set FLAG_STATUSES to a list of tuples in your settings to set the available
# status for each flagged content
# The default status used when a user flag an object is the first of this list.
STATUS = getattr(conf.settings, "FLAG_STATUSES", [
    ("1", _("flagged")),
    ("2", _("flag rejected by moderator")),
    ("3", _("creator notified")),
    ("4", _("content removed by creator")),
    ("5", _("content removed by moderator")),
])
