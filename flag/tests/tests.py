from datetime import datetime
from copy import copy
import time

from django.test import TestCase
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.core.management import call_command
from django.db.models import loading, ObjectDoesNotExist
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.core import mail

from flag.models import FlaggedContent, FlagInstance, add_flag
from flag.tests.models import ModelWithoutAuthor, ModelWithAuthor
from flag import settings as flag_settings
from flag.exceptions import *
from flag.signals import content_flagged
from flag.templatetags import flag_tags
from flag.forms import (FlagForm, FlagFormWithCreator, get_default_form,
        FlagFormWithStatus, FlagFormWithCreatorAndStatus)
from flag.views import (get_confirm_url_for_object,
                       get_content_object,
                       FlagBadRequest)
from flag.utils import get_content_type_tuple


class BaseTestCase(TestCase):
    """
    Base test class to save old flag settings, remove them, and add some
    helper to easily create flags
    """

    test_apps = [
        'django.contrib.auth',
        'django.contrib.messages',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'flag',
        'flag.tests',
    ]

    test_settings = dict(
        ROOT_URLCONF='urls',
        DEBUG=settings.DEBUG)  # used when swapping the debug mode

    def _pre_setup(self):
        """
        Add the test models to the db and other settings
        """

        # manage settings
        self._original_settings = {}
        for key in self.test_settings:
            if hasattr(settings, key):
                self._original_settings[key] = getattr(settings, key)
            setattr(settings, key, self.test_settings[key])

        # manage new apps
        self._original_installed_apps = settings.INSTALLED_APPS

        apps = [app for app in self.test_apps
                    if app not in settings.INSTALLED_APPS]

        settings.INSTALLED_APPS = tuple(
            list(self._original_installed_apps) + list(apps))

        loading.cache.loaded = False
        call_command('syncdb', interactive=False, verbosity=0)

        # Call the original method that does the fixtures etc.
        super(BaseTestCase, self)._pre_setup()

    def _post_teardown(self):
        """
        Restore old INSTALLED_APPS
        """
        # Call the original method.
        super(BaseTestCase, self)._post_teardown()

        # Restore the apps
        settings.INSTALLED_APPS = self._original_installed_apps
        loading.cache.loaded = False
        self._original_installed_apps = ()

        # restore settings
        for key in self._original_settings:
            setattr(settings, key, self._original_settings[key])
        self._original_settings = {}

    def setUp(self):
        """
        Save old flag settings and set them to default
        """
        super(BaseTestCase, self).setUp()
        self._original_flag_settings = dict((key, getattr(flag_settings, key))
                for key in flag_settings.__all__)
        for key in flag_settings.__all__:
            setattr(flag_settings, key, flag_settings._DEFAULTS[key])

    def tearDown(self):
        """
        Restore old flag settings
        """
        for key, value in self._original_flag_settings.items():
            setattr(flag_settings, key, value)
        super(BaseTestCase, self).tearDown()

    def assertNotRaises(self, callableObj, *args, **kwargs):
        """
        Check that an exception is not raised
        """
        try:
            callableObj(*args, **kwargs)
        except Exception, e:
            raise self.failureException("%s raised" % e.__class__.__name__)

    def _add_flagged_content(self, obj, creator=None):
        """
        Create a flag for the given object
        """
        params = dict(content_type=ContentType.objects.get_for_model(obj),
                      object_id=obj.id)
        if creator:
            params['creator'] = creator

        flagged_content = FlaggedContent.objects.create(**params)
        return flagged_content

    def _delete_flagged_contents(self):
        """
        Remove all flagged contents
        """
        FlaggedContent.objects.all().delete()

    def _add_flag(self, flagged_content, comment=None, status=None):
        """
        Add a flag to the given flagged_content
        """
        params = dict(user=self.user)
        if comment:
            params['comment'] = comment
        if status:
            params['status'] = status
        return flagged_content.flag_instances.create(**params)

    def _delete_flags(self):
        """
        Remove all flags
        """
        FlagInstance.objects.all().delete()


class BaseTestCaseWithData(BaseTestCase):

    USER_BASE = 'test-django-flag'

    def setUp(self):
        """
        Add a user which will make the flags, and two flaggable objects
        """
        super(BaseTestCaseWithData, self).setUp()

        # flagger
        self.user = User.objects.create_user(
                username='%s-1' % self.USER_BASE,
                email='%s-1@example.com' % self.USER_BASE,
                password=self.USER_BASE)
        # author of objects
        self.author = User.objects.create_user(
                username='%s-2' % self.USER_BASE,
                email='%s-2@exanple.com' % self.USER_BASE,
                password=self.USER_BASE)
        # staff user
        self.staff_user = User.objects.create_user(
                username='%s-staff' % self.USER_BASE,
                email='%s-staff@example.com' % self.USER_BASE,
                password=self.USER_BASE)
        self.staff_user.is_staff = True
        self.staff_user.save()
        # model without author
        self.model_without_author = ModelWithoutAuthor.objects.create(
                name='foo')
        # model with author
        self.model_with_author = ModelWithAuthor.objects.create(
                name='bar', author=self.author)

    def tearDown(self):
        """
        Drop all objects
        """
        self._delete_flags()
        self._delete_flagged_contents()
        ModelWithoutAuthor.objects.all().delete()
        ModelWithAuthor.objects.all().delete()
        self.user.delete()
        self.author.delete()

        super(BaseTestCaseWithData, self).tearDown()


