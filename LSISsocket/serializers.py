from rest_framework import serializers
from .models import MemoryGroup, Variable, SocketClientConfig, SocketClientStatus, SocketClientLog, SocketClientCommand

# 코어 모델 참조 (MemoryGroup/Variable/DataName/ProjectVersion/Device)
from corecode.models import DataName as CoreDataName, Device as CoreDevice, Adapter as CoreAdapter

class SocketClientStatusSerializer(serializers.ModelSerializer):
    config = serializers.PrimaryKeyRelatedField(queryset=SocketClientConfig.objects.all())
    # 추가: 연결된 설정의 이름
    configName = serializers.CharField(source='config.name', read_only=True)
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
    # 추가: 연결된 설정의 이름
    configName = serializers.CharField(source='config.name', read_only=True)
    class Meta:
        model = SocketClientLog
        exclude = ('is_deleted',)

class SocketClientCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientCommand
        exclude = ('is_deleted',)

# -----------------------------
# MemoryGroup/Variable 직렬화기 (코어 모델 참조)
# -----------------------------
class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    # 그룹 기준 주소 사용 여부 노출
    use_group_base_address = serializers.BooleanField(required=False, default=False, help_text='True이면 변수 주소가 그룹의 start_address를 기준으로 해석됩니다.')
    group = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), required=False, allow_null=True, help_text='소속 MemoryGroup ID(선택)')
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
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'use_group_base_address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes'
        ]
        
    def get_device_address(self, obj):
        unit_map = {
            'bit': ('X', 16),
            'byte': ('B', 2),
            'word': ('W', 1),
            'dword': ('D', 0.5),
        }
        unit_key = (obj.unit or '').lower()
        unit_symbol, multiplier = unit_map.get(unit_key, ('', 1))

        try:
            offset_val = float(obj.offset) if obj.offset is not None else 0.0
        except Exception:
            offset_val = 0.0

        # 그룹 기준 주소 사용이면 그룹의 start_address를 더해서 실제 주소 계산
        base = 0.0
        try:
            if getattr(obj, 'use_group_base_address', False) and getattr(obj, 'group', None) is not None:
                base = float(getattr(obj.group, 'start_address', 0) or 0)
        except Exception:
            base = 0.0

        physical_addr = float(obj.address or 0) + base + offset_val
        addr_int = int(physical_addr * multiplier)
        return f"%{obj.device}{unit_symbol}{addr_int}"

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False, required=False, help_text='이 그룹에 포함된 변수 목록 (선택)')
    # 공용 변수 기반 복제 옵션 (ProjectVersion 제거 구조에 맞게 단순 복제)
    clone_from_group = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), write_only=True, required=False, allow_null=True, help_text='공용 변수 템플릿으로 사용할 MemoryGroup ID(선택)')
    # 추가: Adapter/Device FK 노출 (모델 필드는 대문자이므로 source로 매핑)
    adapter = serializers.PrimaryKeyRelatedField(queryset=CoreAdapter.objects.all(), required=False, allow_null=True, source='Adapter', help_text='연결 어댑터 ID(선택)')
    device = serializers.PrimaryKeyRelatedField(queryset=CoreDevice.objects.all(), required=False, allow_null=True, source='Device', help_text='연결 장치 ID(선택)')
    # 추가: 이름 필드 노출
    adapterName = serializers.CharField(source='Adapter.name', read_only=True)
    deviceName = serializers.CharField(source='Device.name', read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'description', 'size_byte', 'start_address', 'adapter', 'adapterName', 'device', 'deviceName', 'variables',
            'clone_from_group'
        ]

    def _resolve_dataname(self, name_val):
        # name_val은 PK(int) 또는 객체일 수 있음
        if name_val is None:
            return None
        if isinstance(name_val, CoreDataName):
            return name_val
        try:
            return CoreDataName.objects.get(pk=name_val)
        except Exception:
            raise serializers.ValidationError({ 'name': f"DataName (id={name_val})을(를) 찾을 수 없습니다." })

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        template_group = validated_data.pop('clone_from_group', None)
        group = MemoryGroup.objects.create(**validated_data)

        # 1) 명시 변수가 오면 그대로 생성
        if variables_data:
            for var_data in variables_data:
                name_val = var_data.get('name')
                name_obj = self._resolve_dataname(name_val)
                Variable.objects.create(
                    group=group,
                    name=name_obj,
                    device=var_data.get('device'),
                    address=var_data.get('address'),
                    use_group_base_address=var_data.get('use_group_base_address', False),
                    data_type=var_data.get('data_type'),
                    unit=var_data.get('unit'),
                    scale=var_data.get('scale', 1),
                    offset=var_data.get('offset', 0),
                    attributes=var_data.get('attributes', []),
                )
            return group

        # 2) 템플릿 그룹이 있으면 복제
        if template_group:
            try:
                for v in template_group.variables.all():
                    Variable.objects.create(
                        group=group,
                        name=v.name,
                        device=v.device,
                        address=v.address,
                        use_group_base_address=v.use_group_base_address if hasattr(v, 'use_group_base_address') else False,
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
        variables_data = validated_data.pop('variables', None)
        # 기본 필드 업데이트
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                name_val = var_data.get('name')
                name_obj = self._resolve_dataname(name_val)
                Variable.objects.create(
                    group=instance,
                    name=name_obj,
                    device=var_data.get('device'),
                    address=var_data.get('address'),
                    use_group_base_address=var_data.get('use_group_base_address', False),
                    data_type=var_data.get('data_type'),
                    unit=var_data.get('unit'),
                    scale=var_data.get('scale', 1),
                    offset=var_data.get('offset', 0),
                    attributes=var_data.get('attributes', []),
                )
        return instance

