#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys
import zmq
import getopt

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

    def __enter__(self):
        return self

    def __del__(self):
        """ Cleanup zmq stuff if any exists """
        print "Terminating client..."
        if(self.context != None):
            if(self.sender != None):
                self.sender.close()
            self.context.term()

    def quit(self):
        # cleanup is performed by self.__del__()
        sys.exit(0)

    def run(self):
        quit_cmd = 'qqq'
        pending_acks = 0
        print "Will send stdin via zmq.\nTo quit type: %s" % quit_cmd
        while True:
            socks = dict(self.poller.poll(500))
            if socks:
                if socks.get(self.sender, False):
                    # got message from server
                    ack = self.sender.recv()
                    print 'recv(): %s' % ack
                    pending_acks-=1
                if socks.get(sys.stdin.fileno(), False):
                    # got stdin input
                    line = raw_input('')
                    if line == quit_cmd:
                        if(pending_acks==0):
                            self.quit()
                        else:
                            logging.warn('There are %d answers pending, cannot terminate '\
                                'zmq context cleanly.\n'\
                                'Wait for server or force quit by pressing Ctrl+C' % pending_acks)
                    else:
                        self.sender.send(line, copy=True)
                        pending_acks+=1

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

    # parse command line arguments
    arg_list = argv[1:]
    try:
        opts, args = getopt.getopt(arg_list, "ip:s:", ["info", "port=", "server="])
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

    client = PyzmClient(server,port)
    client.run()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
