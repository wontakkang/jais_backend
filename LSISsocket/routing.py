from django.urls import path
from LSISsocket.consumers import LSISWebSocketConsumer

websocket_urlpatterns = [
    path('ws/lsis/', LSISWebSocketConsumer.as_asgi()),
]