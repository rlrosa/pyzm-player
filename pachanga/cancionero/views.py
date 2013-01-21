from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.template import Context, loader, RequestContext
from django.views.decorators.csrf import csrf_exempt

from django_socketio import broadcast, broadcast_channel, NoSocket

import cancionero.shared as shared
import logging
import zmq
from pyzm_client import PyzmClient
from cancionero.models import Song

# get function name from within function
import inspect

SERVER_PORT = 5555
SERVER_IP   = "127.0.0.1"

def buildContextDir():
    global SERVER_PORT, SERVER_IP
    cl = PyzmClient(SERVER_IP, SERVER_PORT)
    # get context info
    playing, song_curr,ans = getCurrentSong(cl)
    if ans[0] == 407:
        # timed out waiting for server
        song_list = []
    else:
        song_list              = getCurrentPlaylist(cl)
    song_DB = Song.objects.all()
    cdir = {
        'song_list'  : song_list,
        'song_DB'    : song_DB,
        'song_curr'  : song_curr,
        'playing'    : playing,
        }
    if ans[0] == 407:
        cdir['server_ok'] = False
    else:
        cdir['server_ok'] = True
    return cdir

def buildContext():
    cdir = buildContextDir()
    context = Context(cdir)
    return context

def updateContext(request):
    new_cdir = buildContextDir()
    context = RequestContext(request)
    context.update(new_cdir)
    return context

def getCurrentSong(cl=None):
    playing = False
    song_curr = Song()
    if not cl:
        cl = PyzmClient(SERVER_IP, SERVER_PORT)

    ans = cl.send_recv("status",timeout=1000)
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

    return playing,song_curr,ans

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
    context = updateContext(request)
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
    return HttpResponseRedirect(reverse('cancionero:index'))

# @csrf_exempt
# def addToDbCancel(request):
#     context = updateContext(request)
#     template = loader.get_template('cancionero/base.html')
#     return HttpResponse(template.render(context))

@csrf_exempt
def addToPlayList(request):
    #listS = request.POST['song_DB'] 
    url = request.POST.get('url')
    cl = PyzmClient("127.0.0.1", 5555)
    ans = cl.send_recv("queue_add", [url]);
    if not ans[0] == 200:
        context = updateContext(request)
        context['fail'] = {'err_code':ans[0],
                           'err_msg':shared.r_codes[ans[0]],
                           'func':inspect.stack()[0][3]}
        template = loader.get_template('cancionero/base.html')
        return HttpResponse(template.render(context))
    else:
        return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def removeFromPL(request):
    listS = request.POST.getlist('songsList')
    cl = PyzmClient("127.0.0.1", 5555)
    for s in listS:
      print "rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr:", s
      cl.send_recv("queue_del", s);
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def dbToPlayList(request):
    listS = request.POST.getlist('song_DB')

    cl = PyzmClient("127.0.0.1", 5555)
    for s in listS:
      songToPl = Song.objects.get(pk=s)
      cl.send_recv("queue_add", [songToPl.url]);
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def queueClear(request):
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_clear");
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def play(request):
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("play")
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def stop(request):
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("stop");
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def nextSong(request):
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_next");
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def prev(request):
    cl = PyzmClient("127.0.0.1", 5555)
    cl.send_recv("queue_prev");
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def addToDb(request):
    context = updateContext(request)
    template = loader.get_template('cancionero/base_addToDb.html')
    return HttpResponse(template.render(context))
