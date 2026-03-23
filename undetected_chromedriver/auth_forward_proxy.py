#!/usr/bin/env python3
"""
Local HTTP proxy on 127.0.0.1 that forwards to an upstream HTTP proxy with
Proxy-Authorization. Chrome uses ``--proxy-server=http://127.0.0.1:PORT`` with
no credentials — more reliable than extension-based proxy auth.
"""

from __future__ import annotations

import base64
import logging
import select
import socket
import socketserver
import threading
from typing import Optional

logger = logging.getLogger(__name__)


def _relay(a: socket.socket, b: socket.socket) -> None:
    sockets = [a, b]
    try:
        while True:
            r, _, _ = select.select(sockets, [], [], 300.0)
            if not r:
                break
            for s in r:
                try:
                    data = s.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                other = b if s is a else a
                try:
                    other.sendall(data)
                except OSError:
                    return
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def _inject_proxy_auth(header_block: bytes, auth_b64: str) -> bytes:
    if b"proxy-authorization:" in header_block.lower():
        return header_block
    parts = header_block.split(b"\r\n", 1)
    if len(parts) < 2:
        return header_block
    inject = b"Proxy-Authorization: Basic " + auth_b64.encode("ascii") + b"\r\n"
    return parts[0] + b"\r\n" + inject + parts[1]


def _make_handler_class(upstream_host: str, upstream_port: int, auth_b64: str):
    # Avoid "x = x" in class body (RHS name resolution breaks); use distinct locals.
    _h, _p, _a = upstream_host, upstream_port, auth_b64

    class Handler(socketserver.BaseRequestHandler):
        upstream_host = _h
        upstream_port = _p
        auth_b64 = _a

        def handle(self) -> None:
            client = self.request
            try:
                buf = b""
                while b"\r\n\r\n" not in buf and len(buf) < 262144:
                    chunk = client.recv(8192)
                    if not chunk:
                        return
                    buf += chunk
                if b"\r\n\r\n" not in buf:
                    return
                header_end = buf.index(b"\r\n\r\n") + 4
                headers_part = buf[:header_end]
                rest = buf[header_end:]

                first = headers_part.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
                if first.upper().startswith("CONNECT "):
                    self._do_connect(client, headers_part, rest)
                else:
                    self._do_http(client, headers_part, rest)
            except Exception as e:
                logger.debug("auth forward proxy: %s", e)
            finally:
                try:
                    client.close()
                except OSError:
                    pass

        def _do_connect(
            self, client: socket.socket, headers_part: bytes, rest: bytes
        ) -> None:
            modified = _inject_proxy_auth(headers_part, self.auth_b64)
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(60)
            try:
                upstream.connect((self.upstream_host, self.upstream_port))
            except OSError as e:
                logger.debug("upstream connect: %s", e)
                try:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                except OSError:
                    pass
                return
            try:
                upstream.sendall(modified)
                if rest:
                    upstream.sendall(rest)
            except OSError:
                upstream.close()
                return

            resp = b""
            while b"\r\n\r\n" not in resp and len(resp) < 65536:
                chunk = upstream.recv(4096)
                if not chunk:
                    upstream.close()
                    return
                resp += chunk
            if not resp:
                upstream.close()
                return
            first_line = resp.split(b"\r\n", 1)[0]
            if b" 200" not in first_line:
                try:
                    client.sendall(resp)
                except OSError:
                    pass
                upstream.close()
                return
            try:
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            except OSError:
                upstream.close()
                return
            _relay(client, upstream)

        def _do_http(
            self, client: socket.socket, headers_part: bytes, rest: bytes
        ) -> None:
            modified = _inject_proxy_auth(headers_part, self.auth_b64)
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(120)
            try:
                upstream.connect((self.upstream_host, self.upstream_port))
            except OSError:
                try:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                except OSError:
                    pass
                return
            try:
                upstream.sendall(modified)
                if rest:
                    upstream.sendall(rest)
                _relay(client, upstream)
            finally:
                try:
                    upstream.close()
                except OSError:
                    pass

    return Handler


class AuthForwardProxy:
    """Forwards from 127.0.0.1:port to upstream HTTP proxy with Basic auth."""

    def __init__(self, upstream_host: str, upstream_port: int, user: str, password: str):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        auth_b64 = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        handler_cls = _make_handler_class(upstream_host, self.upstream_port, auth_b64)
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler_cls)
        self._server.allow_reuse_address = True
        self.port = self._server.socket.getsockname()[1]
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.debug(
            "auth forward proxy 127.0.0.1:%d -> %s:%d",
            self.port,
            self.upstream_host,
            self.upstream_port,
        )
        return self.port

    def stop(self) -> None:
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass


def start_auth_forward_proxy(
    upstream_host: str, upstream_port: int, user: str, password: str
) -> AuthForwardProxy:
    p = AuthForwardProxy(upstream_host, upstream_port, user, password)
    p.start()
    return p
