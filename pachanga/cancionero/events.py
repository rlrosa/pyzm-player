from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from django_socketio import events

import logging

@events.on_connect
def message(request, socket, context):
    """
    Event handler for a room receiving a message.
    """
    logging.debug('Connection established!')
    # connect to zmq, etc

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