class ModelsTestCase(BaseTestCaseWithData):
    """
    Class to test the wo models, combined with settings
    """

    def test_model_can_be_flagged(self):
        """
        Test if a model can be flagged (via the MODELS settings)
        """
        # default setting : all models can be flagged
        flag_settings.MODELS = None
        self.assertTrue(
            FlaggedContent.objects.model_can_be_flagged(
                self.model_without_author))
        self.assertNotRaises(
            FlaggedContent.objects.assert_model_can_be_flagged,
            self.model_without_author)
        self.assertTrue(
            FlaggedContent.objects.model_can_be_flagged(
                self.model_with_author))
        self.assertNotRaises(
            FlaggedContent.objects.assert_model_can_be_flagged,
            self.model_with_author)

        # only one model can be flagged
        flag_settings.MODELS = ('tests.modelwithauthor',)
        self.assertFalse(
            FlaggedContent.objects.model_can_be_flagged(
                self.model_without_author))
        self.assertRaises(ModelCannotBeFlaggedException,
            FlaggedContent.objects.assert_model_can_be_flagged,
            self.model_without_author)
        self.assertTrue(
            FlaggedContent.objects.model_can_be_flagged(
                self.model_with_author))
        self.assertNotRaises(
            FlaggedContent.objects.assert_model_can_be_flagged,
            self.model_with_author)

        # test many ways to pass a contentype
        # - object
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            self.model_with_author))
        # - model
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            self.model_with_author.__class__))
        self.assertFalse(FlaggedContent.objects.model_can_be_flagged(
            Exception))
        # - content_type
        content_type = ContentType.objects.get_for_model(
                self.model_with_author)
        #  - object
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            content_type))
        #  - id
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            content_type.id))
        #  - str(id)
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            str(content_type.id)))
        # app_label.model_name
        self.assertTrue(FlaggedContent.objects.model_can_be_flagged(
            '%s.%s' % (content_type.app_label, content_type.model)))
        self.assertFalse(FlaggedContent.objects.model_can_be_flagged(
            'foobar'))

    def test_add_forbidden_flagged_content(self):
        """
        Try to add a FlaggedContent object regarding the MODELS settings
        """

        # default settings : all models can be flagged
        flag_settings.MODELS = None
        self.assertNotRaises(
            self._add_flagged_content, self.model_without_author)
        self.assertNotRaises(
            self._add_flagged_content, self.model_with_author)

        # only one model can be flagged
        self._delete_flagged_contents()
        flag_settings.MODELS = ('tests.modelwithauthor',)
        self.assertRaises(ModelCannotBeFlaggedException,
            self._add_flagged_content, self.model_without_author)
        self.assertNotRaises(
            self._add_flagged_content, self.model_with_author)

    def test_flagged_content_unicity(self):
        """
        Test that we cannot add more than one FlaggedContent for the same
        object
        """
        self.assertNotRaises(
            self._add_flagged_content, self.model_without_author)
        self.assertNotRaises(
            self._add_flagged_content, self.model_with_author)
        self.assertRaises(IntegrityError,
            self._add_flagged_content, self.model_without_author)
        self.assertRaises(IntegrityError,
            self._add_flagged_content, self.model_with_author)

    def test_object_can_be_flagged(self):
        """
        Test if an object can be flagged (via the LIMIT_FOR_OBJECT settings)
        """
        # create the FlaggedContent object, with 0 tags
        flagged_content = self._add_flagged_content(self.model_without_author)

        # test with count=1
        flagged_content.count = 1

        flag_settings.LIMIT_FOR_OBJECT = 0
        self.assertTrue(flagged_content.can_be_flagged())
        self.assertNotRaises(flagged_content.assert_can_be_flagged)

        flag_settings.LIMIT_FOR_OBJECT = 1
        self.assertFalse(flagged_content.can_be_flagged())
        self.assertRaises(ContentFlaggedEnoughException,
            flagged_content.assert_can_be_flagged)

        flag_settings.LIMIT_FOR_OBJECT = 2
        self.assertTrue(flagged_content.can_be_flagged())
        self.assertNotRaises(flagged_content.assert_can_be_flagged)

        # test with count=10
        flagged_content.count = 10

        flag_settings.LIMIT_FOR_OBJECT = 0
        self.assertTrue(flagged_content.can_be_flagged())
        self.assertNotRaises(flagged_content.assert_can_be_flagged)

        flag_settings.LIMIT_FOR_OBJECT = 1
        self.assertFalse(flagged_content.can_be_flagged())
        self.assertRaises(ContentFlaggedEnoughException,
            flagged_content.assert_can_be_flagged)

        flag_settings.LIMIT_FOR_OBJECT = 10
        self.assertFalse(flagged_content.can_be_flagged())
        self.assertRaises(ContentFlaggedEnoughException,
            flagged_content.assert_can_be_flagged)

        flag_settings.LIMIT_FOR_OBJECT = 20
        self.assertTrue(flagged_content.can_be_flagged())
        self.assertNotRaises(flagged_content.assert_can_be_flagged)

    def test_add_too_much_flags(self):
        """
        Try to add flags to objects regarding the LIMIT_FOR_OBJECT settings)
        """
        def add():
            return FlagInstance.objects.add(self.user,
                                            self.model_without_author,
                                            comment='comment')

        # test without limit
        for i in range(0, 5):
            self.assertNotRaises(add)

        # test with limit=10
        flag_settings.LIMIT_FOR_OBJECT = 10
        for i in range(0, 5):
            self.assertNotRaises(add)

        # fail for the 11th
        self.assertRaises(ContentFlaggedEnoughException, add)

    def test_object_can_be_flagged_by_user(self):
        """
        Test if an object can be flagged by a user (via the
        LIMIT_SAME_OBJECT_FOR_USER settings)
        """
        # create the FlaggedContent object
        flagged_content = self._add_flagged_content(self.model_without_author)

        # test with only one flag
        self._add_flag(flagged_content, 'comment')

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 0
        self.assertTrue(flagged_content.can_be_flagged_by_user(self.user))
        self.assertNotRaises(flagged_content.assert_can_be_flagged_by_user,
                             self.user)

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 1
        self.assertFalse(flagged_content.can_be_flagged_by_user(self.user))
        self.assertRaises(ContentAlreadyFlaggedByUserException,
            flagged_content.assert_can_be_flagged_by_user, self.user)

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 2
        self.assertTrue(flagged_content.can_be_flagged_by_user(self.user))
        self.assertNotRaises(flagged_content.assert_can_be_flagged_by_user,
                             self.user)

        # test with 10 flags
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 0
        for i in range(0, 9):
            self._add_flag(flagged_content, 'comment')

        self.assertTrue(flagged_content.can_be_flagged_by_user(self.user))
        self.assertNotRaises(flagged_content.assert_can_be_flagged_by_user,
                             self.user)

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 1
        self.assertFalse(flagged_content.can_be_flagged_by_user(self.user))
        self.assertRaises(ContentAlreadyFlaggedByUserException,
            flagged_content.assert_can_be_flagged_by_user, self.user)

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 10
        self.assertFalse(flagged_content.can_be_flagged_by_user(self.user))
        self.assertRaises(ContentAlreadyFlaggedByUserException,
            flagged_content.assert_can_be_flagged_by_user, self.user)

        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 20
        self.assertTrue(flagged_content.can_be_flagged_by_user(self.user))
        self.assertNotRaises(flagged_content.assert_can_be_flagged_by_user,
                             self.user)

    def test_add_too_much_flags_for_user(self):
        """
        Try to add flags to objects regarding the
        LIMIT_SAME_OBJECT_FOR_USER settings)
        """
        def add(user):
            return FlagInstance.objects.add(user,
                                            self.model_without_author,
                                            comment='comment')

        user2 = User.objects.create_user(
                username='%s-3' % self.USER_BASE,
                email='%s-2@example.com' % self.USER_BASE,
                password=self.USER_BASE)

        # test without limit
        for i in range(0, 5):
            self.assertNotRaises(add, self.user)

        # test with limit=10
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 10
        for i in range(0, 5):
            self.assertNotRaises(add, self.user)

        # fail for the 11th
        self.assertRaises(ContentAlreadyFlaggedByUserException, add, self.user)

        # do not fail for another user
        for i in range(0, 10):
            self.assertNotRaises(add, user2)
        #... until the max
        self.assertRaises(ContentAlreadyFlaggedByUserException, add, user2)

        user2.delete()

    def test_comments(self):
        """
        Test adding a flag with or without a comment, regarding the
        ALLOW_COMMENTS settings
        """
        def add(with_comment):
            params = dict()
            if with_comment:
                params['comment'] = 'comment'
            return FlagInstance.objects.add(self.user,
                                            self.model_without_author,
                                            **params)

        # allow
        flag_settings.ALLOW_COMMENTS = True
        self.assertNotRaises(add, True)
        self.assertRaises(FlagCommentException, add, False)

        # disallow
        flag_settings.ALLOW_COMMENTS = False
        self.assertRaises(FlagCommentException, add, True)
        self.assertNotRaises(add, False)

    def test_count_flags_for_object(self):
        """
        Test the total flags count for an object by adding flags
        """
        def add(status=None):
            params = dict(user=self.user,
                          content_object=self.model_without_author,
                          comment='comment')
            if status is not None:
                params['status'] = status
            return FlagInstance.objects.add(**params)

        # test by simply adding flags
        self.assertEqual(add().flagged_content.count, 1)
        self.assertEqual(add().flagged_content.count, 2)

        # update a flag : the count shouldn't change
        flag_instance = FlagInstance.objects.all()[0]
        previous_count = flag_instance.flagged_content.count
        flag_instance.when_added = datetime.now()
        flag_instance.save()
        self.assertEqual(flag_instance.flagged_content.count, previous_count)

        # add a flag with a moderation status : the count shouldn't change
        flag_instance = add(status=2)
        self.assertEqual(flag_instance.flagged_content.count, previous_count)

    def test_count_flags_by_user(self):
        """
        Test if the count_flag_by_users is correct
        """
        flagged_content = self._add_flagged_content(self.model_without_author)

        self.assertEqual(flagged_content.count_flags_by_user(self.user), 0)
        self._add_flag(flagged_content, 'comment')
        self.assertEqual(flagged_content.count_flags_by_user(self.user), 1)
        for i in range(0, 9):
            self._add_flag(flagged_content, 'comment')
        self.assertEqual(flagged_content.count_flags_by_user(self.user), 10)

    def test_moderator(self):
        """
        Test the set of the last moderator
        """
        flagged_content = self._add_flagged_content(self.model_without_author)
        self.assertEqual(flagged_content.moderator, None)

        flag_instance = FlagInstance.objects.add(
                user=self.user,
                content_object=self.model_without_author,
                comment='comment')
        self.assertEqual(flag_instance.flagged_content.moderator, None)
        flag_instance = FlagInstance.objects.add(
                user=self.user,
                content_object=self.model_without_author,
                comment='comment',
                status=2)
        self.assertEqual(flag_instance.flagged_content.moderator.id,
                self.user.id)

    def test_signal(self):
        """
        Test if the signal is correctly send
        """
        def receive_signal(sender, signal, flagged_content, flagged_instance):
            self.signal_received = dict(flagged_content=flagged_content,
                                        flagged_instance=flagged_instance)

        def clear_received_signal():
            if hasattr(self, 'signal_received'):
                delattr(self, 'signal_received')

        def add(send_signal=False):
            return FlagInstance.objects.add(self.user,
                                            self.model_without_author,
                                            comment='comment',
                                            send_signal=send_signal)

        # connect to the signal
        self.assertNotRaises(content_flagged.connect, receive_signal)

        # add a flag => by default do not send signal
        flag_instance = add()
        self.assertRaises(AttributeError, getattr, self, 'signal_received')

        clear_received_signal()

        # add a flag by saying "send the signal"
        flag_instance = add(send_signal=True)
        self.assertEqual(self.signal_received['flagged_instance'],
                flag_instance)

        clear_received_signal()

        # update the flag => do not send signal
        flag_instance.when_added = datetime.now()
        flag_instance.save()
        self.assertRaises(AttributeError, getattr, self, 'signal_received')

        clear_received_signal()

    def test_mails(self):
        """
        Test if mails are correctly send
        """
        def add(send_mails=True, flagged_object=None, creator=None):
            if not flagged_object:
                flagged_object = self.model_without_author
            return FlagInstance.objects.add(self.user,
                                            flagged_object,
                                            comment='comment',
                                            content_creator=creator,
                                            send_signal=False,
                                            send_mails=send_mails)

        def reset_outbox():
            mail.outbox = []

        reset_outbox()

        # no sending mails
        flag_settings.SEND_MAILS = False
        add()
        self.assertEqual(len(mail.outbox), 0)

        # send mails, for all flag
        flag_settings.SEND_MAILS = True
        flag_settings.SEND_MAILS_RULES = [
            (1, 1),
        ]
        flag_instance = add()
        self.assertEqual(len(mail.outbox), 1)

        # test mail content
        subject = mail.outbox[0].subject
        body = mail.outbox[0].body
        model = '%s.%s' % (self.model_without_author._meta.app_label,
                self.model_without_author._meta.module_name)
        self.assertTrue(model in subject)
        self.assertTrue('#%d' % flag_instance.flagged_content.object_id
                in subject)
        self.assertTrue(model in body)
        self.assertTrue("Total flags: 2" in body)
        self.assertTrue(self.user.username in body)

        # test rules
        reset_outbox()
        self._delete_flagged_contents()
        self._delete_flags()
        flag_settings.SEND_MAILS_RULES = [
            (1, 1),
            (4, 3),
            (10, 5),
        ]
        last_len = 0
        for i in range(1, 17):
            add()
            if i in (1, 2, 3, 4, 7, 10, 15):
                self.assertEqual(len(mail.outbox), last_len + 1)
                last_len += 1
            else:
                self.assertEqual(len(mail.outbox), last_len)

        # sent when max is reached
        reset_outbox()
        flag_settings.LIMIT_FOR_OBJECT = 17
        add()
        self.assertEqual(len(mail.outbox), 1)

        # test creator
        reset_outbox()
        add(flagged_object=self.model_with_author,
            creator=self.model_with_author.author)
        self.assertTrue("The flagged object was created by %s" % (
            self.model_with_author.author.username  in mail.outbox[0].body))

    def test_get_for_object(self):
        """
        Test the get_for_object helper
        """
        # unexisting flag content
        self.assertRaises(ObjectDoesNotExist,
                          FlaggedContent.objects.get_for_object,
                          self.model_without_author)

        # add one
        flagged_content = self._add_flagged_content(self.model_without_author)
        self.assertEqual(flagged_content,
            FlaggedContent.objects.get_for_object(self.model_without_author))

    def test_get_or_create_for_object(self):
        """
        Test the get_or_create_for_object
        """

        # unexisting
        flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author)
        self.assertTrue(isinstance(flagged_content, FlaggedContent))
        self.assertTrue(created)
        self.assertEqual(flagged_content.content_object,
                         self.model_without_author)

        # existing
        same_flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author)
        self.assertFalse(created)
        self.assertEqual(flagged_content, same_flagged_content)

        flagged_content.delete()

        # with status and creator
        # - unexisting
        flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author,
                                         status=2,
                                         content_creator=self.author)
        self.assertEqual(flagged_content.status, 2)
        self.assertEqual(flagged_content.creator, self.author)

        # - existing, status not updated (it's a feature)
        same_flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author,
                                         status=3,
                                         content_creator=self.user)
        self.assertEqual(same_flagged_content.status, 2)
        self.assertEqual(same_flagged_content.creator, self.author)

    def test_filter_on_model(self):
        """
        Test the `filter_on_model` method of FlaggedContentManager
        """
        flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author)

        flagged_contents = FlaggedContent.objects.filter_on_model(
                ModelWithoutAuthor)
        self.assertEqual(flagged_contents.count(), 1)
        self.assertTrue(isinstance(flagged_contents[0], FlaggedContent))
        self.assertEqual(flagged_contents[0].id, flagged_content.id)

        flagged_contents = FlaggedContent.objects.filter_on_model(
                ModelWithAuthor)
        self.assertEqual(flagged_contents.count(), 0)

        # with only_ids
        qs_ids = FlaggedContent.objects.filter_on_model(
                ModelWithoutAuthor, only_object_ids=True)
        objects = ModelWithoutAuthor.objects.filter(
                id__in=qs_ids.filter(status=1))
        self.assertEqual(
                [o.id for o in objects], [self.model_without_author.id])

    def test_generic_relation(self):
        """
        Test the use of a `GenericRelation` to FlaggedContentManager
        """
        flagged_content, created = FlaggedContent.objects.\
                get_or_create_for_object(self.model_without_author)

        flagged_objects = ModelWithoutAuthor.objects.filter(flagged__isnull=False)
        self.assertEqual(flagged_objects.count(), 1)
        self.assertTrue(isinstance(flagged_objects[0], ModelWithoutAuthor))
        self.assertEqual(flagged_objects[0].id, self.model_without_author.id)


