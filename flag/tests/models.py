from django.db import models
from django.contrib.auth.models import User

class ModelWithoutAuthor(models.Model):
    name = models.CharField(max_length=50)

    def __unicode__(self):
        return self.name


class ModelWithAuthor(models.Model):
    name = models.CharField(max_length=50)
    author = models.ForeignKey(User)

    def __unicode__(self):
        return self.name
