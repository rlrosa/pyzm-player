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
import json
import threading

import zmq

# defs, etc
from shared import r_codes,cmd_id_name,cmd_name_id

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
        print "Loading %s" % location
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
            else:
                msg = raw_input('Command:')
            gst.info('Rx: %s' % msg)
            ans = self.cb(msg)
            gst.debug('Callback exe completed')
            if(self.src == 'zmq'):
                self.server.send(ans)
                gst.debug('Answer sent to client: %s' % ans)
        # zmq_deinit
        if self.context != None:
            gst.debug('Cleaning up zmq')
            if self.server != None:
                self.server.close()
            self.context.term()

    def __del__(self):
        gst.debug('Listener thread finished')

    def join(self, timeout=None):
        self.stop_request.set()


class PlayerControl():
    """
PlayerControl plays mp3 files.
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
        self.register('play',self.play)
        self.register('stop',self.stop)
        self.register('status',self.status)
        self.register('load',self.load)
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
            return handler(**kwargs)

    def load(self, location):
        ans = [200]
        if not gst.uri_is_valid(location):
            gst.error("Error: Invalid URI: %s\nExpected uri"
                      "like file:///home/foo/bar.mp3\nIgnoring...\n" % location)
            ans = [403]
        else:
            # if(self.player.status()):
            #     self.queued = True
            gst.debug('URI is valid: %s' % location)
            err_msg = []
            code = 0
            msg  = ''
            if self.verify_on_load:
                gst.debug('Attempting to verify %s' % location)
                if location[0:4] == 'file':
                    try:
                        with open(location[8:]) as f: pass
                    except IOError as e:
                        gst.error('Failed to open %s' % location[8:])
                        ans = [404]
                        err_msg = 'Failed to find %s\nWill not load. Error: %d - %s' % (location,code,msg)
                        ans.append(err_msg)
                elif location[0:4] == 'http':
                    try:
                        urlopen_ans  = urlopen(location)
                        code = urlopen_ans.code
                        msg  = urlopen_ans.msg
                        if code >= 400:
                            err_msg = 'urlopen failed with %d: %s' % (code,msg)
                    except:
                        err_msg = 'urlopen() failed'
                    if err_msg:
                        ans = [400]
                        ans.append(err_msg)
                if not err_msg:
                    gst.debug('Verification succeeded!')
            if err_msg:
                gst.warning(err_msg)
            else:
                gst.debug('Setting location to %s' % location)
                try:
                    self.player.set_location(location)
                except:
                    ans = [400]
        return ans

    def play(self):
        ans = [200]
        try:
            if self.player.status():
                self.player.pause()
            else:
                self.player.play()
        except:
            ans = [400]
        return ans

    def stop(self):
        """Wrapper for player.stop()"""
        ans = [200]
        try:
            self.player.stop()
        except:
            ans = [400]
        return ans

    def is_playing(self):
        """Wrapper for player.is_playing()"""
        playing = False
        try:
            playing = self.player.is_playing()
            if self.src == 'stdin':
                print "Player state: Playing" if playing else "Player state: NOT Playing"
            gst.debug('status:%r' % playing)
        except Exception as e:
            print e
            gst.error('Problem near is_playing()')
        return playing

    def status(self):
        """Get player playing/!playing"""
        #TODO return metadata if playing
        ans = [200]
        try:
            playing = self.is_playing()
            ans.append(True) if playing else ans.append(False)
        except Exception as e:
            print e
            gst.error('Problem near status()')
            ans = [400]
        return ans

    def help(self):
        ans = [200]
        try:
            help_msg = self.help_msg()
            ans.append(help_msg)
        except:
            ans = [400]
        return ans

    def help_msg(self):
        menu  = "\n-- Help menu --\n\nValid commands:\n\t"
        try:
            funcs = '\n\t'.join(self.handlers.keys())
        except:
            gst.error('Failed to build handler list')
            funcs = []
        return "%s%s" % (menu,funcs)

    def is_registered(self, cmd):
        return cmd in self.handlers

    def json_ans(self, cmd_code, res_code, data=[]):
        ans = [
            {
                'ack':
                    {'res_code':res_code,
                     'cmd_code':cmd_code},
                'data':
                    data
             }
            ]
        data_string = json.dumps(ans)
        return data_string

    def handle_cmd(self, msg):
        """Receives a msg and executes it if it corresponds to a registered cmd"""
        words       = msg.split()
        cmd         = words[0]
        cmd_code    = words[-1]
        cmd_code_dic= 0
        args        = []
        ans         = [200] # default to OK

        if not self.is_registered(cmd) or len(words) < 2:
            gst.error("Error: Invalid command: %s, Ignoring...\n" % cmd)
            help_msg = self.help_msg()
            if(self.src == 'stdin'):
                print help_msg
            ans = [401]
            ans.append(help_msg)
        else:
            # first arg is command name, last is cmd if
            args = words[1:-1]
            try:
                # get command id from dict, compare with rx id (must match)
                gst.debug('Matching command id with dict values...')
                cmd_code_dic = cmd_name_id[cmd]
                try:
                    # convert from string to int
                    cmd_code = int(cmd_code)
                    # check matching
                    if cmd_code_dic != cmd_code:
                        gst.error('Command code received %d does not match dict %d'
                                    % (cmd_code,cmd_code_dic))
                    else:
                        gst.debug('Command id matched!')
                    try:
                        if(args):
                            gst.debug('Executing cmd=%s with args=%s' % (cmd,args))
                            assert(cmd == 'load')
                            args = args[0]
                            ans = list(self.load(args))
                            #TODO implement generic multi arg command and support for multi load (queue)
                            # ans = self.fire(cmd,args)
                        else:
                            gst.debug('Executing cmd=%s without args' % cmd)
                            ans = list(self.fire(cmd))
                    except ValueError as ve:
                        print 'Exception:',ve
                    except Exception, e:
                        print 'Exception:',e
                        gst.error('Problem near cmd execution: %s' % msg)
                        ans = [402]
                except Exception as e:
                    print 'Exception:',e
                    gst.error('Problem near command id matching: (rx,dict)=(%d,%d)' % (cmd_code,cmd_code_dic))
            except Exception as e:
                print 'Exception:',e
                gst.error('Problem near: find Id for cmd: %s' % cmd)

        # Take cmd result and prepare answer to send to client
        gst.debug('ans(len=%d)=%s' % (len(ans),ans))
        assert(len(ans) == 1 or len(ans) == 2) # (code, data)
        data = []
        if len(ans) == 2:
            data = ans[1]
        return self.json_ans(cmd_code, ans[0], data)

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
        ans = [200]
        try:
            gst.debug('Triggering join() on %s listener thread...' % self.src)
            self.listener.join()
            # don't wait, quit() is a callback within listener thread, it will
            # never finish if we wait here.
        except:
            ans = [400]
        return ans

def main(argv):

    def usage():
        help_str = "Valid arguments:\n"\
            "\t-f mediaFileUri\t//\t--file=uriOfMediaFile\n"\
            "\t-p portNumber\t//\t--port=portNumber\n"\
            "\t-l [zmq,stdin]\t//\t--listen=[zmq,stdin]\n"\
            "\t-i\t\t//\t--info\n"\
            "\t-v\t\t//\t--verify\n"
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
        pl.load(file_name)

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