class FlagTestSettings(BaseTestCase):
    """
    Class to tests settings and settings by model
    """

    def test_flag_settings(self):
        """
        Test settings
        """
        model = ModelWithAuthor
        model_name = 'tests.modelwithauthor'
        self.assertEqual('.'.join(get_content_type_tuple(model)), model_name)

        # no settings for this model
        flag_settings.MODELS_SETTINGS = {}
        flag_settings.SEND_MAILS = True
        self.assertEqual(flag_settings.SEND_MAILS,
                flag_settings.get_for_model(model_name, 'SEND_MAILS'))
        self.assertEqual(flag_settings.SEND_MAILS,
                flag_settings.get_for_model(model, 'SEND_MAILS'))

        # a setting for this model
        flag_settings.MODELS_SETTINGS[model_name] = {}
        flag_settings.MODELS_SETTINGS[model_name]['SEND_MAILS'] = False
        self.assertNotEqual(flag_settings.SEND_MAILS,
                            flag_settings.get_for_model(model_name,
                                                        'SEND_MAILS'))
        self.assertNotEqual(flag_settings.SEND_MAILS,
                            flag_settings.get_for_model(model, 'SEND_MAILS'))

        # bad model
        self.assertEqual(flag_settings.SEND_MAILS,
                flag_settings.get_for_model('bad-model', 'SEND_MAILS'))

        # forbidden setting
        flag_settings.MODELS = (model_name,)
        flag_settings.MODELS_SETTINGS = {}
        self.assertEqual(flag_settings.MODELS,
                         flag_settings.get_for_model(model_name, 'MODELS'))
        flag_settings.MODELS_SETTINGS[model_name] = {}
        flag_settings.MODELS_SETTINGS[model_name]['MODELS'] = (
                'tests.modelwithoutauthor',)
        self.assertEqual(flag_settings.MODELS,
                         flag_settings.get_for_model(model_name, 'MODELS'))

        # inexistint setting
        self.assertRaises(AttributeError,
                          flag_settings.get_for_model,
                          model_name,
                          'INEXISTING_SETTINGS')


