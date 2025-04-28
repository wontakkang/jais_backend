from django.urls import path
from websocket.consumers import MyWebSocketConsumer

websocket_urlpatterns = [
    path('ws/some_path/', MyWebSocketConsumer.as_asgi()),
]