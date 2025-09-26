from django.shortcuts import render
from rest_framework import viewsets
from LSISsocket.models import SensorNodeConfig, ControlNodeConfig
from .serializers import SensorNodeConfigSerializer, ControlNodeConfigSerializer

class SensorNodeConfigViewSet(viewsets.ModelViewSet):
    queryset = SensorNodeConfig.objects.all()
    serializer_class = SensorNodeConfigSerializer

class ControlNodeConfigViewSet(viewsets.ModelViewSet):
    queryset = ControlNodeConfig.objects.all()
    serializer_class = ControlNodeConfigSerializer

# Create your views here.
