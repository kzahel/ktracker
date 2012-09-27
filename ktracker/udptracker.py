import socket,struct
import urlparse
import urllib
import logging
import random

uint32_max = 2**32
import functools
import tornado.ioloop
from tornado import gen
ioloop = tornado.ioloop.IOLoop.instance()

class UDPTracker(object):
    def send_and_wait(self, msg):
        self.clisocket.sendto(msg, (self.host, self.port))
        logging.info('sending to udp tracker...')
        #res = self.clisocket.recv(1024)
        #res = self.clisocket.recv(20 + 6 * 150)
        res = self.clisocket.recv(4096)
        logging.info('udp tracker response %s of len %s' % ([res], len(res)))
        return res

    def send_and_get(self, msg, callback=None):
        self.clisocket.sendto(msg, (self.host, self.port))
        ioloop.add_handler(self.clisocket.fileno(), functools.partial(self.got_data, callback), ioloop.READ)

    def got_data(self, callback, *args):
        ioloop.remove_handler(self.clisocket.fileno())
        data = self.clisocket.recv(4096)
        callback(data)

    @gen.engine
    def get_connection(self, callback=None):
        protocol_id = 0x41727101980
        connection_request_action = 0
        req_transaction_id = self.get_new_transaction_id()
        conn_pack = struct.pack(">QII", protocol_id, connection_request_action, req_transaction_id)

        res = yield gen.Task( self.send_and_get,conn_pack )

        response = struct.unpack(">IIQ", res)
        action, transaction_id, connection_id = response

        if req_transaction_id != transaction_id:
            raise Exception
        if action != 0:
            raise Exception

        logging.info('got connection id %s' % connection_id)
        self.connection_id = connection_id
        callback()
        
    def get_new_transaction_id(self):
        return random.randrange(0,uint32_max)

    def __init__(self, tracker_url, request):
        self.parsed = urlparse.urlparse(tracker_url)
        if request.method == 'POST':
            args = request.arguments
        else:
            args = urlparse.parse_qs( str(self.parsed.path.split('?')[1]) )

        self.host,self.port = self.parsed.netloc.split(':')
        self.port = int(self.port)
        self.request = request
        self.clisocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.clisocket.setblocking(False)
        #self.clisocket.settimeout(4)


        self.info_hash = args
        self.info_hash = args['info_hash'][0]
        self.peer_id = args['peer_id'][0]

        #self.info_hash = request.arguments['info_hash'][0]
        #self.peer_id = request.arguments['peer_id'][0]

        #self.get_connection()
        #self.announce()

    @gen.engine
    def announce(self, callback=None):
        action = 1
        downloaded = 0
        left = 0
        uploaded = 0
        event =0
        ip = 0
        key = 0
        num_want = -1
        port = 9999
        extensions = 0

        tid = self.get_new_transaction_id()

        announce_pack = struct.pack(">QLL20s20sQQQLLLlHH",
                                    self.connection_id,
                                    action,
                                    tid,
                                    self.info_hash,
                                    self.peer_id,
                                    downloaded,
                                    left,
                                    uploaded,
                                    event,
                                    ip,
                                    key,
                                    num_want,
                                    port,
                                    extensions
                                    )
        print 'announce_pack',len(announce_pack)
        res = yield gen.Task( self.send_and_get, announce_pack )
        #res = self.send_and_wait(announce_pack)
        assert len(res) > 20
        response = struct.unpack(">IIIII", res[:20])

        raction, rtid, interval, leechers, seeders = response
        assert raction == action
        assert rtid == tid
        logging.info('tracker response seeders %s, leechers %s' % (seeders, leechers))

        remainder_len = len(res) - 20

        if remainder_len % 6 != 0:
            logging.error('response not divisible by 6...')
        #assert remainder_len % 6 == 0

        peers = []

        numpeers = remainder_len/6
        #assert numpeers == seeders+leechers
        for i in range(numpeers):
            peerdata = res[20 + i*6 : 20 + (i+1)*6]
            host, port = struct.unpack('>4sH', peerdata)
            host = '.'.join(map(str, map(ord, host)))
            peers.append( (host, port) )

        callback(peers)
