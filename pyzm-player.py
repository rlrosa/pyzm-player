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
import getopt

import zmq

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
    """ PlayerControl is plays mp3 files. Receives commands over zmq """
    handlers = None
    queded = False

    # zmq variables
    port    = None
    context = None
    server  = None

    def __init__(self, port):

        self.player  = GstPlayer()
        self.port    = port
        self.context = None
        self.server  = None

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

    def __enter__(self):
        return self

    def __del__(self):
        """ Cleanup zmq stuff if any exists """
        print "Terminating server..."
        self.zmq_deinit()

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

    def handle_cmd(self, msg):
        """Receives a msg and executes it if it corresponds to a registered cmd"""
        words = msg.split()
        in_len = len(words)
        if in_len == 2 and words[0] == 'load':
            # must be new file
            new_file = words[1]
            if (gst.uri_is_valid(new_file)):
                # load new file
                self.load_file(new_file)
            else:
                sys.stderr.write("Error: Invalid URI: %s\nIgnoring..." % new_file)
        elif (in_len == 1):
            # update command (play, pause, etc)
            cmd = words[0]
            if not self.is_registered(cmd):
                sys.stderr.write("Error: Invalid command: %s, Ignoring...\n" % cmd)
                self.help()
            else:
                self.fire(cmd)

    def zmq_init(self):
        self.context = zmq.Context()
        self.server  = self.context.socket(zmq.REP)
        self.server.bind('tcp://*:%d' % self.port)

    def zmq_deinit(self):
        if self.context != None:
            if self.server != None:
                self.server.close()
            self.context.term()

    def run_zmq(self):
        self.zmq_init()
        print 'Server running, listening on zmq port %d...' % self.port
        while True:
            msg = self.server.recv()
            self.server.send('ack')
            self.handle_cmd(msg)

    def run_stdin(self):
        print 'Server running, listening on stdin...'
        # input loop
        cmd = 0
        arg = 0
        while(True):
            line = raw_input('Command:')
            self.handle_cmd(line)

    def quit(self):
        # cleanup is performed by self.__del__()
        sys.exit(0)

def main(argv):

    def usage():
        help_str = "Valid arguments:\n"\
            "\t-f mediaFileUri\t//\t--file=uriOfMediaFile\n"\
            "\t-p portNumber\t//\t--port=portNumber\n"\
            "\t-l [zmq,stdin]\t//\t--listen=[zmq,stdin]\n"\
            "\t-i\t\t//\t--info\n"
        sys.stderr.write("%s" % help_str)
        sys.exit(1)

    # default values
    port      = 5555
    file_name = None
    listen    = 'zmq'

    # parse command line arguments
    # note: Cannot use -h/--help with gst:
    #           - https://bugzilla.gnome.org/show_bug.cgi?id=625211 
    #           - https://bugzilla.gnome.org/show_bug.cgi?id=549879
    arg_list = argv[1:]
    try:
        opts, args = getopt.getopt(arg_list, "ip:f:l:", ["i", "port=", "file=", "listen="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-i","--info"):
            usage()
            sys.exit()
        elif opt in ("-p", "--port"):
            port = int(arg)
        elif opt in ("-f", "--file"):
            file_name = arg
        elif opt in ("-l", "--listen"):
            listen = arg

    pl = PlayerControl(port)

    if(file_name != None):
        pl.load_file(file_name)

    if listen == 'stdin':
        pl.run_stdin()
    else:
        pl.run_zmq()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
