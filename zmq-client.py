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
    port    = None

    def __init__(self, server, port):
        self.server  = server
        self.port    = port
        self.context = zmq.Context()
        self.sender  = self.context.socket(zmq.REQ)
        self.sender.connect('tcp://%s:%d' % (server,port))

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
        print "Will send stdin via zmq.\nTo quit type: %s\n" % quit_cmd
        while True:
            line = raw_input('Msg to send:')
            if(line == quit_cmd):
                self.quit()
            self.sender.send(line)
            print 'Waiting for recv()...',
            ack = self.sender.recv()
            print 'recv(): %s' % ack

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
