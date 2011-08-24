from django import get_version
from django.contrib import admin

from flag.models import FlaggedContent, FlagInstance


class InlineFlagInstance(admin.TabularInline):
    model = FlagInstance
    extra = 0


class FlaggedContentAdmin(admin.ModelAdmin):
    inlines = [InlineFlagInstance]
    list_display = ('id', '__unicode__', 'status', 'count')
    list_display_links = ('id', '__unicode__')
    list_filter = ('status',)
    readonly_fields = ('content_type', 'object_id')
    if get_version() >= '1.4':
        fields = (('content_type', 'object_id'), 'creator', 'status', 'count', 'moderator')
    else:
        fields = ('content_type', 'object_id', 'creator', 'status', 'count', 'moderator')


admin.site.register(FlaggedContent, FlaggedContentAdmin)
