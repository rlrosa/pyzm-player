#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys
import zmq
import getopt
import logging
import json
import shared

class PyzmClient:
    """
    Simple zmq client for pyzm_player.
    Can be used as a class, manually, or launched as a listener
    for stdin input.

    Example usage in main thread:
      cl = PyzmClient('192.168.0.101',5555)
      cl.send_recv('queue_add',['http:///www.mysite.com/tmp/file.mp3'])
      cl.send_recv('play')
      cl.send_recv('stop')
    Example as cmd line interface:
      cl = PyzmClient('192.168.0.101',5555)
      cl.run()
      # trigger quit from command line
    """
    context = None
    sender  = None
    server  = None
    poller  = None
    port    = None

    def __init__(self, server='127.0.0.1', port=5555):
        self.server  = server
        self.port    = port
        self.context = zmq.Context()
        self.sender  = self.context.socket(zmq.REQ)
        self.sender.connect('tcp://%s:%d' % (server,port))
        self.poller  = zmq.Poller()
        self.poller.register(self.sender, zmq.POLLIN)
        self.pending_acks = 0

    def __enter__(self):
        return self

    def __del__(self):
        """ Cleanup zmq stuff if any exists """
        print "Terminating client..."
        self.quit(force=True)

    def quit(self,force=False):
        # cleanup is performed by self.__del__()
        self.do_run = False
        if force and self.sender != None:
            logging.debug('Discarding pending answers')
            self.sender.setsockopt(zmq.LINGER,0)
        if force or self.pending_acks == 0:
            if(self.context != None):
                logging.debug('Cleaning up zmq')
                if(self.sender != None):
                    logging.debug('Closing sender socket...')
                    self.sender.close()
                    self.sender = None
                    logging.debug('Terminating zmq context')
                    self.context.term()
                    self.context = None
                    logging.debug('zmq cleanup completed!')

    def send(self,cmd_name,args=[]):
        ans = [400]
        if self.pending_acks > 0:
            ans = [408]
        try:
            msg = shared.json_client_enc(cmd_name,args)
            try:
                self.sender.send(msg, copy=True)
                self.pending_acks+=1
                ans = [200]
            except Exception as e:
                ans = [400]
                err_msg = 'Failed to send "%s" via zmq!'\
                    'Exception:%s' % msg,e.__str__()
                ans.append(err_msg)
                logging.error(err_msg)
        except Exception as e:
            ans = [400]
            err_msg = 'Failed encode json msg. Exception:%s' % e.__str__()
            ans.append(err_msg)
            logging.error(err_msg)
        return ans

    def recv(self, timeout=5000):
        ans = []
        try:
            socks = dict(self.poller.poll(timeout))
            if not socks or not socks.get(self.sender, False):
                # did not get answer from server
                logging.error('Timed out waiting for answer from server')
                ans = [407]
                ans.append(shared.r_codes[ans[0]])
                return ans
            logging.debug('Will recv()')
            ack = self.sender.recv()
            logging.debug('Raw data:%s' % ack)
            self.pending_acks-=1
            try:
                cmd_code,cmd_res,data,dec = shared.json_client_dec(ack)
                ans = [cmd_code,cmd_res,data,dec]
                logging.debug('will json.dumps to print data on screen')
                print 'DECODED:',json.dumps(dec,indent=2)
                if data:
                    print 'DATA:',data
            except:
                print 'ERROR: failed to decode json. Raw data:\n%s' % ack
        except Exception as e:
            print e
            logging.error('recv(): %s' % e.__str__())
        return ans

    def send_recv(self,cmd_name,args=[],timeout=5000):
        """
        Will send a command via zmq and wait (blocking)
        for an answer from the client for up to 'timeout'
        miliseconds.

        Arguments:
          - cmd_name: Name of command to execute (see shared.py)
          - args    : List of string to send as arguments to cmd
          - timeout : Max time to wait for answer from player (ms)
        """
        ans = [400]
        try:
            ans = self.send(cmd_name,args)
            if not ans[0] == 200:
                return ans
            ans = self.recv(timeout)
            if not ans[0] == 200:
                return ans
        except Exception as e:
            ans = [400]
            ans.append(e.__str__())
            print e
        return ans

    def run(self):
        quit_cmd = 'qqq'
        quit_linger = 'qqqq'
        self.do_run = True
        self.poller.register(sys.stdin, zmq.POLLIN)

        print "Will send stdin via zmq.\n"\
            "Example:\n"\
            "\tplay file:///tmp/audio1.mp3,file:///tmp/audio2.mp3\n"\
            "\tstop\n\n"\
            "To quit type: %s" % quit_cmd
        while self.do_run:
            socks = dict(self.poller.poll(500))
            if socks:
                if socks.get(self.sender, False):
                    # got message from server
                    ans = self.recv()
                if socks.get(sys.stdin.fileno(), False):
                    # got stdin input
                    line = raw_input('')
                    if line == quit_cmd or line == quit_linger:
                        if(line == quit_linger):
                            self.quit(force=True)
                        if(self.pending_acks==0):
                            self.quit()
                        else:
                            logging.warn('There are %d answers pending, cannot terminate '\
                                'zmq context cleanly.\n'\
                                'Wait for server or force quit by typing "%s"' % (self.pending_acks,quit_linger))
                    elif line:
                        try:
                            unicode(line)
                            words = line.split()
                            cmd_name = words[0]
                            args = []
                            # now fetch args
                            if(len(words) > 1):
                                args = ' '.join(words[1:]).split(',')
                            self.send(cmd_name,args)
                        except UnicodeDecodeError as e:
                            logging.error('Input must be unicode')
                        except Exception as e:
                            logging.error('Exception:' % e.__str__())

def main(argv):
    def usage():
        help_str = "Valid arguments:\n"\
            "\t-p portNumber\t//\t--port=portNumber\n"\
            "\t-s serverIP\t//\t--server=xxx.xxx.xxx.xxx\n"\
            "\t-i\t\t//\t--info\n"
        sys.stderr.write("%s" % help_str)
        sys.exit(1)

    # default values
    port      = 5555
    server    = '*'
    file_name = None
    log_level = logging.WARN

    # parse command line arguments
    arg_list = argv[1:]
    try:
        opts, args = getopt.getopt(arg_list, "ip:s:d", ["info", "port=", "server=", "debug"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-i","--info"):
            usage()
            sys.exit()
        elif opt in ("-p", "--port"):
            port = int(arg)
        elif opt in ("-s", "--server"):
            server = arg
        elif opt in ("-d", "--debug"):
            logging.root.level = logging.DEBUG
            logging.debug('Debug output enabled')

    client = PyzmClient(server,port)
    client.run()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
