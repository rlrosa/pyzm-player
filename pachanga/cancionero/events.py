from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from django_socketio import events

import logging

from gevent_zeromq import zmq
from gevent import spawn
zmq_ctx = zmq.Context()
zmq_sub = None

def zmq_subscriber(socketio):
    # For too many threads spawning new connection will cause a
    # "too many mailboxes" error, but for small amounts of
    # threads this is fine.

    global zmq_ctx, zmq_sub
    subscriber = zmq_ctx.socket(zmq.SUB)
    subscriber.connect("tcp://127.0.0.1:5556")

    # setsockopt doesn't like unicode
    subscriber.setsockopt(zmq.SUBSCRIBE, '')

    socketio.send({'msg':'django connected'})

    while True:
        msg = subscriber.recv()
        logging.debug('RX: %s' % msg)
        if msg:
            socketio.send({'msg':msg})

@events.on_connect
def message(request, socket, context):
    """
    Event handler for connection establishment.
    """
    logging.debug('websocket Connection established!')
    # connect to zmq
    try:
        zmq_running = context['socket_up']
    except KeyError as e:
        socketio = request.environ['socketio']
        spawn(zmq_subscriber, socketio)
        context['socket_up'] = True
        logging.info('zmq subscriber running')

@events.on_message(channel='sucket')
def message(request, socket, context, message):
    """
    Event handler for receiving a message.
    """
    logging.debug(message)
    msg_ans = {'msg': 'server says go away'}
    socket.send_and_broadcast_channel(msg_ans)

@events.on_finish
def finish(request, socket, context):
    """
    Event handler for a socket session ending in a room. Broadcast
    the user leaving and delete them from the DB.
    """
    logging.debug('leaving...')
    if zmq_ctx:
        if zmq_sub:
            logging.debug('closing zmq subscriber')
            zmq_sub.close()
        logging.debug('terminating zmq context')
        zmq_ctx.term()
