from channels.routing import ProtocolTypeRouter, URLRouter
from LSISsocket.routing import websocket_urlpatterns as lsis_websocket_urlpatterns
from websocket.routing import websocket_urlpatterns as websocket_websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        lsis_websocket_urlpatterns + websocket_websocket_urlpatterns
    ),
})