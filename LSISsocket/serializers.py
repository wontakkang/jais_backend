from rest_framework import serializers
from .models import SocketClientConfig, SocketClientLog

class SocketClientConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientConfig
        fields = '__all__'

class SocketClientLogSerializer(serializers.ModelSerializer):
    config = serializers.StringRelatedField()  # 또는 PrimaryKeyRelatedField 등 필요에 따라 변경
    class Meta:
        model = SocketClientLog
        fields = '__all__'