class FlagTemplateTagsTestCase(BaseTestCaseWithData):
    """
    Class to test all template tags and filters
    """

    def test_flag_count(self):
        """
        Test the `flag_count` filter
        """
        # no tags
        self.assertEqual(flag_tags.flag_count(self.model_with_author), 0)

        # add a flagged content
        flagged_content = self._add_flagged_content(self.model_with_author)
        self.assertEqual(flag_tags.flag_count(self.model_with_author), 0)

        # add a tag
        self._add_flag(flagged_content, comment='comment')
        self.assertEqual(flag_tags.flag_count(self.model_with_author), 1)

        # and another
        self._add_flag(flagged_content, comment='comment')
        self.assertEqual(flag_tags.flag_count(self.model_with_author), 2)

    def test_flag_status(self):
        """
        Test the `flat_status` filter
        """
        # no tags
        self.assertEqual(flag_tags.flag_status(self.model_with_author), None)

        # add a tag
        flagged_content = self._add_flagged_content(self.model_with_author)
        self._add_flag(flagged_content, comment='comment')
        self.assertEqual(flag_tags.flag_status(self.model_with_author),
                         flag_settings.STATUSES[0][0])

        # change the status
        flagged_content.status = flag_settings.STATUSES[1][0]
        flagged_content.save()
        self.assertEqual(flag_tags.flag_status(self.model_with_author),
                         flag_settings.STATUSES[1][0])

        # display status' string
        self.assertEqual(unicode(flag_tags.flag_status(
                            self.model_with_author, True)),
                         unicode(flag_settings.STATUSES[1][1]))

    def test_can_be_flagged_by(self):
        """
        Test the `can_be_flagged_by` filter
        """
        def add():
            return FlagInstance.objects.add(self.user,
                                            self.model_with_author,
                                            comment='comment')

        # anonymous user can't
        anonymous = AnonymousUser()
        self.assertFalse(flag_tags.can_be_flagged_by(self.model_with_author,
                                                     anonymous))

        # normal user can
        self.assertTrue(flag_tags.can_be_flagged_by(self.model_with_author,
                                                    self.user))

        # but not on not allowed models
        flag_settings.MODELS = ('tests.modelwithauthor',)
        self.assertFalse(flag_tags.can_be_flagged_by(self.model_without_author,
                                                     self.user))

        # test when limits are raised

        flag_settings.LIMIT_FOR_OBJECT = 5
        for i in range(0, 4):
            add()
        self.assertTrue(flag_tags.can_be_flagged_by(self.model_with_author,
                                                    self.user))
        add()
        self.assertFalse(flag_tags.can_be_flagged_by(self.model_with_author,
                                                     self.user))

        flag_settings.LIMIT_FOR_OBJECT = 0
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 6
        self.assertTrue(flag_tags.can_be_flagged_by(self.model_with_author,
                                                    self.user))
        add()
        self.assertFalse(flag_tags.can_be_flagged_by(self.model_with_author,
                                                     self.user))

        # test with invalid object
        self.assertFalse(flag_tags.can_be_flagged_by(self.model_with_author,
                                                     Exception))

    def test_flag_confirm_url(self):
        """
        Test the `flag_confirm_url` filter (and also urls btw)
        """
        # no object
        self.assertEqual(flag_tags.flag_confirm_url(None), "")
        self.assertEqual(flag_tags.flag_confirm_url_with_status(None), "")

        # an existing object without author
        wanted_url1 = reverse('flag_confirm', kwargs=dict(
                app_label=self.model_without_author._meta.app_label,
                object_name=self.model_without_author._meta.module_name,
                object_id=self.model_without_author.id))
        self.assertEqual(wanted_url1, '/flag/tests/modelwithoutauthor/%d/'
                % self.model_without_author.id)
        self.assertEqual(flag_tags.flag_confirm_url(self.model_without_author),
                         wanted_url1)

        # an existing object with author
        wanted_url2 = reverse('flag_confirm', kwargs=dict(
                app_label=self.model_with_author._meta.app_label,
                object_name=self.model_with_author._meta.module_name,
                object_id=self.model_with_author.id))
        self.assertEqual(wanted_url2, '/flag/tests/modelwithauthor/%d/'
                % self.model_with_author.id)
        wanted_url2bis = wanted_url2 + '?creator_field=author'
        self.assertEqual(wanted_url2bis,
                '/flag/tests/modelwithauthor/%d/?creator_field=author'
                    % self.model_with_author.id)
        self.assertEqual(flag_tags.flag_confirm_url(self.model_with_author,
                'author'), wanted_url2bis)

        # url to update status
        wanted_url1bis = wanted_url1 + '?with_status=1'
        self.assertEqual(wanted_url1bis,
                '/flag/tests/modelwithoutauthor/%d/?with_status=1'
                    % self.model_without_author.id)
        self.assertEqual(flag_tags.flag_confirm_url_with_status(
                self.model_without_author), wanted_url1bis)

        # status and creator field
        wanted_url2ter = wanted_url2 + '?creator_field=author&with_status=1'
        self.assertEqual(wanted_url2ter,
                '/flag/tests/modelwithauthor/%d/'
                '?creator_field=author&with_status=1'
                    % self.model_with_author.id)
        self.assertEqual(flag_tags.flag_confirm_url_with_status(
                self.model_with_author, 'author'), wanted_url2ter)

    def test_flag(self):
        """
        Test the `flag` templatetag
        """
        # no object
        self.assertEqual(flag_tags.flag({}, None), {})

        # an existing object
        result = flag_tags.flag({}, self.model_without_author)
        self.assertEqual(len(result), 2)
        self.assertTrue('next' in result)
        self.assertTrue('form' in result)
        self.assertEqual(result['next'], None)
        # do not test form here
        self.assertTrue(isinstance(result['form'], FlagForm))

        # with status
        result = flag_tags.flag({}, self.model_without_author,
                with_status=True)
        self.assertTrue(isinstance(result['form'],
                        FlagFormWithStatus))
        result = flag_tags.flag({}, self.model_with_author,
                creator_field='author', with_status=True)
        self.assertTrue(isinstance(result['form'],
                        FlagFormWithCreatorAndStatus))

        # helper for status
        result = flag_tags.flag_with_status({}, self.model_without_author)
        self.assertTrue(isinstance(result['form'], FlagFormWithStatus))


