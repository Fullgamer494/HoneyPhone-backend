"""HTTP controls applied before reading request bodies or opening database sessions."""

import json
import math
import time
from collections import OrderedDict
from threading import Lock


class RateLimitMiddleware:
    """Fixed windows per transport client IP; bounded memory, one process.

    Forwarded headers must be resolved by Uvicorn using trusted proxy addresses.
    Never trust an arbitrary X-Forwarded-For value here.
    """

    def __init__(self, app, requests=120, auth_requests=10, window_seconds=60,
                 max_clients=10000, clock=time.monotonic):
        self.app = app
        self.requests = requests
        self.auth_requests = auth_requests
        self.window = window_seconds
        self.max_clients = max_clients
        self.clock = clock
        self.clients = OrderedDict()
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path', '').startswith('/api/'):
            await self.app(scope, receive, send)
            return
        now = self.clock()
        ip = (scope.get('client') or ('unknown', 0))[0]
        is_auth = scope.get('path', '').startswith('/api/v1/auth/') and scope.get('method') == 'POST'
        with self.lock:
            # Windows expire in insertion order. Active clients are never evicted
            # to admit new clients, which would allow bypassing limits by churn.
            while self.clients and next(iter(self.clients.values()))[0] <= now:
                self.clients.popitem(last=False)
            row = self.clients.get(ip)
            if row is None and len(self.clients) < self.max_clients:
                row = [now + self.window, 0, 0]
                self.clients[ip] = row
            if row is None:
                retry = max(1, math.ceil(next(iter(self.clients.values()))[0] - now))
                allowed = False
            else:
                retry = max(1, math.ceil(row[0] - now))
                allowed = row[1] < self.requests and (not is_auth or row[2] < self.auth_requests)
                if allowed:
                    row[1] += 1
                    row[2] += int(is_auth)
        if allowed:
            await self.app(scope, receive, send)
            return
        body = json.dumps({'code': 'RATE_LIMIT_EXCEEDED', 'message': 'Too many requests. Try again later.'}).encode()
        await send({'type': 'http.response.start', 'status': 429, 'headers': [
            (b'content-type', b'application/json'), (b'content-length', str(len(body)).encode()),
            (b'retry-after', str(retry).encode()), (b'cache-control', b'no-store')]})
        await send({'type': 'http.response.body', 'body': body})


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                headers = dict(message.get('headers', []))
                headers.update({
                    b'x-content-type-options': b'nosniff',
                    b'x-frame-options': b'DENY',
                    b'referrer-policy': b'no-referrer',
                    b'permissions-policy': b'camera=(), microphone=(), geolocation=()',
                })
                if scope.get('scheme') == 'https':
                    headers[b'strict-transport-security'] = b'max-age=31536000'
                if scope.get('path', '').startswith('/api/') or scope.get('path', '').startswith('/account/'):
                    headers[b'cache-control'] = b'no-store'
                message = {**message, 'headers': list(headers.items())}
            await send(message)

        await self.app(scope, receive, secure_send)
