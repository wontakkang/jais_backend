from rest_framework import serializers
from .models import *

class SocketClientConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientConfig
        exclude = ('is_deleted',)

class SocketClientLogSerializer(serializers.ModelSerializer):
    config = serializers.StringRelatedField()  # 또는 PrimaryKeyRelatedField 등 필요에 따라 변경
    class Meta:
        model = SocketClientLog
        exclude = ('is_deleted',)

class SocketClientCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientCommand
        exclude = ('is_deleted',)

class SensorNodeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorNodeConfig
        exclude = ('is_deleted',)

class ControlNodeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlNodeConfig
        exclude = ('is_deleted',)

class AdapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adapter
        exclude = ('is_deleted',)