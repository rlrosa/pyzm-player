pyzm-player
===========

Python based network controlled music player

Usage
-----
The order in which client/server are run does not matter. Communication between server/client is done via zmq. Server can run on its own and get input from stdin.

Running the server:

    rrosa@rrosa-X220:~/work/pyzm-player$ ./pyzm-player.py -i
    Valid arguments:
        -f mediaFileUri //      --file=uriOfMediaFile
        -p portNumber   //      --port=portNumber
        -l [zmq,stdin]  //      --listen=[zmq,stdin]
        -i              //      --info
        -v              //      --verify
    
    rrosa@rrosa-X220:~/work/pyzm-player$./pyzm-player.py
    Server running, listening on zmq port 5555...

Running the client:

    rrosa@rrosa-X220:~/work/pyzm-player$ ./zmq-client.py -i
    Valid arguments:
        -p portNumber   //      --port=portNumber
        -s serverIP     //      --server=xxx.xxx.xxx.xxx
        -i              //      --info
    rrosa@rrosa-X220:~/work/pyzm-player$ ./zmq-client.py 
    Will send stdin via zmq.
    Example:
            play file:///tmp/audio1.mp3,file:///tmp/audio2.mp3
            stop
    To quit type: qqq
    

Now type commands accepted by the server. Server will display a list of valid commands when an invalid one is received.

Server-client communication protocol
------------------------------------

Server-client comm is done over [zmq](http://zguide.zeromq.org/) using [REP/REQ](http://zguide.zeromq.org/php:chapter3#The-Request-Reply-Mechanisms) and sending using json encoded strings.

### Client to server: ###

    msg = {
        'cmd':
            {'name':,
             'code':,
             },
        'args':
            []
        }

The field 'args' is assumed to be a list of (ascii) strings.

Example:

    msg = {
        'cmd':
            {'name':'queue_add',
             'code':4,
             },
        'args':
            ['file:///tmp/playme.mp3']
        }

### Server to client: ###

    data_string = []
    msg = {
        'ack':
            {'res_code':,
             'cmd_code':},
        'data':
            []
        }

Currently the field 'data' is assumed to be a list of strings, may contain error info, command output, etc.

    msg = {
        'ack':
            {'res_code':res_code,
             'cmd_code':cmd_code},
        'data':
            data
        }

Example message received from server in response to 'status' command:

    "ack": {
      "cmd_code": 3, 
      "res_code": 200
    }, 
    "data": [
      false, 
      "file:///tmp/orishas.mp3", 
      {
        "uri": "file:///tmp/orishas.mp3", 
        "tags": {
          "album": "Lo Mejor De Orishas", 
          "genre": "Hip-Hop", 
          "artist": "Orishas", 
          "title": "Emigrantes"
        }
      }
    ]

