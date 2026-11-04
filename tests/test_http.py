"""The local server must reject requests for other hosts and origins."""

import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer

from server import Handler


class LocalRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.service.server_close()
        cls.thread.join()

    def request(self, method, headers):
        client = http.client.HTTPConnection(
            "127.0.0.1", self.service.server_port, timeout=3
        )
        try:
            client.request(
                method,
                "/api/fonts" if method == "GET" else "/api/render",
                headers=headers,
            )
            reply = client.getresponse()
            reply.read()
            return reply.status
        finally:
            client.close()

    def test_local_host_is_accepted(self):
        self.assertEqual(self.request("GET", {"Host": "127.0.0.1:8791"}), 200)

    def test_other_host_is_rejected(self):
        self.assertEqual(self.request("GET", {"Host": "example.com"}), 403)

    def test_other_origin_is_rejected(self):
        self.assertEqual(
            self.request(
                "GET", {"Host": "127.0.0.1:8791", "Origin": "https://example.com"}
            ),
            403,
        )

    def test_negative_body_length_is_rejected(self):
        self.assertEqual(
            self.request("POST", {"Host": "127.0.0.1:8791", "Content-Length": "-1"}),
            400,
        )
