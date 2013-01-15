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
    """Simple command-line to zmq client for pyzm-player"""
    context = None
    sender  = None
    server  = None
    poller  = None
    port    = None

    def __init__(self, server, port):
        self.server  = server
        self.port    = port
        self.context = zmq.Context()
        self.sender  = self.context.socket(zmq.REQ)
        self.sender.connect('tcp://%s:%d' % (server,port))
        self.poller  = zmq.Poller()
        self.poller.register(self.sender, zmq.POLLIN)
        self.poller.register(sys.stdin, zmq.POLLIN)
        self.pending_acks = 0

    def __enter__(self):
        return self

    def __del__(self):
        """ Cleanup zmq stuff if any exists """
        print "Terminating client..."
        if(self.context != None):
            logging.debug('Cleaning up zmq')
            if(self.sender != None):
                logging.debug('Closing sender socket...')
                self.sender.close()
            logging.debug('Terminating zmq context')
            self.context.term()
            logging.debug('zmq cleanup completed!')

    def quit(self,force=False):
        # cleanup is performed by self.__del__()
        if(force):
            logging.debug('Discarding pending answers')
            self.sender.setsockopt(zmq.LINGER,0)
        sys.exit(0)

    def send(self,cmd_name,args=[]):
        try:
            msg = shared.json_client_enc(cmd_name,args)
            try:
                self.sender.send(msg, copy=True)
                self.pending_acks+=1
            except Exception as e:
                logging.error('Failed to send "%s" via zmq!'\
                                  'Exception:%s' % (msg,e.__str__()))
        except Exception as e:
            logging.error('Failed encode json msg. Exception:%s' % e.__str__())

    def recv(self):
        ans = []
        try:
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
            logging.error('recv(): %s' % e.__str__())
        return ans

    def send_recv(self,cmd_name,args=[]):
        try:
            self.send(cmd_name,args)
            self.recv()
        except Exception as e:
            print e

    def run(self):
        quit_cmd = 'qqq'
        quit_linger = 'qqqq'
        print "Will send stdin via zmq.\n"\
            "Example:\n"\
            "\tplay file:///tmp/audio1.mp3,file:///tmp/audio2.mp3\n"\
            "\tstop\n\n"\
            "To quit type: %s" % quit_cmd
        while True:
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