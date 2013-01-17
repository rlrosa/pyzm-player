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

SERVER_PORT = 5555
SERVER_IP   = "127.0.0.1"

def getContext():
    global SERVER_PORT, SERVER_IP
    cl = PyzmClient(SERVER_IP, SERVER_PORT)
    # get context info
    playing, song_curr = getCurrentSong(cl)
    song_list          = getCurrentPlaylist(cl)
    song_DB = Song.objects.all()
    context = Context({
        'song_list'  : song_list,
        'song_DB'    : song_DB,
        'song_curr'  : song_curr,
        'playing'    : playing,
    })
    return context

def getCurrentSong(cl=None):
    playing = False
    song_curr = Song()
    if not cl:
        cl = PyzmClient(SERVER_IP, SERVER_PORT)

    ans = cl.send_recv("status")
    if ans[0] == 200:
        try:
            playing = ans[2][0]
        except (IndexError) as e:
            logging.warning(e)
        try:
            song_curr.title = ans[2][2]['tags']['title']
        except (KeyError,IndexError) as e:
            logging.warning(e)
        try:
            song_curr.artist = ans[2][2]['tags']['artist']
        except (KeyError,IndexError) as e:
            logging.warning(e)
        try:
            song_curr.genre = ans[2][2]['tags']['genre']
        except (KeyError,IndexError) as e:
            logging.warning(e)
        try:
            song_curr.album = ans[2][2]['tags']['album']
        except (KeyError,IndexError) as e:
            logging.warning(e)
        try:
            song_curr.url = ans[2][2]['uri']
        except (KeyError,IndexError) as e:
            logging.warning(e)

    return playing,song_curr

def getCurrentPlaylist(cl=None):
    song_list = []
    if not cl:
        cl = PyzmClient(SERVER_IP, SERVER_PORT)
    ans = cl.send_recv("queue_get")
    index = 0
    if ans[0] == 200:
        logging.debug('queue_get ok, analyzing answer')
        for track in ans[2]:
            logging.debug(track)
            uri   = ''
            title  = 'Loading'
            album = 'Loading'
            try:
                uri  = track['uri']
            except KeyError as e:
                logging.info('Incomplete track info for track')
            try:
                title = track['tags']['title']
            except KeyError as e:
                logging.info('Incomplete track info for %s' % uri)
            try:
                album = track['tags']['album']
            except KeyError as e:
                logging.info('Incomplete track info for %s' % uri)
            # save whatever we managed to get (maybe nothing)
            
            aux = [index, "%s - %s" % (title,album)]
            song_list.append(aux)
            index = index + 1
    return song_list

def index(request):
    context = getContext()
    template = loader.get_template('cancionero/base.html')
    return HttpResponse(template.render(context))
  
@csrf_exempt
def addSong(request):
    title   = request.POST.get('title')
    url     = request.POST.get('url')
    artist  = request.POST.get('artist')
    genre   = request.POST.get('genre')
    newSong = Song(title=title, url=url, artist=artist, genre=genre, album='unknown')
    newSong.save()
    template = loader.get_template('cancionero/base.html')
    return HttpResponseRedirect(reverse('cancionero:index'))
    
@csrf_exempt
def addToDbCancel(request):
    template = loader.get_template('cancionero/base.html')
    context = getContext()
    return HttpResponse(template.render(context))
    
@csrf_exempt
def addToPlayList(request):
    #listS = request.POST['song_DB'] 
    url = request.POST.get('url')
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_add", [url]);
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
    
@csrf_exempt
def removeFromPL(request):
  
    listS = request.POST.getlist('songsList')
    cl = PyzmClient("127.0.0.1", 5555)
    for s in listS:
      print "rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr:", s
      cl.send_recv("queue_del", s);      
      
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
    
@csrf_exempt
def dbToPlayList(request):
    listS = request.POST.getlist('song_DB')
    

    cl = PyzmClient("127.0.0.1", 5555)
    for s in listS:
      songToPl = Song.objects.get(pk=s)
      cl.send_recv("queue_add", [songToPl.url]);
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
 
 
@csrf_exempt
def queueClear(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_clear");
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
 
 
@csrf_exempt
def play(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("play")
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def stop(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("stop");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
    
@csrf_exempt
def nextSong(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_next");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def prev(request):
  
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_prev");
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/base.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def addToDb(request):
    context = getContext()
    template = loader.get_template('cancionero/base_addToDb.html')
    return HttpResponse(template.render(context))
