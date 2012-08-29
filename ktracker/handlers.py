import tornado.web
import logging
import tornado.httpclient
httpclient = tornado.httpclient.AsyncHTTPClient()
from tornado import gen
import bencode
import json
import binascii
import base64
from cgi import escape
import struct

def decode_peer(bytes):
    assert len(bytes) == 6
    ip = '.'.join( map(str, ( map(ord, bytes[:4]) ) ) )
    port = ord(bytes[4]) * 256 + ord(bytes[5])
    return ip, port

def encode_peer(ip, port):
    ippart = ''.join(map(chr, map(int, ip.split('.'))))
    port = struct.pack('>H', port)

    return ippart+port


class Peer(object):
    def __init__(self, request, args):
        self.ip = request.remote_ip
        self.port = args['port']
        self.peer_id = args['peer_id']
        self.downloaded = args['downloaded']
        self.uploaded = args['uploaded']
        
    def update(self, args):
        logging.info('udpate peer %s' % self)

class Swarm(object):
    def __init__(self, hash):
        self.hash = hash
        self.peers = {}

    def serialize(self):
        d = {}
        for id,peer in self.peers.iteritems():
            d['%s:%s' % (peer.ip, peer.port)] = peer
        return d

    def handle_announce(self, args):
        if args['peer_id'] not in self.peers:
            peer = Peer(args['_request'], args)
            self.peers[args['peer_id']] = peer
        else:
            peer = self.peers[args['peer_id']]
            peer.update(args)

        return self.dump_peers()

    def dump_peers(self):
        d = {}
        arr = []
        for peerid, peer in self.peers.iteritems():
            arr.append( encode_peer( peer.ip, peer.port ) )
        d['peers'] = ''.join(arr)
        return d


class Tracker(object):
    swarms = {}

    def handle_announce(self, args):
        hash = args['info_hash']
        if hash not in self.swarms:
            self.swarms[hash] = Swarm(hash)

        return self.swarms[hash].handle_announce(args)
        
tracker = Tracker()

class BaseHandler(tornado.web.RequestHandler):

    key_types = {'numwant':'int',
                 'compact':'int',
                 'port':'int',
                 'downloaded':'int',
                 'uploaded':'int',
                 'left':'int'}

    def writeout(self, data):
        if 'callback' in self.request.arguments:
            self.write(self.get_argument('callback'))
            self.write('("')
            #self.write(base64.b64encode(bencode.bencode(data)))
            self.set_header('Content-Type', 'application/x-bittorrent; charset=ISO-8859-1')
            self.write(bencode.bencode(data))
            self.write('")')
        else:
            self.write(bencode.bencode(data))

    def get_args(self):
        d = {}
        d['_request'] = self.request
        for key in self.request.arguments:
            vals = self.request.arguments[key]
            val = vals[0]
            #try:
            #    val = self.get_argument(key) # unicodedecode error
            #except:
            #    logging.info('error decodin %s' % key)
            if key in self.key_types:
                if self.key_types[key] == 'int':
                    d[key] = int(val)
                else:
                    d[key] = val
            else:
                d[key] = val
        return d
            

class AnnounceHandler(BaseHandler):
    def get(self):
        logging.info('got announce %s,%s' % (self.request.headers, self.request.arguments))
        if 'info_hash' in self.request.arguments:
            args = self.get_args()
            if len(args['info_hash']) != 20:
                import pdb; pdb.set_trace()
            assert(len(args['info_hash']) == 20)
            response = tracker.handle_announce( args )
            self.writeout(response)

class Handler(tornado.web.RequestHandler):
    @gen.engine
    @tornado.web.asynchronous
    def get(self):
        if '_tracker_url' in self.request.arguments:
            tracker_url = self.get_argument('_tracker_url')
            response = yield gen.Task( httpclient.fetch, '%s%s' % (tracker_url, self.request.uri ) )
            if response.code == 200:
                self.write(self.get_argument('callback'))
                self.write('("')
                self.write(base64.b64encode(response.body))
                self.write('")')
        self.finish()

class DebugHandler(BaseHandler):
    def get(self):
        attrs = {}
        attrs.update( 
            dict( 
                tracker = tracker,
                swarms = dict( (binascii.hexlify(h),s.serialize()) for h,s in tracker.swarms.iteritems() )
                )
            )
                      
        def custom(obj):
            return escape(str(obj))

        self.write('<html><body><pre>')
        self.write( json.dumps( attrs, indent=2, sort_keys = True, default=custom ) )
#        options['colorize'].set(colorval)
        self.write('</pre><script src="/static/repl.js"></script>')
        self.write('<p><input style="width:100%" name="input" autocomplete="off" type="text" onkeydown="keydown(this, event);" /></p><div id="output" style="border:1px solid black; margin: 1em"></div>')
        command = """     Connection.initiate(host,port,startuphash) """
        self.write('<pre>%s</pre>' % command)
        self.write('</body></html>')
        
