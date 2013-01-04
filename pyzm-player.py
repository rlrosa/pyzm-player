#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import pygtk
pygtk.require('2.0')

import sys

import gobject
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

import collections

class GstPlayer:
    def __init__(self):
        self.playing = False
        self.player = gst.element_factory_make("playbin", "player")
#        self.on_eos = False

        bus = self.player.get_bus()
#        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        # bus.connect('sync-message::element', self.on_sync_message)
        bus.connect('message', self.on_message)
        bus.connect('message::eos',self.on_message)
        bus.connect('message::error',self.on_message)

    # def on_sync_message(self, bus, message):
    #     if message.structure is None:
    #         return
    #     if message.structure.get_name() == 'prepare-xwindow-id':
    #         # Sync with the X server before giving the X-id to the sink
    #         gtk.gdk.threads_enter()
    #         gtk.gdk.display_get_default().sync()
    #         self.videowidget.set_sink(message.src)
    #         message.src.set_property('force-aspect-ratio', True)
    #         gtk.gdk.threads_leave()
            
    def on_message(self, bus, message):
        t = message.type
        print 'Message received'
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
#            if self.on_eos:
#                self.on_eos()
            self.playing = False
        elif t == gst.MESSAGE_EOS:
            print "File playback completed"
#            if self.on_eos:
#                self.on_eos()
            self.stop()
            if(self.queded):
                self.play()

    def set_location(self, location):
        print "Loading %s", location
        self.player.set_property('uri', location)

    def query_position(self):
        "Returns a (position, duration) tuple"
        try:
            position, format = self.player.query_position(gst.FORMAT_TIME)
        except:
            position = gst.CLOCK_TIME_NONE

        try:
            duration, format = self.player.query_duration(gst.FORMAT_TIME)
        except:
            duration = gst.CLOCK_TIME_NONE

        return (position, duration)

    # def seek(self, location):
    #     """
    #     @param location: time to seek to, in nanoseconds
    #     """
    #     gst.debug("seeking to %r" % location)
    #     event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
    #         gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
    #         gst.SEEK_TYPE_SET, location,
    #         gst.SEEK_TYPE_NONE, 0)

    #     res = self.player.send_event(event)
    #     if res:
    #         gst.info("setting new stream time to 0")
    #         self.player.set_new_stream_time(0L)
    #     else:
    #         gst.error("seek to %r failed" % location)

    def pause(self):
        gst.info("pausing player")
        self.player.set_state(gst.STATE_PAUSED)
        self.playing = False

    def play(self):
        gst.info("playing player")
        self.player.set_state(gst.STATE_PLAYING)
        self.playing = True

    def stop(self):
        self.player.set_state(gst.STATE_NULL)
        gst.info("stopped player")
        self.playing = False

    def get_state(self, timeout=1):
        return self.player.get_state(timeout=timeout)

    def is_playing(self):
        return self.playing

class PlayerControl():
    handlers = None
    queded = False

    def __init__(self):

        self.player = GstPlayer()

        def on_eos():
            self.player.seek(0L)
            self.play_toggled()
        self.player.on_eos = lambda *x: on_eos()

        self.p_position = gst.CLOCK_TIME_NONE
        self.p_duration = gst.CLOCK_TIME_NONE

        def on_delete_event():
            self.player.stop()

        # init callbacks
        self.handlers = collections.defaultdict(set)
        self.register('play',self.play_toggled)
        self.register('stop',self.player.stop)
        self.register('is_playing',self.is_playing)
        self.register('quit',self.quit)
        self.register('help',self.help)

    def register(self, event, callback):
        self.handlers[event].add(callback)

    def fire(self, event, **kwargs):
        for handler in self.handlers.get(event, []):
            handler(**kwargs)

    def load_file(self, location):
        if not gst.uri_is_valid(location):
            sys.stderr.write("Error: Invalid URI: %s\nExpected uri"
                             "like file:///home/foo/bar.mp3\nIgnoring...\n" % location)
        else:
            if(self.player.is_playing()):
                self.player.queued = True
            self.player.set_location(location)

    def play_toggled(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def is_playing(self):
        playing = self.player.is_playing()
        print "Player state: %s" % "Playing" if playing else "NOT Playing"
        return playing

    def scale_button_press_cb(self, widget, event):
        gst.debug('starting seek')

        self.was_playing = self.player.is_playing()
        if self.was_playing:
            self.player.pause()

    def help(self):
        print "\n-- Help menu --\n\nValid commands:"
        for k,v in self.handlers.items():
            print "\t%s" % k

    def is_registered(self, cmd):
        return cmd in self.handlers

    def quit(self):
         sys.exit(0)

def main(args):
    def usage():
        sys.stderr.write("usage: %s URI-OF-MEDIA-FILE\n" % args[0])
        sys.exit(1)

    pl = PlayerControl()

    if len(args) != 2:
        usage()

    pl.load_file(args[1])

    # input loop
    cmd = 0
    arg = 0
    while(cmd >= 0):
        line = raw_input('Command:')
        words = line.split()
        in_len = len(words)
        if in_len == 2 and words[0] == 'load':
            # must be new file
            new_file = words[1]
            if (gst.uri_is_valid(new_file)):
                # load new file
                pl.load_file(new_file)
            else:
                sys.stderr.write("Error: Invalid URI: %s\nIgnoring..." % new_file)
        elif (in_len == 1):
            # update command (play, pause, etc)
            cmd = words[0]
            if not pl.is_registered(cmd):
                sys.stderr.write("Error: Invalid command: %s, Ignoring...\n" % cmd)
                pl.help()
            else:
                pl.fire(cmd)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
