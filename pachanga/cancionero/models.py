from django.db import models


class Song(models.Model):
    title  = models.CharField(max_length=200, default='unknown')
    artist = models.CharField(max_length=200,  default='unknown')
    album  = models.CharField(max_length=200,  default='unknown')
    genre  = models.CharField(max_length=200,  default='unknown')
    url    = models.CharField(max_length=1000, default='')
