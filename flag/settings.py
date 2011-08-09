from django import conf

# Set FLAG_ALLOW_COMMENTS to True in settings to allow users to
# comment their flags
ALLOW_COMMENTS = getattr(conf.settings, 'FLAG_ALLOW_COMMENTS', False)

