from rest_framework import serializers
from .models import *

class SocketClientStatusSerializer(serializers.ModelSerializer):
    config = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = SocketClientStatus
        fields = '__all__'
    
class SocketClientConfigSerializer(serializers.ModelSerializer):
    detailedStatus = serializers.SerializerMethodField()
    class Meta:
        model = SocketClientConfig
        exclude = ('is_deleted',)
        read_only_fields = ['id']

    def get_detailedStatus(self, obj):
        status = obj.status_logs.order_by('-updated_at').first()
        if status:
            return SocketClientStatusSerializer(status).data
        return None

    def validate_name(self, value):
        if self.instance is None and SocketClientConfig.objects.filter(name=value).exists():
            raise serializers.ValidationError("같은 이름의 게이트웨이 노드가 이미 존재합니다.")
        return value

    def create(self, validated_data):
        # ✅ force_insert 방지 → 명시적 save()
        instance = SocketClientConfig(**validated_data)
        instance.save()
        
        # SocketClientStatus 생성
        SocketClientStatus.objects.create(config=instance)
        
        return instance
    
        
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
