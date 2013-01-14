from django.conf.urls import patterns, url
from cancionero.models import Song
from cancionero import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^/addSong$', views.addSong,  name='addSong'),
)


