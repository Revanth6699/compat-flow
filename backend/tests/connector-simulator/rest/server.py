from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import ssl
from urllib.parse import urlparse, parse_qs

PRODUCTS = [
    {"sku": "SIM-1001", "title": "Industrial Pump Seal", "unit_price": 12.5, "currency": "USD", "quantity": 120},
    {"sku": "SIM-1002", "title": "Stainless Steel Fastener", "unit_price": 0.85, "currency": "USD", "quantity": 2500},
]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("X-API-Key") != os.environ.get("SIMULATOR_API_KEY", "local-test-key"):
            self.send_error(401, "Invalid simulator API key")
            return
        parsed = urlparse(self.path)
        if parsed.path != "/catalog":
            self.send_error(404)
            return
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        body = {"data": {"items": PRODUCTS if page == 1 else [], "next_page": None}}
        encoded = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_):
        pass

server = HTTPServer(("0.0.0.0", 8443), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("/run/tls/server.crt", "/run/tls/server.key")
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
