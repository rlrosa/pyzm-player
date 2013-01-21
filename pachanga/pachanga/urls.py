from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^cancionero/', include('cancionero.urls', namespace="cancionero")),
    url(r'', include("django_socketio.urls")),
    url(r'^admin/', include(admin.site.urls)),
)
