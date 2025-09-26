from rest_framework import serializers
from .models import *

# 코어 모델 참조 (MemoryGroup/Variable/DataName/ProjectVersion/Device)
from corecode.models import MemoryGroup as CoreMemoryGroup, Variable as CoreVariable, DataName as CoreDataName, ProjectVersion as CoreProjectVersion, Device as CoreDevice
# from corecode.models import Adapter as CoreAdapter  # 제거: Adapter 직렬화기는 corecode로 이전됨

class SocketClientStatusSerializer(serializers.ModelSerializer):
    config = serializers.PrimaryKeyRelatedField(queryset=SocketClientConfig.objects.all())
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
    config = serializers.PrimaryKeyRelatedField(queryset=SocketClientConfig.objects.all())
    class Meta:
        model = SocketClientLog
        exclude = ('is_deleted',)

class SocketClientCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientCommand
        exclude = ('is_deleted',)

# SensorNodeConfigSerializer와 ControlNodeConfigSerializer는 MCUnode로 이전됨

# -----------------------------
# MemoryGroup/Variable 직렬화기 (코어 모델 참조)
# -----------------------------
class LSISVariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    group = serializers.PrimaryKeyRelatedField(queryset=CoreMemoryGroup.objects.all(), required=False, allow_null=True, help_text='소속 MemoryGroup ID(선택)')
    name = serializers.PrimaryKeyRelatedField(queryset=CoreDataName.objects.all(), help_text='연결된 DataName ID')
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]'
    )
    # 모델과 동일한 타입으로 정정
    device = serializers.CharField(max_length=2, help_text='장치 종류 코드(예: D/M/R)')
    address = serializers.FloatField(help_text='장치 내 주소(숫자). 예: 100')

    class Meta:
        model = CoreVariable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes'
        ]

    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        try:
            addr_int = int(float(obj.address)) if obj.address is not None else 0
        except Exception:
            addr_int = 0
        return f"%{obj.device}{unit_symbol}{addr_int}"

class LSISMemoryGroupSerializer(serializers.ModelSerializer):
    variables = LSISVariableSerializer(many=True, read_only=False, required=False, help_text='이 그룹에 포함된 변수 목록 (선택)')
    project_version = serializers.PrimaryKeyRelatedField(queryset=CoreProjectVersion.objects.all(), help_text='소속 ProjectVersion ID. 예: 7')
    project_id = serializers.SerializerMethodField(read_only=True)
    # 공용 변수 기반 복제 옵션
    clone_from_group = serializers.PrimaryKeyRelatedField(queryset=CoreMemoryGroup.objects.all(), write_only=True, required=False, allow_null=True, help_text='공용 변수 템플릿으로 사용할 MemoryGroup ID(선택)')
    adjust_address = serializers.BooleanField(write_only=True, required=False, default=True, help_text='시작주소 차이만큼 변수 address를 자동 보정할지 여부(기본 true)')

    class Meta:
        model = CoreMemoryGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'start_device', 'start_address', 'size_byte', 'variables',
            'clone_from_group', 'adjust_address'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        template_group = validated_data.pop('clone_from_group', None)
        adjust_address = validated_data.pop('adjust_address', True)
        group = CoreMemoryGroup.objects.create(**validated_data)

        # 1) 명시 변수가 오면 그대로 생성
        if variables_data:
            for var_data in variables_data:
                CoreVariable.objects.create(group=group, **var_data)
            return group

        # 2) 템플릿 그룹이 있으면 복제
        if template_group:
            try:
                address_delta = 0
                if adjust_address:
                    try:
                        address_delta = int(group.start_address) - int(template_group.start_address)
                    except Exception:
                        address_delta = 0
                for v in template_group.variables.all():
                    CoreVariable.objects.create(
                        group=group,
                        name=v.name,
                        device=v.device,
                        address=int(v.address) + address_delta if isinstance(v.address, (int, float)) else v.address,
                        data_type=v.data_type,
                        unit=v.unit,
                        scale=v.scale,
                        offset=v.offset,
                        attributes=v.attributes,
                    )
            except Exception as e:
                raise serializers.ValidationError({"clone_from_group": f"변수 복제 실패: {str(e)}"})
        return group

    def update(self, instance, validated_data):
        # 복제 관련 필드는 업데이트에서 무시
        validated_data.pop('clone_from_group', None)
        validated_data.pop('adjust_address', None)
        variables_data = validated_data.pop('variables', None)
        # 기본 필드 업데이트
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                CoreVariable.objects.create(group=instance, **var_data)
        return instance
