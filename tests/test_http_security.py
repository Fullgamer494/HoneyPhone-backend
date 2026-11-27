"""Database-free checks for the outer ASGI security controls."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'http_security', Path(__file__).parents[1] / 'src/honeyphone/core/http_security.py')
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)


async def endpoint(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    await send({'type': 'http.response.body', 'body': b'ok'})


async def request(app, path='/api/v1/devices', ip='192.0.2.1', method='GET', scheme='http', forwarded=None):
    messages = []

    async def receive():
        raise AssertionError('The limiter must not read the request body')

    async def send(message):
        messages.append(message)

    await app({'type': 'http', 'path': path, 'method': method, 'scheme': scheme,
               'client': (ip, 1234), 'headers': [(b'x-forwarded-for', forwarded)] if forwarded else []}, receive, send)
    return messages[0]['status'], dict(messages[0]['headers'])


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_general_limit_reset_and_client_isolation(self):
        now = [0]
        app = security.RateLimitMiddleware(endpoint, requests=2, clock=lambda: now[0])
        self.assertEqual((await request(app))[0], 200)
        self.assertEqual((await request(app))[0], 200)
        status, headers = await request(app)
        self.assertEqual(status, 429)
        self.assertEqual(headers[b'retry-after'], b'60')
        self.assertEqual((await request(app, ip='192.0.2.2'))[0], 200)
        now[0] = 60
        self.assertEqual((await request(app))[0], 200)

    async def test_auth_budget_shared_across_auth_endpoints(self):
        app = security.RateLimitMiddleware(endpoint, auth_requests=1)
        self.assertEqual((await request(app, '/api/v1/auth/login', method='POST'))[0], 200)
        self.assertEqual((await request(app, '/api/v1/auth/password/forgot', method='POST'))[0], 429)
        self.assertEqual((await request(app))[0], 200)

    async def test_untrusted_forwarded_header_cannot_bypass_limit(self):
        app = security.RateLimitMiddleware(endpoint, requests=1)
        await request(app, forwarded=b'198.51.100.1')
        self.assertEqual((await request(app, forwarded=b'198.51.100.2'))[0], 429)

    async def test_capacity_is_bounded_without_evicting_active_clients(self):
        now = [0]
        app = security.RateLimitMiddleware(endpoint, max_clients=1, clock=lambda: now[0])
        await request(app)
        self.assertEqual((await request(app, ip='192.0.2.2'))[0], 429)
        self.assertEqual(len(app.clients), 1)
        now[0] = 60
        self.assertEqual((await request(app, ip='192.0.2.2'))[0], 200)

    async def test_headers_apply_to_429_and_hsts_only_on_https(self):
        app = security.SecurityHeadersMiddleware(security.RateLimitMiddleware(endpoint, requests=1))
        _, headers = await request(app)
        self.assertNotIn(b'strict-transport-security', headers)
        status, headers = await request(app, scheme='https')
        self.assertEqual(status, 429)
        self.assertEqual(headers[b'x-content-type-options'], b'nosniff')
        self.assertEqual(headers[b'x-frame-options'], b'DENY')
        self.assertEqual(headers[b'cache-control'], b'no-store')
        self.assertEqual(headers[b'strict-transport-security'], b'max-age=31536000')

    async def test_health_remains_available(self):
        app = security.RateLimitMiddleware(endpoint, requests=1)
        await request(app)
        await request(app)
        self.assertEqual((await request(app, '/healthz'))[0], 200)
