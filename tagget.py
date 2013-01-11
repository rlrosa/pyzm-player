#!/usr/bin/env python
# src: http://www.jezra.net/blog/use_python_and_gstreamer_to_get_the_tags_of_an_audio_file
import os
import sys
import gst
import gobject

class tag_getter:
    def __init__(self, tags, timeout=2000):
        #make a dictionary to hold our tag info
        self.file_tags = tags
        #make a playbin to parse the audio file
        self.pbin = gst.element_factory_make("playbin")
        #we need to receive signals from the playbin's bus
        self.bus = self.pbin.get_bus()
        #make sure we are watching the signals on the bus
        self.bus.add_signal_watch()
        #what do we do when a tag is part of the bus signal?
        self.bus.connect("message::tag", self.bus_message_tag)
        self.bus.connect("message::err", self.bus_message_err)
        self.bus.connect("message::eos", self.bus_message_eos)
        #create a timeout in case we fail to get tags
        gobject.timeout_add(timeout,self.timeout)
        #create a loop to control our app
        self.mainloop = gobject.MainLoop()

    def bus_message_tag (self, bus, message):
        #we received a tag message
        gst.debug('msg rx: tag')
        taglist = message.parse_tag()
        #put the keys in the dictionary
        for key in taglist.keys():
            self.file_tags[key] = taglist[key]
        #for this test, if we have the artist tag, we can quit
        if self.file_tags['artist']:
            gst.debug('got artist+title, will quit mainloop')
            self.file_tags['done'] = '1'
            # avoid gst warnings
            self.quit()

    def bus_message_err (self, bus, message):
        err, debug = message.parse_error()
        err_msg = 'Got error message, will abort:%s ' % err, debug
        gst.error(err_msg)
        self.quit()

    def bus_message_eos (self, bus, message):
        gst.error('Got eos, will abort')
        self.quit()

    def bus_message_eos(self, bus, message):
        gst.debug('msg rx: eos')
        sys.exit(0)

    def set_file(self,uri):
        #set the uri of the playbin to our audio file
        self.pbin.set_property('uri',uri)
        #pause the playbin, we don't really need to play
        self.pbin.set_state(gst.STATE_PAUSED)
        
    def run(self):
        #start the main loop
        gst.debug('Will enter mainloop to wait for tag messages')
        self.mainloop.run()
        gst.debug('mainloop finished, will quit')
        return False

    def timeout(self):
        # time to give up
        gst.warning('Timed out before getting tag')
        self.quit()
        return False

    def quit(self):
        # avoid gst warnings
        self.pbin.set_state(gst.STATE_NULL)
        # done, lets go
        self.mainloop.quit()

def get_tags(tags,uri,timeout=2000):
    tg = tag_getter(tags,timeout)
    tg.set_file(uri)
    tg.run()

if __name__=="__main__":
    if len(sys.argv)>1:
        file = sys.argv[1]
        try:
            timeout = int(sys.argv[2])
        except (IndexError,TypeError):
            timeout = 2000
        tags = {}
        pwd = os.getcwd()
        filepath = os.path.join(pwd,file)
        getter = tag_getter(tags,timeout)
        getter.set_file(file)
        getter.run()
        print 'done:',tags

    else:
        print "select an audio file"
