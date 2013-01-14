#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# for mainloop in listeners
import gobject
gobject.threads_init()

# python gstreamer bindings
import gst

# callbacks are organized in dict
import collections

# input parsing
import getopt

# __main__ keep alive is based on polling to
# check is listener threads are alive, sleep
# between polls
from time import sleep
# to exit __main__
import sys

# enables verification of url
from urllib2 import urlopen
# enables verification of local files
import os

# used for:
#   - gst,zmq listeners,
#   - bg metadata lookup
import threading

# metadata reading
import tagget

# server-client communication
import zmq

# server-client msg builder, defs, etc
import shared

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
    def __init__(self, cb_eos=None):
        self.playing = False
        self.player  = gst.element_factory_make("playbin", "player")
        self.bus     = self.player.get_bus()
        self.cb_eos = cb_eos if not None else self.stop()

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.stop()
        elif t == gst.MESSAGE_EOS:
            gst.info("File playback completed")
            ok,moved = self.cb_eos()
            if ok:
                gst.debug('eos callback completed, moved queue %d places' % moved)
            else:
                gst.warning('eos callback failed!')
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
        gst.info("playing player. src:%s" % self.get_current)
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

    def get_current(self):
        ans = []
        try:
            ans = self.player.get_property('uri')
        except Exception as e:
            err_msg = 'Failed to get current. Exception:%s' % e.__str__()
            gst.error(err_msg)
        return ans

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
    queue    = None
    queue_pos= None

    # zmq variables
    port    = None
    context = None
    server  = None
    src     = None

    def __init__(self, src, port=5555, verify_on_load=False):
        self.port           = port
        self.src            = src
        self.verify_on_load = verify_on_load
        self.player         = GstPlayer(self.queue_next)
        self.gst_listener   = GstListener(args=(self.player.bus, self.player.on_message),kwargs=[])
        self.listener       = Listener(args=(self.handle_cmd, self.src, self.port),kwargs=[])
        self.queue          = list()
        self.queue_pos      = -1

        # init callbacks
        self.handlers = collections.defaultdict(set)
        self.register('play',self.play)
        self.register('stop',self.stop)
        self.register('status',self.status)
        self.register('queue_add',self.queue_add)
        self.register('queue_del',self.queue_del)
        self.register('queue_get',self.queue_get)
        self.register('queue_clear',self.queue_clear)
        self.register('queue_next',self.queue_next)
        self.register('queue_prev',self.queue_prev)
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

    def queue_add(self, location):
        ans = [200]
        is_dir = False
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
                    path = location[7:]
                    try:
                        with open(path) as f: pass
                    except IOError as e:
                        if e.errno == 21:
                            is_dir = True
                            loaded = []
                            try:
                                # is directory, load content
                                os.chdir(path)
                                for f in os.listdir('.'):
                                    if f.endswith('.mp3'):
                                        full_path = location+'/'+f
                                        res = self.queue_add(full_path)
                                        if res[0] == 200:
                                            loaded.append(full_path)
                                ans.append(loaded)
                            except IOError as e:
                                err_msg = 'Error parsing directory, will'\
                                    'stop loading, exception:%s' % e.__str__()
                                gst.error(err_msg)
                                ans = [404]
                                ans.append(err_msg)
                        else:
                            err_msg = 'Will not load, exception when opening'\
                                '%s: %s' % (path,e.__str__())
                            gst.error(err_msg)
                            ans = [404]
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
            elif not is_dir:
                gst.debug('Setting location to %s' % location)
                try:
                    if location in self.queue:
                        gst.info('Duplicate entry %s' % location)
                    self.queue.append({'uri':location,'tags':{}})
                    try:
                        gst.debug('will prepare tag getter: get_tags(%s)' % location)
                        tgt = threading.Thread(target=tagget.get_tags,
                                               args=[self.queue[-1]['tags'],
                                                     location])
                        gst.debug('will start tag getter')
                        tgt.start()

                    except Exception as e:
                        err_msg = 'Problem near tag get thread. Exception:%s' % e.__str__()
                        gst.warning(err_msg)
                    # call to print current queue
                    self.queue_get()
                    if self.queue_pos == -1:
                        gst.debug('New queue, will next()')
                        ans_n = self.queue_next()
                        if ans_n[0] == 200:
                            gst.debug('New queue play success!')
                        else:
                            ans = [400]
                            ans.append('Failed to set initial queue position')
                except Exception as e:
                    print e
                    ans = [400]
                    gst.error('Problem near queue.append()')
        return ans

    def queue_item_by_uri(self,uri):
        try:
            elem = (item for item in self.queue if item['uri'] == uri).next()
        except StopIteration as e:
            err_msg = 'Exception:%s' % e.__str__()
            return False
        return elem

    def queue_del(self,uri=None,pos=-1):
        """Remove an item from the queue. Item can be selected
        either by URI or by pos (position) in the queue.

        Removing the currently playing element will not stop playback.
        """
        ans = [200]
        ind = -1
        if uri:
            try:
                elem = self.queue_item_by_uri(uri)
                self.queue.index(elem)
                self.queue.remove(uri)
                ans.append('Removed element %s' % uri)
            except (ValueError, StopIteration) as e:
                err_msg = 'Exception:%s' % e.__str__()
                gst.warning(err_msg)
                ans = [400]
                ans.append(err_msg)
        elif pos >= 0:
            try:
                ind = pos
                del self.queue[pos]
                ans.append('Removed element at queue[%d]' % pos)
            except IndexError as e:
                err_msg = 'Failed to remove at %d. Exception:%s' % (pos,e.__str__())
                gst.warning(err_msg)
                ans = [400]
                ans.append(err_msg)
        try:
            if ans[0] == 200:
                if ind < self.queue_pos:
                    # update queue_pos to new queue size
                    self.queue_pos -= 1
                elif ind == self.queue_pos:
                    # check if currently selected item was deleted
                    if not ind and self.queue:
                        # special case, first element was removed and
                        # more are left, set queue_pos to head
                        self.queue_pos = 0
                    if self.queue_pos >= 0:
                        uri_new = self.queue[self.queue_pos]['uri']
                        get.debug('setting uri to %s' % uri_new)
                        self.player.set_location(uri_new)
                    else:
                        # queue is empty now
                        self.player.set_location(None)
        except Exception as e:
            print e
            err_msg = 'Problem near update queue_pos. Exception:%s' % e.__str__()
            gst.error(err_msg)
            ans = [400]
            ans.append(err_msg)
        if ans[0] == 200 and len(ans) > 1:
            # call to get debug output
            self.queue_get()
        return ans

    def queue_get(self):
        ans = [200]
        try:
            uris = []
            for elem in self.queue:
                uris.append(elem['uri'])
            gst.debug('Current queue:\n\t%s' % '\n\t'.join(uris))
            ans.append(uris)
        except Exception as e:
            err_msg = 'Problem in queue_get. Exception:%s' % e.__str__()
            gst.debug(err_msg)
            ans = [400]
            ans.append(err_msg)
        return ans

    def queue_clear(self):
        ans = [200]
        try:
            self.queue_pos = -1
            self.queue[:] = []
            gst.debug('queue cleared')
            self.queue_get()
        except Exception as e:
            err_msg = 'Problem near queue_clear. Exception:%s' % e.__str__()
            gst.debug(err_msg)
            ans = [400]
            ans.append(err_msg)
        return ans

    def queue_next(self,step=1):
        """Wrapper for client call to next(), adds client-server
        protocol overhead"""
        ans = [400]
        try:
            gst.debug('Will next_prev(%d)' % step)
            ok,moved = self.next_prev(step)
            gst.debug('next_prev(%d) returned (%f,%d)' % (step,ok,moved))
            if ok:
                ans = [200]
                ans.append(moved)
        except Exception as e:
            print e
            gst.error('Problem near queue_next()')
        return ans

    def queue_prev(self,step=-1):
        ans = [400]
        if step >= 0:
            return ans
        try:
            ok,moved = self.next_prev(step)
            if ok:
                ans = [200]
                ans.append(moved)
        except Exception as e:
            print e
            gst.error('Problem near queue_prev()')
        return ans

    def next_prev(self, step):
        """Move queue step positions (next,back)
        Returns a tuple (ok,queue_moved), where
        the value queue_moved indicates number of postions
        shifted by queue_move(), and is valid only if ok==True
        """
        ans         = False
        queue_moved = 0
        if(step == 0):
            # come on...
            return ans,queue_moved
        elif not self.queue:
            # queue is empty
            gst.debug('queue is empty')
            ans = True
            return ans,queue_moved
        try:
            queue_pos_old   = self.queue_pos
            queue_pos_new   = self.queue_pos + step
            queue_finished  = False
            # Verify index is within limits, stop if out of boundries
            # This is the typical behaviour of mp3 playing software
            # such as Rhythmbox.
            if queue_pos_new < 0 or queue_pos_new >= len(self.queue):
                gst.debug('queue playback completed, will stop and return to first element')
                # queue completed, stop player and return
                queue_pos_new  = 0
                queue_finished = True
            queue_moved = abs(queue_pos_new - queue_pos_old)

            uri_new = self.queue[queue_pos_new]['uri']
            gst.debug('Will set new location to %s' % uri_new)
            self.player.set_location(uri_new)
            # update queue position
            self.queue_pos = queue_pos_new
            gst.debug('New queue_pos:%d/%d' % (self.queue_pos, len(self.queue)))
            try:
                if(self.is_playing()):
                    gst.debug('Will stop+play to advance in queue')
                    self.stop()
                    if queue_finished:
                        gst.debug('Omiting play(), queue finished')
                    else:
                        self.play()
                # Mark success
                ans = True
            except Exception as e:
                print e
                gst.error('Failed to advance in queue')
        except Exception as e:
            print e
            gst.error('Problem near next()')
        return ans,queue_moved

    def play(self):
        ans = [200]
        try:
            if self.is_playing():
                gst.debug('Will pause player')
                self.player.pause()
            else:
                gst.debug('Will play player')
                self.player.play()
        except Exception as e:
            err_msg = 'Problem near play. Exception:%s' % e.__str__()
            ans = [400]
            ans.append(err_msg)
        return ans

    def stop(self):
        """Wrapper for player.stop()"""
        ans = [200]
        try:
            gst.debug('Will stop player')
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
            gst.debug(self.queue.__str__())
            playing = self.is_playing()
            current = self.player.get_current()
            tags    = self.queue_item_by_uri(current)
            if not tags:
                # Failed to find tags or search is still
                # in progress
                tags = {}
            ans.append([playing,current,tags])
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

    def handle_cmd(self, msg):
        """Receives a msg and executes it if it corresponds to a registered cmd"""
        if self.src == 'zmq':
            cmd,cmd_code,args = shared.json_server_dec(msg)
            gst.debug('dec: cmd_name=%s,'\
                          'cmd_code=%d,args=%s' % (cmd,cmd_code,args.__str__()))
        else:
            words       = msg.split()
            cmd         = words[0]
            cmd_code    = words[-1]
            args        = []
        cmd_code_dic= 0
        ans         = [200] # default to OK

        if not self.is_registered(cmd) or (self.src == 'stdin' and len(words) < 2):
            gst.error("Error: Invalid command: %s, Ignoring...\n" % cmd)
            help_msg = self.help_msg()
            if(self.src == 'stdin'):
                print help_msg
            ans = [401]
            ans.append(help_msg)
        else:
            # first arg is command name, last is cmd if
            if self.src == 'stdin':
                # if src is zmq, then json_server_dec() took
                # care of fetching arguments for command
                args = words[1:-1]
                try:
                    # convert from string to int
                    cmd_code = int(cmd_code)
                except ValueError as e:
                    gst.warning('int(cmd_code) failed!Exception:%s' % e.__str__())
            try:
                # get command id from dict, compare with rx id (must match)
                gst.debug('Matching command id with dict values...')
                cmd_code_dic = shared.cmd_name_id[cmd]
                try:
                    # check matching
                    if cmd_code_dic != cmd_code:
                        gst.error('Command code received %d does not match dict %d'
                                    % (cmd_code,cmd_code_dic))
                    else:
                        gst.debug('Command id matched!')
                    try:
                        if(args):
                            gst.debug('Executing cmd=%s with args=%s' % (cmd,args))
                            args = args[0]
                            if cmd == 'queue_add':
                                ans = list(self.queue_add(args))
                            elif cmd == 'queue_del':
                                param = -1
                                try:
                                    param = int(args)
                                except ValueError as e:
                                    gst.debug('Param is not int. Exception:%s' % e.__str__())
                                if not param == -1:
                                    ans = list(self.queue_del(pos=param))
                                else:
                                    ans = list(self.queue_del(uri=args))
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
        return shared.json_server_enc(cmd_code, ans[0], data)

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