class FlagFormTestCase(BaseTestCaseWithData):
    """
    Class to test the flag form
    """

    def test_create_form(self):
        """
        Test the creation of the form
        """
        flag_settings.ALLOW_COMMENTS = False

        form = get_default_form(self.model_without_author)

        # check the used form
        self.assertTrue(isinstance(form, FlagForm))
        self.assertFalse(isinstance(form, FlagFormWithCreator))

        # check data
        self.assertEqual(form['object_pk'].value(),
            str(self.model_without_author.id))
        self.assertEqual(form['content_type'].value(), '%s.%s' % (
            self.model_without_author._meta.app_label,
            self.model_without_author._meta.module_name))

        # check security
        self.assertTrue('timestamp' in form.fields)
        self.assertTrue('security_hash' in form.fields)

        # check with_author
        form = get_default_form(self.model_with_author, 'author')
        self.assertTrue(isinstance(form, FlagFormWithCreator))
        self.assertEqual(form['creator_field'].value(), 'author')

        # check with_status
        form = get_default_form(self.model_without_author, with_status=True)
        self.assertTrue(isinstance(form, FlagFormWithStatus))
        self.assertEqual(form['status'].field.choices,
                flag_settings.get_for_model(
                    self.model_without_author, 'STATUSES'))

        # check with_status and with_author
        form = get_default_form(self.model_with_author,
                                'author',
                                with_status=True)
        self.assertTrue(isinstance(form, FlagFormWithCreatorAndStatus))
        self.assertEqual(form['creator_field'].value(), 'author')
        self.assertEqual(form['status'].field.choices,
                flag_settings.get_for_model(
                    self.model_with_author, 'STATUSES'))

    def _get_form_data(self, obj, creator_field=None):
        """
        Helper to get some data for the form
        """
        return data

    def test_validate_form(self):
        """
        Test the validation of the form
        """
        # get default form data
        form = get_default_form(self.model_without_author)
        form_data = dict((key, form[key].value()) for key in form.fields)
        form_data.update(dict(csrf_token=None, comment='comment'))

        # test valid form
        form = FlagForm(self.model_without_author, copy(form_data))
        self.assertTrue(form.is_valid())

        # test bad security hash
        data = copy(form_data)
        data['security_hash'] = 'zz' + data['security_hash'][2:]
        form = FlagForm(self.model_without_author, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form['security_hash'].errors), 1)
        self.assertTrue(len(form.security_errors()) == 1)

        # test bad timestamp
        data = copy(form_data)
        data['timestamp'] = str(int(time.time()) - (3 * 60 * 60))
        form = FlagForm(self.model_without_author, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form['timestamp'].errors), 1)

        # test missing comment
        data = copy(form_data)
        del data['comment']
        form = FlagForm(self.model_without_author, data)
        self.assertFalse(form.is_valid())


