from django import conf

# Set FLAG_ALLOW_COMMENTS to False in settings to not allow users to
# comment their flags (True by default)
ALLOW_COMMENTS = getattr(conf.settings, 'FLAG_ALLOW_COMMENTS', True)

# Set FLAG_LIMIT_SAME_OBJECT_FOR_USER to a number in settings to limit the times
# a user can flag a single object
LIMIT_SAME_OBJECT_FOR_USER = getattr(conf.settings, 'FLAG_LIMIT_SAME_OBJECT_FOR_USER', 0)

# Set FLAG_LIMIT_FOR_OBJECT to a number in settings to limit the times an
# object can be flagged
LIMIT_FOR_OBJECT = getattr(conf.settings, 'FLAG_LIMIT_FOR_OBJECT', 0)


