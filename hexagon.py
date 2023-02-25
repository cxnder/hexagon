import http
from http.client import HTTPConnection
from threading import Thread
from typing import List, Callable, Dict
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import socket


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def wax(status_code: int, rdata: str) -> str:
    return json.dumps({
        'status': status_code,
        'data': rdata
    })


def pollen(wax_string: str):
    return json.loads(wax_string)


class Queen(BaseHTTPRequestHandler):
    PORT = 8888

    mapped_ports_for_addr: Dict[str, List[int]] = {}
    cells = []
    endpoints = {}

    @classmethod
    def queen_setup(cls):
        server = ThreadingHTTPServer(("0.0.0.0", Queen.PORT), Queen)
        print('[+] Queen spinning up')
        server.serve_forever()

    def do_POST(self):
        body: bytes = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        if self.path == '/claim_slot':
            w = Queen.claim_available_slot(body.decode('utf-8'))
            self.wfile.write(w.encode('utf-8'))
        elif self.path == '/register_endpoint':
            body: str = body.decode('utf-8')
            cell = body.split('/')[0]
            endpoint = body.split('/', 1)[1]
            self.endpoints['/' + endpoint] = cell
        else:
            try:
                cell = self.endpoints[self.path]
                client = http.client.HTTPConnection(cell)
                client.request("POST", self.path, body, {"Content-type": "text/plain"})
                self.wfile.write(client.getresponse().read())
            except KeyError:
                self.wfile.write(wax(1, f'Endpoint {self.path} offline or non-existient').encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        try:
            cell = self.endpoints[self.path]
            client = http.client.HTTPConnection(cell)
            client.request("GET", self.path)
            self.wfile.write(client.getresponse().read())
        except KeyError:
            self.wfile.write(wax(1, f'Endpoint {self.path} offline or non-existient').encode('utf-8'))

    @classmethod
    def claim_available_slot(cls, address):
        n = Queen.PORT + 1
        if address not in cls.mapped_ports_for_addr:
            cls.mapped_ports_for_addr[address] = [n]
        else:
            while n in cls.mapped_ports_for_addr[address]:
                n += 1
        cell_addr = address + ':' + str(n)
        cls.cells.append(cell_addr)
        return wax(0, str(n))


class Cell(BaseHTTPRequestHandler):
    queen = ''
    endpoints = {}
    ready = False
    addr = None
    port = None
    client = None
    server = None

    @classmethod
    def add_endpoint(cls, endpoint_name: str, endpoint: Callable):
        cls.client.request("POST", "/register_endpoint", cls.addr + ':' + str(cls.port) + endpoint_name, {"Content-type": "text/plain"})
        cls.endpoints[endpoint_name] = endpoint

    def do_POST(self):
        body: bytes = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        target = Cell.endpoints[self.path]
        val = target(self)
        self.wfile.write(val.encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        target = Cell.endpoints[self.path]
        val = target(self)
        self.wfile.write(val.encode('utf-8'))

    @classmethod
    def configure(cls, queen='127.0.0.1') -> None:
        if cls.server is not None:
            raise KeyboardInterrupt
        if queen == '127.0.0.1':
            Thread(target=Queen.queen_setup, args=[]).start()
        cls.queen = queen
        cls.addr = ''
        cls.client = http.client.HTTPConnection(cls.queen + ':' + str(Queen.PORT))
        cls.server = None
        Thread(target=cls.bind, args=[]).start()

    @classmethod
    def bind(cls):
        if cls.queen == '127.0.0.1':
            cls.addr = '127.0.0.1'
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                s.connect(('10.254.254.254', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()
            cls.addr = IP
        cls.client.request("POST", "/claim_slot", cls.addr, {"Content-type": "text/plain"})
        resp = pollen(cls.client.getresponse().read().decode('utf-8'))
        port = int(resp["data"])
        print(f'[+] Got response from queen, binding to port {port}')
        cls.port = port
        cls.server = ThreadingHTTPServer(("0.0.0.0", port), Cell)
        cls.ready = True
        cls.server.serve_forever()


# ----====== End Hexagon Setup ======---- #


class Hexagon:
    def __init__(self):
        Cell.configure()
        while not Cell.ready:
            pass
        self.register_endpoint('/demo', Hexagon.demo_endpoint)

    def register_endpoint(self, endpoint_name: str, endpoint: Callable):
        Cell.add_endpoint(endpoint_name, endpoint)

    @staticmethod
    def demo_endpoint(req: BaseHTTPRequestHandler):
        return wax(0, 'sup')


if __name__ == '__main__':
    Hexagon()
