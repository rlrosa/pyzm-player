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
    
    rrosa@rrosa-X220:~/work/pyzm-player$./pyzm-player.py
    Server running, listening on zmq port 5555...

Running the client:

    rrosa@rrosa-X220:~/work/pyzm-player$ ./zmq-client.py -i
    Valid arguments:
        -p portNumber   //      --port=portNumber
        -i              //      --info
    rrosa@rrosa-X220:~/work/pyzm-player$ ./zmq-client.py 
    Will send stdin via zmq.
    To quit type: qqq

    Msg to send:

Now type commands accepted by the server. Server will display a list of valid commands when an invalid one is received.
