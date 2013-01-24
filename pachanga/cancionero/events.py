from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from django_socketio import events

import logging
import zmq
import threading

# get function name from within function
import inspect

zmq_ctx = zmq.Context()
run     = False

def zmq_subscriber(ip='127.0.0.1', port=5556):
    # For too many threads spawning new connection will cause a
    # "too many mailboxes" error, but for small amounts of
    # threads this is fine.

    global zmq_ctx, run
    zmq_sub = zmq_ctx.socket(zmq.SUB)
    zmq_sub.connect("tcp://127.0.0.1:5556")

    try:
        # setsockopt doesn't like unicode
        zmq_sub.setsockopt(zmq.SUBSCRIBE, '')
    except Exception as e:
        raise e

    while run:
        msg = zmq_sub.recv()
        logging.debug('%s-RX: %s' % (inspect.stack()[0][3],msg))
        if msg and sock_list:
            sock_list[0].send_and_broadcast_channel({'msg':msg})
            # the line above does the job, this is not required
            # for sock in sock_list:
            #     sock.send({'msg':msg})
    if zmq_sub:
        logging.debug('closing zmq subscriber')
        zmq_sub.close()
        zmq_sub = None

zmq_t   = None
zmq_t = threading.Thread(target=zmq_subscriber)
zmq_t.setDaemon(True)
run = True
zmq_t.start()
sock_list = []

@events.on_connect
def connect(request, socket, context):
    """
    Event handler for subscribe establishment.
    """
    print 'connect'
    context['socket_up'] = True

@events.on_subscribe(channel='sucket')
def subscribe(request, socket, context, channel):
    """
    Event handler for subscribe establishment.
    """
    global sock_list
    logging.debug('websocket subscriber detected!')
    sock_list.append(socket)
    print 'subscribe', sock_list

@events.on_disconnect
def disconnect(request, socket, context):
    global sock_list
    try:
        sock_list.remove(socket)
    except: pass
    print 'disconnect',sock_list

@events.on_unsubscribe(channel='sucket')
def unsubscribe(request, socket, context, channel):
    global sock_list
    try:
        sock_list.remove(socket)
    except: pass
    print 'unsubscribe',sock_list

@events.on_message(channel='sucket')
def message(request, socket, context, message):
    """
    Event handler for receiving a message.
    """
    logging.debug(message)
    msg_ans = {'msg': 'server says go away'}
    socket.send_and_broadcast_channel({'msg':msg_ans})

@events.on_finish
def finish(request, socket, context):
    """
    Event handler for a socket session ending in a room. Broadcast
    the user leaving and delete them from the DB.
    """
    global sock_list
    try:
        sock_list.remove(socket)
    except: pass
    print 'finish',sock_list
    # logging.debug('leaving...')
    # global zmq_ctx, zmq_t, run
    # run = False
    # if zmq_t:
    #     logging.debug('Waiting for zmq sub thread to join()...')
    #     zmq_t.join()
    #     logging.debug('zmq sub thread finished!')
    # if zmq_ctx:
    #     logging.debug('terminating zmq context')
    #     zmq_ctx.term()
    #     zmq_ctx = None
