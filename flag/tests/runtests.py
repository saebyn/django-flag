#!/usr/bin/env python
import os
import sys

from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES = dict(default=dict(ENGINE='django.db.backends.sqlite3')),
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.messages',
            'django.contrib.contenttypes',
            'flag',
            'flag.tests',
        ]
    )

from django.test.simple import DjangoTestSuiteRunner

class FlagTestSuiteRunner(DjangoTestSuiteRunner):
    pass

def runtests(*test_args):
    if not test_args:
        test_args = ['tests']
    parent = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
    )
    sys.path.insert(0, parent)
    failures = FlagTestSuiteRunner(verbosity=1, interactive=True).run_tests(test_args)
    sys.exit(failures)


if __name__ == '__main__':
    runtests(*sys.argv[1:])


