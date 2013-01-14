from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.template import Context, loader
from django.views.decorators.csrf import csrf_exempt


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
    
    



