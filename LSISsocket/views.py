from rest_framework import viewsets
from .models import SocketClientConfig, SocketClientLog
from .serializers import SocketClientConfigSerializer, SocketClientLogSerializer

class SocketClientConfigViewSet(viewsets.ModelViewSet):
    queryset = SocketClientConfig.objects.all()
    serializer_class = SocketClientConfigSerializer

class SocketClientLogViewSet(viewsets.ModelViewSet):
    queryset = SocketClientLog.objects.all()
    serializer_class = SocketClientLogSerializer
