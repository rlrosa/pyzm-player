from django.db import models


class Song(models.Model):
    songName = models.CharField(max_length=200)
    songSource = models.CharField(max_length=1000)
    songAuthor = models.CharField(max_length=200)
    songStyle = models.CharField(max_length=200)
    