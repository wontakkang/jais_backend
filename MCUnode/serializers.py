from rest_framework import serializers
from LSISsocket.models import SensorNodeConfig, ControlNodeConfig

class SensorNodeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorNodeConfig
        exclude = ('is_deleted',)

class ControlNodeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlNodeConfig
        exclude = ('is_deleted',)
