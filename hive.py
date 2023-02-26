#
# Hive is a minified queen that just serves
#   content from other queens across internet.
#

import http
from http.client import HTTPConnection
from typing import List, Dict
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def wax(status_code: int, rdata: str) -> str:
    return json.dumps({
        'status': status_code,
        'data': rdata
    })


class Hive(BaseHTTPRequestHandler):
    PORT = 88

    mapped_ports_for_addr: Dict[str, List[int]] = {}
    queens = {}
    endpoints = {}
    unauth_endpoints = {}

    @classmethod
    def hive_setup(cls):
        server = ThreadingHTTPServer(("0.0.0.0", Hive.PORT), Hive)
        print('[+] Hive.')
        server.serve_forever()

    def do_POST(self):
        if self.headers['Token'] != os.environ['TOKEN']:
            print(self.headers)
            try:
                cell = self.unauth_endpoints[self.path]
                print(f'Attempting con to {cell}')
                body: bytes = self.rfile.read(int(self.headers['Content-Length']))
                client = http.client.HTTPConnection(cell)
                client.request("POST", self.path, body, {"Content-type": "text/plain"})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(client.getresponse().read())
            except KeyError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'Endpoint {self.path} offline or non-existient'.encode('utf-8'))
            return
        try:
            body: bytes = self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            if self.path == '/register_queen':
                body: str = body.decode('utf-8')
                exposed_ip = self.request.getpeername()[0]
                self.queens[exposed_ip] = body
                print(f'Registered Queen for {exposed_ip} -> {body}')
                return
            if self.path == '/register_endpoint':
                body: str = body.decode('utf-8')
                port = body.split(':')[1].split('/')[0]
                endpoint = body.split('/', 1)[1]
                self.endpoints['/' + endpoint] = self.request.getpeername()[0] + f':{port}'
            if self.path == '/register_endpoint_unauth':
                body: str = body.decode('utf-8')
                port = body.split(':')[1].split('/')[0]
                endpoint = body.split('/', 1)[1]
                self.endpoints['/' + endpoint] = self.request.getpeername()[0] + f':{port}'
                self.unauth_endpoints['/' + endpoint] = self.request.getpeername()[0] + f':{port}'
            else:
                try:
                    cell = self.endpoints[self.path]
                    client = http.client.HTTPConnection(cell)
                    client.request("POST", self.path, body, {"Content-type": "text/plain"})
                    self.wfile.write(client.getresponse().read())
                except KeyError:
                    self.wfile.write(f'Endpoint {self.path} offline or non-existient'.encode('utf-8'))
        except Exception as ex:
            print(ex)

    def do_GET(self):
        if self.headers['Token'] != os.environ['TOKEN']:
            print(self.headers)
            try:
                cell = self.unauth_endpoints[self.path]
                print(f'Attempting con to {cell}')
                self.send_response(200)
                self.end_headers()
                client = http.client.HTTPConnection(cell)
                client.request("GET", self.path)
                self.wfile.write(client.getresponse().read())
            except KeyError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'Endpoint {self.path} offline or non-existient'.encode('utf-8'))
            return
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        if self.path == "/get_queen":
            key = self.request.getpeername()[0]
            try:
                queen = self.queens[key]
                self.wfile.write(wax(0, queen).encode('utf-8'))
                return
            except KeyError:
                self.wfile.write(wax(1, "").encode('utf-8'))
                return
        try:
            try:
                cell = self.endpoints[self.path]
                client = http.client.HTTPConnection(cell)
                client.request("GET", self.path)
                self.wfile.write(client.getresponse().read())
            except KeyError:
                self.wfile.write(f'Endpoint {self.path} offline or non-existient'.encode('utf-8'))
        except Exception as ex:
            print(ex)


if __name__ == '__main__':
    Hive.hive_setup()
