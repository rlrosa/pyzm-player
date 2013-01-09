#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

r_codes = {
    200: 'OK',             # OK: Generic
    400: 'NK',             # NK: Generic
    401: 'Invalid cmd',    # NK: Invalid command
    402: 'Cmd exe failed', # NK: Failed to execute cmd
    403: 'Invalid URI',    # NK: Invalid URI
    404: 'URI not found!', # NK: URI not found
}

cmd_id_name = {
    0: 'invalid',
    1: 'play',
    2: 'stop',
    3: 'is_playing',
    4: 'load',
    10:'help',
    11:'quit',
}

cmd_name_id = dict((v,k) for k, v in cmd_id_name.iteritems())
