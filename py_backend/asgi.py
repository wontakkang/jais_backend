"""
ASGI config for py_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import logging

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'py_backend.settings')

application = get_asgi_application()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('py_backend.asgi')

django_asgi_app = get_asgi_application()

# Import websocket handler directly from utils to avoid import-time side effects
try:
    from utils.ws_log import websocket_app as ws_log_app  # type: ignore
except Exception:
    ws_log_app = None

async def application(scope, receive, send):
    """Dispatch ASGI connections: websocket (/ws/logging-tail) -> ws_log_app, http -> Django."""
    try:
        typ = scope.get('type')
        path = scope.get('path', '')
    except Exception:
        typ = None
        path = ''

    # Log incoming ASGI scopes for debugging connection attempts
    try:
        logger.info('ASGI incoming connection: type=%s path=%s', typ, path)
        # log query string and Origin header to diagnose websocket handshake failures
        try:
            q = scope.get('query_string') or b''
            logger.info('ASGI scope query_string: %s', (q[:200] if isinstance(q, (bytes, bytearray)) else str(q)))
        except Exception:
            pass
        try:
            hdrs = scope.get('headers') or []
            # headers are list of [name, value] bytes pairs
            hdr_map = {k.decode('latin1'): v.decode('latin1') for k, v in hdrs if isinstance(k, (bytes, bytearray))}
            # log common headers useful for WS: origin, host, upgrade
            logger.info('ASGI scope headers (origin/host/upgrade): origin=%s host=%s upgrade=%s', hdr_map.get('origin'), hdr_map.get('host'), hdr_map.get('upgrade'))
        except Exception:
            pass
    except Exception:
        pass

    if typ == 'websocket' and path.startswith('/ws/logging-tail'):
        if ws_log_app is None:
            logger.error('websocket_app not available to handle request')
            try:
                await send({'type': 'websocket.close', 'code': 1011})
            except Exception:
                pass
            return
        # call the websocket ASGI app directly
        try:
            await ws_log_app(scope, receive, send)
        except Exception:
            logger.exception('Error while handling websocket in ws_log_app')
            try:
                await send({'type': 'websocket.close', 'code': 1011})
            except Exception:
                pass
        return

    if typ == 'http':
        await django_asgi_app(scope, receive, send)
        return

    # Other websocket paths: reject politely
    if typ == 'websocket':
        try:
            await send({'type': 'websocket.close', 'code': 1000})
        except Exception:
            pass
        return

    # Fallback to Django for anything else
    await django_asgi_app(scope, receive, send)
