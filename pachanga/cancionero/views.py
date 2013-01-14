from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.template import Context, loader
from django.views.decorators.csrf import csrf_exempt

import cancionero.shared as shared
import logging
import zmq
from cancionero.models import Song

def index(request):
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
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
  
    #Comunicacion con el player
    url = request.POST.get('url')
    print "URL: ",url
    context = zmq.Context()
    sender  = context.socket(zmq.REQ)
    sender.connect('tcp://%s:%d' % ("127.0.0.1",5555 ))
    
    
    msg = shared.json_client_enc("queue_add", [url])
    print "MENSAJE: ", msg
    try:
	sender.send(msg, copy=True)
    except Exception as e:
	logging.error('Failed to send "%s" via zmq!'\
			  'Exception:%s' % (msg,e.__str__()))

    ack = sender.recv()
    logging.debug('Raw data:%s' % ack)
    
    sender.close()
    context.term()
    #fin coso player
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
    
@csrf_exempt
def play(request):
  
    #Comunicacion con el player

    context = zmq.Context()
    sender  = context.socket(zmq.REQ)
    sender.connect('tcp://%s:%d' % ("127.0.0.1",5555 ))
    print "PLAY"
    msg = shared.json_client_enc("play")
    try:
	sender.send(msg, copy=True)
    except Exception as e:
	logging.error('Failed to send "%s" via zmq!'\
			  'Exception:%s' % (msg,e.__str__()))
    
    
    ack = sender.recv()
    logging.debug('Raw data:%s' % ack)
    
    sender.close()
    context.term()
    #fin coso player
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))

@csrf_exempt
def stop(request):
  
    #Comunicacion con el player

    context = zmq.Context()
    sender  = context.socket(zmq.REQ)
    sender.connect('tcp://%s:%d' % ("127.0.0.1",5555 ))
    print "STOP"
    msg = shared.json_client_enc("stop")
    try:
	sender.send(msg, copy=True)
    except Exception as e:
	logging.error('Failed to send "%s" via zmq!'\
			  'Exception:%s' % (msg,e.__str__()))
    
    
    ack = sender.recv()
    logging.debug('Raw data:%s' % ack)
    
    sender.close()
    context.term()
    #fin coso player
       
    
    song_list = Song.objects.all()
    template = loader.get_template('cancionero/index.html')
    context = Context({
        'song_list': song_list,
    })
    return HttpResponseRedirect(reverse('cancionero:index'))
