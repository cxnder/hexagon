import http
from http.client import HTTPConnection
from threading import Thread
from typing import List, Callable, Dict
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import socket
import os

TOKEN = os.environ['Token']
HIVE = os.environ['Hive'] if 'Hive' in os.environ else None


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
    client = None

    mapped_ports_for_addr: Dict[str, List[int]] = {}
    cells = []
    endpoints = {}
    exposed_endpoints = {}
    addr = None

    @classmethod
    def queen_setup(cls):
        server = ThreadingHTTPServer(("0.0.0.0", Queen.PORT), Queen)
        cls.client = http.client.HTTPConnection(HIVE + ':88')
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
            port = body.split(':')[1].split('/')[0]
            endpoint = body.split('/', 1)[1]
            self.endpoints['/' + endpoint] = self.request.getpeername()[0] + ':' + port
        elif self.path == '/register_endpoint_hive':
            body: str = body.decode('utf-8')
            port = body.split(':')[1].split('/')[0]
            endpoint = body.split('/', 1)[1]
            self.endpoints['/' + endpoint] = self.request.getpeername()[0] + ':' + port
            self.exposed_endpoints['/' + endpoint] = self.request.getpeername()[0] + ':' + port
            self.client.request("POST", "/register_endpoint",
                                self.addr + f':8888/{endpoint}',
                                {"Content-type": "text/plain", 'Token': TOKEN})
        elif self.path == '/register_endpoint_hive_unauth':
            body: str = body.decode('utf-8')
            port = body.split(':')[1].split('/')[0]
            endpoint = body.split('/', 1)[1]
            self.endpoints['/' + endpoint] = self.request.getpeername()[0] + ':' + port
            self.exposed_endpoints['/' + endpoint] = self.request.getpeername()[0] + ':' + port
            self.client.request("POST", "/register_endpoint_unauth",
                                self.addr + f':8888/{endpoint}',
                                {"Content-type": "text/plain", 'Token': TOKEN})
        else:
            try:
                cell = self.endpoints[self.path]
                client = http.client.HTTPConnection(cell)
                client.request("POST", self.path, body, {"Content-type": "text/plain", 'Token': TOKEN})
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
        except ConnectionRefusedError:
            self.wfile.write(wax(1, f'Endpoint {self.endpoints[self.path]} offline or non-existient').encode('utf-8'))

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
    def add_endpoint(cls, endpoint_name: str, endpoint: Callable, exposed: bool = False, unauth = False):
        cls.client.request("POST", "/register_endpoint_hive" + ''.join('_unauth' if unauth else '') if exposed else "/register_endpoint",
                           cls.addr + ':' + str(cls.port) + endpoint_name,
                           {"Content-type": "text/plain", 'Token': TOKEN})
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
        cls.client.request("POST", "/claim_slot", cls.addr, {"Content-type": "text/plain", 'Token': TOKEN})
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
        self.register_endpoint('/demo3', Hexagon.demo_endpoint, True, True)

    def register_endpoint(self, endpoint_name: str, endpoint: Callable, exposed=False, unauth=False):
        Cell.add_endpoint(endpoint_name, endpoint, exposed, unauth)

    @staticmethod
    def demo_endpoint(req: BaseHTTPRequestHandler):
        return wax(0, 'sup2')


if __name__ == '__main__':
    Hexagon()
