from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pprint import pprint
import cgi
import os
import sys
import shutil
ADDRESS = ""
PORT = 27121
WORKDIR = os.path.abspath(os.curdir)
if len(sys.argv) > 1:
    WORKDIR = os.path.abspath(os.path.join(os.curdir, sys.argv[1]))
    print(WORKDIR)


def handle_message(message):
    data = json.loads(message)
    pprint(data)
    try:
        os.mkdir(f'{WORKDIR}/samples')
    except:
        shutil.rmtree(f'{WORKDIR}/samples')
        os.mkdir(f'{WORKDIR}/samples')
    for i, testcase in enumerate(data['tests']):
        in_f = open(f'{WORKDIR}/samples/in{i+1}', 'w+')
        out_f = open(f'{WORKDIR}/samples/out{i+1}', 'w+')
        in_f.write(testcase['input'])
        out_f.write(testcase['output'])
        in_f.close()
        out_f.close()


class Handler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def log_message(self, *_):
        pass

    def do_HEAD(self):
        self._set_headers()

    def do_GET(self):
        self._set_headers()
        self.send_response(200, "OK bro")

    def do_POST(self):
        ctype, _ = cgi.parse_header(self.headers.get('content-type'))

        if ctype != 'application/json':
            self.send_response(400)
            self.end_headers()
            return
        length = int(self.headers.get('content-length'))
        raw = self.rfile.read(length).decode('utf-8')
        print(":: PROBLEM RECEIVED ::")
        message = json.loads(raw)
        handle_message(json.dumps(message))
        self._set_headers()
        self.send_response(200, "OK bro")


server = HTTPServer((ADDRESS, PORT), Handler)
print("Started listening on port", PORT)
server.serve_forever()
