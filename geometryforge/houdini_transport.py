"""Authenticated JSON-only loopback transport; no Python object RPC or pickle."""
import hmac
import json
import socket
import socketserver

LIMIT = 2_000_000


class Client:
    def __init__(self, port, token):
        self.port, self.token = port, token

    def invoke(self, method, *args):
        data = json.dumps({'token': self.token, 'method': method, 'args': args}).encode() + b'\n'
        if len(data) > LIMIT:
            raise ValueError('Houdini request too large')
        with socket.create_connection(('127.0.0.1', self.port), timeout=5) as sock:
            sock.sendall(data)
            with sock.makefile('rb') as stream:
                raw = stream.readline(LIMIT + 1)
        if len(raw) > LIMIT:
            raise RuntimeError('Houdini response too large')
        result = json.loads(raw)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result['result']

    def submit(self, token, job, request):
        return self.invoke('submit', job, request)

    def status(self, token, job):
        return self.invoke('status', job)

    def cancel(self, token, job):
        return self.invoke('cancel', job)

    def close(self):
        pass  # Each request owns its connection.


def server(port, token, methods):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(5)
            try:
                raw = self.rfile.readline(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise ValueError('Request too large')
                request = json.loads(raw)
                supplied = request.get('token', '')
                if not isinstance(supplied, str) or not hmac.compare_digest(supplied, token):
                    raise ValueError('Invalid session credential')
                method = request.get('method')
                if method not in methods:
                    raise ValueError('Unsupported job operation')
                result = {'result': methods[method](*request.get('args', []))}
            except Exception as exc:
                result = {'error': str(exc)}
            self.wfile.write(json.dumps(result).encode() + b'\n')

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = False

    return Server(('127.0.0.1', port), Handler)
