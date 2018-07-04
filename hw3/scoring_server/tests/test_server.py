from .. import api, store
from threading import Thread
from BaseHTTPServer import HTTPServer
import unittest
import socket
import requests
import test_constants


def get_free_port():
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    address, port = s.getsockname()
    s.close()
    return port


class MainHandlerTest(unittest.TestCase):

    def setUp(self):
        self.port = get_free_port()
        self.handler_url = 'http://localhost:%d/method/' % self.port
        self.server = HTTPServer(('localhost', self.port),
                                 api.MainHTTPHandler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.setDaemon(True)
        self.server_thread.start()
        self.cache_store = store.Store()

    def test_score_request(self):
        response = requests.post(self.handler_url,
                                 json=test_constants.VALID_SCORE_REQUEST)
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()['response']['score'], 5.0)

    def test_client_interests(self):
        self.cache_store.cache_set('i:1', "{\"i\": [\"travel\", \"geek\"]}",
                                   100)
        self.cache_store.cache_set('i:2', "{\"i\": [\"sport\", \"cars\"]}",
                                   100)
        self.cache_store.cache_set('i:3', "{\"i\": [\"books\", \"sport\"]}",
                                   100)
        self.cache_store.cache_set('i:4', "{\"i\": [\"hi-tech\", \"cinema\"]}",
                                   100)
        response = requests.post(self.handler_url,
                                 json=test_constants.VALID_INTERESTS_REQUEST)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.json()['response'],
            {"1": {'i': ["travel", "geek"]}, "2": {'i': ["sport", "cars"]},
             "3": {'i': ["books", "sport"]},
             "4": {'i': ["hi-tech", "cinema"]}})

    def tearDown(self):
        self.cache_store.client.flush_all()
