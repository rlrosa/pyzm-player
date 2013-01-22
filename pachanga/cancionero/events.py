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
zmq_t   = None

def zmq_subscriber(socketio):
    # For too many threads spawning new connection will cause a
    # "too many mailboxes" error, but for small amounts of
    # threads this is fine.

    global zmq_ctx, run
    zmq_sub = zmq_ctx.socket(zmq.SUB)
    zmq_sub.connect("tcp://127.0.0.1:5556")

    try:
        # setsockopt doesn't like unicode
        zmq_sub.setsockopt(zmq.SUBSCRIBE, '')
        socketio.send({'msg':'django connected'})
    except Exception as e:
        raise e

    while run:
        msg = zmq_sub.recv()
        logging.debug('%s-RX: %s' % (inspect.stack()[0][3],msg))
        if msg:
            socketio.send({'msg':msg})
    if zmq_sub:
        logging.debug('closing zmq subscriber')
        zmq_sub.close()
        zmq_sub = None

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
        zmq_t = threading.Thread(target=zmq_subscriber,
                                 args=[socketio])
        zmq_t.setDaemon(True)
        global run
        run = True
        zmq_t.start()
#        spawn(zmq_subscriber, socketio)
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
    global zmq_ctx, zmq_t, run
    run = False
    if zmq_t:
        logging.debug('Waiting for zmq sub thread to join()...')
        zmq_t.join()
        logging.debug('zmq sub thread finished!')
    if zmq_ctx:
        logging.debug('terminating zmq context')
        zmq_ctx.term()
        zmq_ctx = None
