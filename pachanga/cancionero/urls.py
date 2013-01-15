from django.conf.urls import patterns, url
from cancionero.models import Song
from cancionero import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^/addSong$', views.addSong,  name='addSong'),
    url(r'^/addToPlayList$', views.addToPlayList,  name='addToPlayList'),
    url(r'^/play$', views.play,  name='play'),
    url(r'^/stop$', views.stop,  name='stop'),
    url(r'^/nextSong', views.nextSong,  name='nextSong'),
    url(r'^/prev', views.prev,  name='prev'),
)


