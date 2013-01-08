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
from time import sleep
from urllib2 import urlopen
import threading

import zmq

class GstListener(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        threading.Thread.__init__(self, group=group, target=target,
                                  name=name, verbose=verbose)
        self.args   = args
        self.kargs  = kwargs

        # don't know how to get out of self.loop.run(), so just die
        # when everybody else dies
        self.daemon = True
        return
    def run(self):
        self.gstBus = self.args[0]
        self.cb  = self.args[1]
        self.gstBus.add_signal_watch()
        self.gstBus.connect('message', self.cb)
        self.loop = gobject.MainLoop()
        gst.info('Running gst listener thread')
        self.loop.run()

class GstPlayer():
    def __init__(self):
        self.playing = False
        self.player  = gst.element_factory_make("playbin", "player")
        self.bus     = self.player.get_bus()
#        self.on_eos = False

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.stop()
        elif t == gst.MESSAGE_EOS:
            gst.info("File playback completed")
            self.stop()
            # if(self.queued):
            #     self.play()

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

class Listener(threading.Thread):
    """Listen on src (zmq or stdin) for incomming commands"""
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        threading.Thread.__init__(self, group=group, target=target,
                                  name=name, verbose=verbose)
        self.args  = args
        self.kargs = kwargs
        self.stop_request = threading.Event()
        return

    def run(self):
        # arg list: cb,src,port=555
        assert(len(self.args) == 3)
        self.threadID = 1
        self.cb       = self.args[0]
        self.src      = self.args[1]
        self.port     = self.args[2]
        self.context  = None
        self.server   = None
        self.name     = 'Listener'

        gst.debug('%s listener thread starting....' % self.src)
        if self.src == 'zmq':
            # zmq_init
            self.context = zmq.Context()
            self.server  = self.context.socket(zmq.REP)
            self.server.bind('tcp://*:%d' % self.port)
            print 'zmq listener running on port %d' % self.port
        # run loop
        while not self.stop_request.is_set():
            gst.info('Waiting for %s input...' % self.src)
            if(self.src == 'zmq'):
                msg = self.server.recv()
                self.server.send('ack')
            else:
                msg = raw_input('Command:')
            gst.info('Rx: %s' % msg)
            self.cb(msg)
            gst.debug('Callback exe completed')

    def __del__(self):
        gst.debug('Listener thread finished')

    def join(self, timeout=None):
        # zmq_deinit
        self.stop_request.set()
        if self.context != None:
            gst.debug('Cleaning up zmq')
            if self.server != None:
                self.server.close()
            self.context.term()

class PlayerControl():
    """
PlayerControl is plays mp3 files.
Receives commands over zmq or stdin.
Usage example:
      pl = PlayerControl('zmq',5556)
      pl.start()
      # now run a client and send commands, loop
      # until client sends 'quit'.
      while pl.is_alive():
        sleep(0.5)
    """
    handlers = None
    # queued = False

    # zmq variables
    port    = None
    context = None
    server  = None
    src     = None

    def __init__(self, src, port=5555, verify_on_load=False):
        self.port           = port
        self.src            = src
        self.verify_on_load = verify_on_load
        self.player         = GstPlayer()
        self.gst_listener   = GstListener(args=(self.player.bus, self.player.on_message),kwargs=[])
        self.listener       = Listener(args=(self.handle_cmd, self.src, self.port),kwargs=[])

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
        gst.debug("Terminating server...")

    def register(self, event, callback):
        self.handlers[event].add(callback)

    def fire(self, event, **kwargs):
        for handler in self.handlers.get(event, []):
            handler(**kwargs)

    def load_file(self, location):
        if not gst.uri_is_valid(location):
            gst.error("Error: Invalid URI: %s\nExpected uri"
                      "like file:///home/foo/bar.mp3\nIgnoring...\n" % location)
        else:
            # if(self.player.is_playing()):
            #     self.queued = True
            ok   = True
            code = 0
            msg  = ''
            if self.verify_on_load:
                gst.debug('Attempting to verify %s' % location)
                if location[0:4] == 'file':
                    try:
                        with open(location[8:]) as f: pass
                    except IOError as e:
                        ok   = False
                        code = e.errno
                        msg  = e.strerror
                elif location[0:4] == 'http':
                    ans  = urlopen(location)
                    code = ans.code
                    msg  = ans.msg
                    if code >= 400:
                        ok = False
                if ok:
                    gst.debug('Verification succeeded!')
            if not ok:
                gst.warning('Failed to find %s\nWill not load. Error: %d - %s' % (location,code,msg))
            else:
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

    def start(self):
        """Starts listener threads for both gst and src (stdin,zmq)"""
        # start gst_listener thread
        self.gst_listener.start()
        # start input listener thread
        self.listener.start()

    def is_alive(self):
        """Returns true if both gst and src listener threads are alive"""
        return self.gst_listener.is_alive() and self.listener.is_alive()

    def quit(self):
        """Trigger join() on listener thread to make it terminate"""
        gst.debug('Triggering join() on %s listener thread...' % self.src)
        self.listener.join()
        # don't wait, quit() is a callback within listener thread, it will
        # never finish if we wait here.

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
    verify    = False

    # parse command line arguments
    # note: Cannot use -h/--help with gst:
    #           - https://bugzilla.gnome.org/show_bug.cgi?id=625211 
    #           - https://bugzilla.gnome.org/show_bug.cgi?id=549879
    arg_list = argv[1:]
    try:
        opts, args = getopt.getopt(arg_list, "ip:f:l:v", ["i", "port=", "file=", "listen=", "verify"])
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
        elif opt in ("-v", "--verify"):
            verify = True

    pl = PlayerControl(listen,port,verify)

    if(file_name != None):
        pl.load_file(file_name)

    print 'Starting PlayerControl...'
    pl.start()

    print 'Waiting...'
    while pl.is_alive():
        sleep(0.5)
    if(not pl.listener.is_alive()):
        gst.debug('%s listener thread died, terminating...' % pl.src)
    if(not pl.gst_listener.is_alive()):
        gst.debug('gst_listener thread died, terminating...')

    gst.debug('Gracefully finishing...')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