class FlagViewsTestCase(BaseTestCaseWithData):
    """
    Test the two views
    """

    def test_get_content_object(self):
        """
        Test the get_content_object in views.py
        """
        ctype = 'tests.modelwithauthor'
        id = self.model_with_author.id

        # no ctype or no id
        self.assertTrue(isinstance(get_content_object(None, None),
                        FlagBadRequest))
        # bad ctype
        self.assertTrue(isinstance(get_content_object('foobar', id),
                        FlagBadRequest))
        # not resolvable ctype
        self.assertTrue(isinstance(get_content_object(ctype + 'x', id),
                        FlagBadRequest))
        # not existing id
        self.assertTrue(isinstance(get_content_object(ctype, 10000),
                        FlagBadRequest))
        # invalid id
        self.assertTrue(isinstance(get_content_object(ctype, 'foobar'),
                        FlagBadRequest))

        # all ok
        self.assertEqual(get_content_object(ctype, id), self.model_with_author)

        # forbidden model
        flag_settings.MODELS = ('tests.modelwithoutauthor',)
        self.assertTrue(isinstance(get_content_object(ctype, id),
                        FlagBadRequest))

        # test debug mode on error
        flag_settings.MODELS = None
        settings.DEBUG = False
        result_debug_false = get_content_object(ctype, 'foobar')
        self.assertEqual(len(result_debug_false.content), 0)
        debug = settings.DEBUG
        settings.DEBUG = True
        result_debug_true = get_content_object(ctype, 'foobar')
        self.assertNotEqual(len(result_debug_true.content), 0)
        settings.DEBUG = debug

    def test_confirm_view(self):
        """
        Test the "confirm" view
        """
        url = get_confirm_url_for_object(self.model_without_author)

        # not authenticated
        resp = self.client.get(url)
        self.assertTrue(isinstance(resp, HttpResponseRedirect))
        self.assertTrue('?next=%s' % url in resp['Location'])

        # authenticated user
        self.client.login(username=self.user.username,
                          password=self.USER_BASE)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.context['form'], FlagForm))
        self.assertEqual(resp.context['next'], url)

        # already flagged object
        FlagInstance.objects.add(self.user,
                                 self.model_without_author,
                                 comment='comment')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # with limit
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 1
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 0

        # bad content object
        resp = self.client.get('/flag/foo/bar/1000/')
        self.assertTrue(isinstance(resp, FlagBadRequest))

        # test with_status
        url_with_status = get_confirm_url_for_object(self.model_without_author,
                with_status=True)
        # user is not staff
        resp = self.client.get(url_with_status)
        self.assertEqual(resp.status_code, 400)
        # user is staff
        self.client.logout()
        self.client.login(username=self.staff_user,
                          password=self.USER_BASE)
        resp = self.client.get(url_with_status)
        self.assertEqual(resp.status_code, 200)

    def test_post_view(self):
        """
        Test the "flag" view
        """
        # get default form data
        form = get_default_form(self.model_without_author)
        form_data = dict((key, form[key].value()) for key in form.fields)
        form_data.update(dict(csrf_token=None, comment='comment'))

        url = reverse('flag')

        # not authenticated
        resp = self.client.post(url, copy(form_data))
        self.assertTrue(isinstance(resp, HttpResponseRedirect))
        self.assertTrue('?next=%s' % url in resp['Location'])
        self.assertEqual(FlagInstance.objects.count(), 0)

        # authenticated user
        self.client.login(username='%s-1' % self.USER_BASE,
                          password=self.USER_BASE)
        resp = self.client.post(url, copy(form_data))
        self.assertTrue(isinstance(resp, HttpResponseRedirect))
        self.assertEqual(FlagInstance.objects.count(), 1)
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_without_author)
        self.assertEqual(flagged_content.count, 1)
        self.assertEqual(flagged_content.flag_instances.all()[0].comment,
                         'comment')

        # bad object
        data = copy(form_data)
        data['object_pk'] = 'foo'
        resp = self.client.post(url, data)
        self.assertTrue(isinstance(resp, FlagBadRequest))

        # creator
        cform = get_default_form(self.model_with_author, 'author')
        self.assertTrue('creator_field' in cform.fields)
        cform_data = dict((key, cform[key].value()) for key in cform.fields)
        cform_data.update(dict(csrf_token=None, comment='comment'))
        resp = self.client.post(url, cform_data)
        self.assertTrue(isinstance(resp, HttpResponseRedirect))
        self.assertEqual(FlagInstance.objects.count(), 2)
        self.assertEqual(FlaggedContent.objects.get_for_object(
            self.model_with_author).count, 1)

        # bad security
        data = copy(form_data)
        data['security_hash'] = 'zz' + data['security_hash'][2:]
        resp = self.client.post(url, data)
        self.assertTrue(isinstance(resp, FlagBadRequest))

        # no comment allowed
        flag_settings.ALLOW_COMMENTS = False
        data = copy(form_data)
        resp = self.client.post(url, data)
        self.assertTrue('<ul class="errorlist"><li>You are not allowed to add '
                'a comment</li></ul>' in resp.content)
        del data['comment']
        resp = self.client.post(url, data)
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_without_author)
        self.assertEqual(flagged_content.count, 2)
        self.assertIsNone(flagged_content.flag_instances.all()[0].comment)

        # limit by user
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 2
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_without_author)
        count_before = flagged_content.count
        resp = self.client.post(url, copy(form_data))
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_without_author)
        self.assertEqual(flagged_content.count, count_before)
        flag_settings.LIMIT_SAME_OBJECT_FOR_USER = 0

        # error : return to confirm page
        flag_settings.ALLOW_COMMENTS = True
        data = copy(form_data)
        del data['comment']  # missing comment
        data['next'] = '/foobar/'
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.context['form'], FlagForm))
        self.assertEqual(resp.context['next'], data['next'])

        # test get access
        resp = self.client.get(url)
        self.assertTrue(isinstance(resp, FlagBadRequest))

        # test with_status
        data = copy(form_data)
        data['status'] = 2
        # user is not staff
        resp = self.client.post(url, data)
        self.assertTrue(isinstance(resp, FlagBadRequest))
        # user is staff
        self.client.logout()
        self.client.login(username=self.staff_user,
                          password=self.USER_BASE)
        count_before_obj = FlagInstance.objects.count()
        count_before_inst = FlaggedContent.objects.get_for_object(
                self.model_without_author).count
        resp = self.client.post(url, data)
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_without_author)
        self.assertEqual(flagged_content.status, 2)
        # we have a new flag instance
        self.assertEqual(FlagInstance.objects.count(), count_before_obj + 1)
        # but the flag's count for this object is the same
        self.assertEqual(flagged_content.count, count_before_inst)

        # creator and status
        form = get_default_form(self.model_with_author, creator_field='author')
        data = dict((key, form[key].value()) for key in form.fields)
        data.update(dict(csrf_token=None, comment='comment'))
        data['status'] = 3
        resp = self.client.post(url, data)
        flagged_content = FlaggedContent.objects.get_for_object(
                self.model_with_author)
        self.assertEqual(flagged_content.status, 3)
        self.assertEqual(flagged_content.moderator.id, self.staff_user.id)

    def test_add_flag_compatibility(self):
        """
        Test the old "add_flag" function, kept for compatibility
        """
        flag_instance = add_flag(
            self.user,
            ContentType.objects.get_for_model(self.model_with_author),
            self.model_with_author.id,
            None,
            'comment')

        self.assertTrue(isinstance(flag_instance, FlagInstance))
        self.assertEqual(flag_instance.flagged_content.content_object,
                         self.model_with_author)
