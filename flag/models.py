from datetime import datetime

from django.db import models
from django.core import urlresolvers
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _, ungettext

from flag import settings as flag_settings
from flag import signals
from flag.exceptions import *

class FlaggedContentManager(models.Manager):
    """
    Manager for the FlaggedContent models
    """

    def get_for_object(self, content_object):
        """
        Helper to get a FlaggedContent instance for the given object
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return self.get(
                content_type__id=content_type.id,
                object_id=content_object.id
            )

    def get_or_create_for_object(self, content_object, content_creator=None, status=None):
        """
        A wrapper around get_or_create to easily manage the fields
        `content_creator` and `status` are only set when creating the object
        """
        defaults = {}
        if content_creator is not None:
            defaults['creator'] = content_creator
        if status is not None:
            defaults['status'] = status
        flagged_content, created = FlaggedContent.objects.get_or_create(
            content_type = ContentType.objects.get_for_model(content_object),
            object_id = content_object.id,
            defaults = defaults
        )
        return flagged_content, created

    def model_can_be_flagged(self, content_type):
        """
        Return True if the model is listed in the MODELS settings (or if this
        settings is not defined)
        `content_type` can be : a ContentType id (as integer or string), a
        ContentType object, a string 'app_label.model_name', a model or an object
        """
        if flag_settings.MODELS is None:
            return True

        # try to find app and model from the content_type

        # check if integer, as integer or string => content_type id
        if isinstance(content_type, int) or (
                isinstance(content_type, basestring) and content_type.isdigit()):
            ctype = ContentType.objects.get_for_id(content_type)
            app_label, model = ctype.app_label, ctype.model

        # check if string => 'app_label.model_name'
        elif isinstance(content_type, basestring):
            try:
                app_label, model = content_type.split('.', 1)
            except:
                return False

        # check if its a content_type object
        elif isinstance(content_type, ContentType):
            app_label, model = content_type.app_label, content_type.model

        # check if a model
        else:
            try:
                ctype = ContentType.objects.get_for_model(content_type)
            except:
                return False
            else:
                app_label, model = ctype.app_label, ctype.model

        # finally we can check
        model = '%s.%s' % (app_label, model)
        return model in flag_settings.MODELS

    def assert_model_can_be_flagged(self, content_type):
        """
        Raise an acception if the "model_can_be_flagged" method return False
        """
        if not self.model_can_be_flagged(content_type):
            raise ModelCannotBeFlaggedException(_('This model cannot be flagged'))


class FlaggedContent(models.Model):

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey("content_type", "object_id")

    creator = models.ForeignKey(User, related_name="flagged_content", null=True, blank=True) # user who created flagged content -- this is kept in model so it outlives content
    status = models.CharField(max_length=1, choices=flag_settings.STATUS, default=flag_settings.STATUS[0][0])
    moderator = models.ForeignKey(User, null=True, related_name="moderated_content") # moderator responsible for last status change
    count = models.PositiveIntegerField(default=0)

    # manager
    objects = FlaggedContentManager()

    class Meta:
        unique_together = [("content_type", "object_id")]
        ordering = ('-id',)

    def __unicode__(self):
        """
        Show the flagged object in the unicode string
        """
        return u'%s' % repr(self.content_object)

    def count_flags_by_user(self, user):
        """
        Helper to get the number of flags on this flagged content by the
        given user
        """
        return self.flaginstance_set.filter(user=user).count()

    def can_be_flagged(self):
        """
        Check that the LIMIT_FOR_OBJECT is not raised
        """
        if not flag_settings.LIMIT_FOR_OBJECT:
            return True
        return self.count < flag_settings.LIMIT_FOR_OBJECT

    def assert_can_be_flagged(self):
        """
        Raise an acception if the "can_be_flagged" method return False
        """
        if not self.can_be_flagged():
            raise ContentFlaggedEnoughException(_('Flag limit raised'))

    def can_be_flagged_by_user(self, user):
        """
        Check that the LIMIT_SAME_OBJECT_FOR_USER is not raised for this user
        """
        if not self.can_be_flagged():
            return False
        if not flag_settings.LIMIT_SAME_OBJECT_FOR_USER:
            return True
        return self.count_flags_by_user(user) < flag_settings.LIMIT_SAME_OBJECT_FOR_USER

    def assert_can_be_flagged_by_user(self, user):
        """
        Raise an exception if the given user cannot flag this object
        """
        try:
            self.assert_can_be_flagged()
        except ContentFlaggedEnoughException, e:
            raise e
        else:
            # do not use self.can_be_flagged_by_user because we need the count
            if not flag_settings.LIMIT_SAME_OBJECT_FOR_USER:
                return
            count = self.count_flags_by_user(user)
            if count >= flag_settings.LIMIT_SAME_OBJECT_FOR_USER:
                error = ungettext(
                            'You already flagged this',
                            'You already flagged this %(count)d times',
                            count
                        ) % {
                            'count': count
                        }
                raise ContentAlreadyFlaggedByUserException(error)

    def get_content_object_admin_url(self):
        """
        Return the admin url to the content object
        """
        if self.content_object:
            return urlresolvers.reverse("admin:%s_%s_change" % (
                    self.content_object._meta.app_label,
                    self.content_object._meta.module_name
                ), args=(self.object_id,)
            )

    def save(self, *args, **kwargs):
        """
        Before the save, we check that we can flag this object
        """

        # check if we can flag this model
        FlaggedContent.objects.assert_model_can_be_flagged(self.content_object)

        super(FlaggedContent, self).save(*args, **kwargs)

    def flag_added(self, flag_instance):
        """
        Called when a flag is added, to update the count and send a signal
        """
        # increment the count
        self.count = models.F('count') + 1
        self.save()

        # update count of the current object
        new_self = FlaggedContent.objects.get(id=self.id)
        self.count = new_self.count

        # send a signal
        signals.content_flagged.send(
            sender = FlaggedContent,
            flagged_content = self,
            flagged_instance = flag_instance,
        )


class FlagInstanceManager(models.Manager):
    """
    Manager for the FlagInstance model, adding a `add` method
    """

    def add(self, user, content_object, content_creator=None, comment=None, status=None):
        """
        Helper to easily create a flag of an object
        `content_creator` and `status` can only be set if it's the first flag
        """

        # get or create the FlaggedContent object
        flagged_content, created = FlaggedContent.objects.get_or_create_for_object(
                content_object, content_creator, status)

        # add the flag
        flag_instance = FlagInstance.objects.create(
            flagged_content = flagged_content,
            user = user,
            comment = comment
        )

        return flag_instance


class FlagInstance(models.Model):

    flagged_content = models.ForeignKey(FlaggedContent)
    user = models.ForeignKey(User) # user flagging the content
    when_added = models.DateTimeField(default=datetime.now)
    when_recalled = models.DateTimeField(null=True) # if recalled at all
    comment = models.TextField(null=True, blank=True) # comment by the flagger

    objects = FlagInstanceManager()

    class Meta:
        ordering = ('-when_added',)

    def save(self, *args, **kwargs):
        """
        Save the flag and, if it's a new one, tell it to the flagged_content.
        Also check if set a comment is allowed
        """
        is_new = not bool(self.id)

        # check if the user can flag this object
        self.flagged_content.assert_can_be_flagged_by_user(self.user)

        # check comment
        if is_new:
            if flag_settings.ALLOW_COMMENTS and not self.comment:
                raise FlagCommentException(_('You must had a comment'))
            if not flag_settings.ALLOW_COMMENTS and self.comment:
                raise FlagCommentException(_('You are not allowed to add a comment'))

        super(FlagInstance, self).save(*args, **kwargs)

        # tell the flagged_content that it has a new flag
        if is_new:
            self.flagged_content.flag_added(self)


def add_flag(flagger, content_type, object_id, content_creator, comment, status=None):
    """
    This function is here for compatibility
    """
    content_object = content_type.get_object_for_this_type(id=object_id)
    return FlagInstance.objects.add(flagger, content_object, content_creator, comment, status)
