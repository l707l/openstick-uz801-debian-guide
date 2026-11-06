#!/usr/bin/env python3
"""
usb_gateway.py - Pasarela HTTP/HTTPS transparente para compartir Internet de Windows al módem USB

Permite que el módem con Debian tenga acceso completo a Internet para apt-get, curl, wget, git, etc.
sin depender de los permisos de Administrador ni de la interfaz gráfica de Windows ICS.
"""

import http.server
import socket
import select
import sys

PORT = 8080
HOST = "0.0.0.0"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_CONNECT(self):
        # Túnel seguro para tráfico HTTPS (apt, curl, git, etc.)
        try:
            host, port = self.path.split(":")
            port = int(port)
            target = socket.create_connection((host, port), timeout=15)
            self.send_response(200, "Connection Established")
            self.end_headers()
            self._tunnel(self.connection, target)
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {e}")

    def do_GET(self):
        self._proxy_http()

    def do_POST(self):
        self._proxy_http()

    def _proxy_http(self):
        import urllib.request
        try:
            req = urllib.request.Request(
                self.path,
                headers={k: v for k, v in self.headers.items() if k.lower() != "proxy-connection"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except Exception as e:
            self.send_error(502, f"Gateway Error: {e}")

    def _tunnel(self, client, target):
        sockets = [client, target]
        while True:
            r, _, _ = select.select(sockets, [], [], 30)
            if not r:
                break
            for s in r:
                data = s.recv(8192)
                if not data:
                    return
                if s is client:
                    target.sendall(data)
                else:
                    client.sendall(data)

    def log_message(self, format, *args):
        pass  # Silencioso

class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

def run():
    print(f"[*] Pasarela de Internet iniciada en http://{HOST}:{PORT}")
    print("[*] En el módem, apt y curl utilizarán la IP de Windows: http://192.168.200.149:8080")
    server = ThreadedHTTPServer((HOST, PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Pasarela detenida.")

if __name__ == "__main__":
    run()
