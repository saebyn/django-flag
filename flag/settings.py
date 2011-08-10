from django import conf

# Set FLAG_ALLOW_COMMENTS to False in settings to not allow users to
# comment their flags (True by default)
ALLOW_COMMENTS = getattr(conf.settings, 'FLAG_ALLOW_COMMENTS', True)

