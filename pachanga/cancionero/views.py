from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.template import Context, loader
from django.views.decorators.csrf import csrf_exempt

import cancionero.shared as shared
import logging
import zmq
from pyzm_client import PyzmClient
from cancionero.models import Song

def index(request):
    
    cl = PyzmClient("127.0.0.1", 5555)
    
    ans = cl.send_recv("queue_get")
    song_list = []
    for track in ans[2]:
      song_list.insert(0, track['tags']['title'])
    
    ans = cl.send_recv("status")
    song_title = ans[2][2]['tags']['title']
    song_artist = ans[2][2]['tags']['artist']
    song_genre = ans[2][2]['tags']['genre']
    song_album = ans[2][2]['tags']['album']
    
    song_DB = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
        'song_DB': song_DB,
        'song_title': song_title,
        'song_artist': song_artist,
        'song_genre': song_genre,
        'song_album': song_album,
    })
    return HttpResponse(template.render(context))
  
@csrf_exempt
def addSong(request):
    name = request.POST.get('name')
    url = request.POST.get('url')
    author = request.POST.get('author')
    style = request.POST.get('style')
    newSong = Song(songName=name, songSource=url, songAuthor=author, songStyle=style)
    newSong.save()
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
    
@csrf_exempt
def addToPlayList(request):
  
    url = request.POST.get('url')
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_add", [url]);
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
@csrf_exempt
def play(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("play")
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def stop(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("stop");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
    
@csrf_exempt
def nextSong(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_next");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def prev(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_prev");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
