import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import requests
import libtorrent as lt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from shared.modules.libtorrentx import MagnetUtils
from shared.modules.libtorrentx.tracker_gateway import TrackerRoute,public_http_tracker

PAYLOAD=lt.bencode({b'interval':1800,b'peers':b''})
class Response:
    def __init__(self,status=200,payload=PAYLOAD,headers=None): self.status_code,self.payload,self.headers=status,payload,headers or {}
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def iter_content(self,*_):yield self.payload

class TorrentTransportTests(unittest.TestCase):
    def test_magnet_case_and_base32(self):
        uri='magnet:?dn=MixedCase&tr=https%3A%2F%2Ftracker.example%2FCase%3FPasskey%3DAbCd&xt=urn:btih:'+'A'*40
        result=MagnetUtils()._clean_magnet_uri(uri)
        self.assertEqual(parse_qs(urlsplit(result).query)['tr'],['https://tracker.example/Case?Passkey=AbCd'])
        self.assertIn('urn:btih:',MagnetUtils()._clean_magnet_uri('B'*32))
    def test_retries_only_failed_http_announces_and_recovers_direct(self):
        route=TrackerRoute('https://tracker.example/Case?Passkey=AbCd',True);calls=[]
        def blocked(url,**kwargs):
            calls.append((url,kwargs))
            if kwargs['proxies']['https']:return Response()
            raise requests.ConnectionError('blocked')
        self.assertEqual(route.fetch('info_hash=%FF%00',blocked,now=0)[0],502)
        self.assertEqual(route.fetch('info_hash=%FF%00',blocked,now=70)[0],200)
        self.assertEqual(route.route,'tor')
        self.assertTrue(calls[-1][0].endswith('Passkey=AbCd&info_hash=%FF%00'))
        self.assertTrue(calls[-1][1]['proxies']['https'].startswith('socks5h:'))
        route.fetch('info_hash=%FF',lambda *a,**k:Response(),now=1000)
        self.assertEqual(route.route,'direct')
    def test_private_rate_limit_and_tracker_error_do_not_trigger_tor(self):
        for allowed,response in [(False,None),(True,Response(429)),(True,Response(404)),(True,Response(payload=lt.bencode({b'failure reason':b'Invalid passkey'})))]:
            route=TrackerRoute('https://tracker.example/announce',allowed);proxies=[]
            def get(*a,**kw):
                proxies.append(kw['proxies']['https'])
                if response:return response
                raise requests.ConnectionError()
            route.fetch('x=y',get,now=0);route.fetch('x=y',get,now=100)
            self.assertFalse(any(proxies))
    def test_cached_tor_failure_falls_back_to_direct(self):
        route=TrackerRoute('https://tracker.example/announce',True);route.tor_until=1000
        def get(*a,**kw):
            if kw['proxies']['https']:raise requests.ConnectionError()
            return Response()
        self.assertEqual(route.fetch('x=y',get,now=100)[0],200)
        self.assertEqual(route.route,'direct')
    def test_redirect_preserves_query_and_refuses_private_targets(self):
        calls=[]
        def get(url,**kw):
            calls.append(url)
            return Response(302,headers={'Location':'https://other.example/announce'}) if len(calls)==1 else Response()
        self.assertEqual(TrackerRoute('https://tracker.example/announce').fetch('info_hash=%FF',get)[0],200)
        self.assertIn('info_hash=%FF',calls[1])
        self.assertFalse(public_http_tracker('udp://tracker.example:80/announce'))
        self.assertFalse(public_http_tracker('http://127.0.0.1/announce'))
        self.assertFalse(public_http_tracker('http://10.0.0.1/announce'))
        self.assertTrue(public_http_tracker('https://tracker.example/Case'))

if __name__=='__main__':unittest.main()
