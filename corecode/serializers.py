from rest_framework import serializers
from .models import *
from agriseed.models import Module, DeviceInstance, Facility  # 필요한 agriseed 모델만 사용
from utils.control import __all__ as control_methods_list  # ControlLogic use_method choices
from utils.calculation import all_dict  # DataNameSerializer choices에 사용
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

# 추가: agriseed.ControlGroup 별칭 임포트 (corecode.ControlGroup과 구분)
from agriseed.models import ControlGroup as AgriseedControlGroup

User = get_user_model()

class UserPreferenceSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = UserPreference
        fields = ['user', 'preferences']

class DataNameSerializer(serializers.ModelSerializer):
    use_method = serializers.ChoiceField(
        choices=[(k, k) for k in all_dict.keys()],
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='데이터 이름에 연결된 처리 방법(선택). 예: "temperature_average"',
        style={'example': 'temperature_average'}
    )
    class Meta:
        model = DataName
        fields = '__all__'

class ControlLogicSerializer(serializers.ModelSerializer):
    use_method = serializers.ChoiceField(choices=[(method, method) for method in control_methods_list], help_text='제어 로직에서 사용할 메서드 이름(필수). 예: "pid_control"', style={'example': 'pid_control'})
    class Meta:
        model = ControlLogic
        fields = [
            'id', 'name', 'use_method', 'method_description', 
            'method_args_desc', 'method_result', 'method_args_type', 'method_result_type'
        ]

# corecode.ControlGroup은 현재 변수 중첩이 없고 project_version/group_id 필드도 없음
class ControlGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'description', 'size_byte'
        ]

class CalcVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), required=False, allow_null=True, help_text='소속 CalcGroup ID(선택). 예: 4', style={'example': 4})
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID. 예: 8', style={'example': 8})
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]',
        style={'example': ['감시']}
    )
    # use_method는 models.py의 choices를 따름 (calculation_methods)
    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

class CalcGroupSerializer(serializers.ModelSerializer):
    # corecode.CalcGroup의 related_name은 calc_variables_in_group
    calc_variables_in_group = CalcVariableSerializer(
        many=True,
        read_only=False,
        required=False
    )

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'description', 'size_byte', 'calc_variables_in_group'
        ]

    def create(self, validated_data):
        calc_variables_data = validated_data.pop('calc_variables_in_group', [])
        group = CalcGroup.objects.create(**validated_data)
        for var_data in calc_variables_data:
            CalcVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        calc_variables_data = validated_data.pop('calc_variables_in_group', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.size_byte = validated_data.get('size_byte', instance.size_byte)
        instance.save()
        if calc_variables_data is not None:
            instance.calc_variables_in_group.all().delete()
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=instance, **var_data)
        return instance

class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True, help_text='표현형 장치 주소 문자열. 예: "%DW100"')
    group = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), required=False, allow_null=True, help_text='소속 MemoryGroup ID(선택)')
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID')
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]',
        style={'example': ['감시']}
    )
    # 모델에 맞게 CharField/FloatField 사용
    device = serializers.CharField(max_length=2, required=True, help_text='장치 코드(예: D, M 등 2자 이하)')
    address = serializers.FloatField(help_text='장치 내 주소(실수 가능). 예: 100.0', style={'example': 100.0})
    class Meta:
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes'
        ]
    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        try:
            addr_int = int(obj.address)
        except Exception:
            addr_int = obj.address
        return f"%{obj.device}{unit_symbol}{addr_int}"


class ControlValueSerializer(serializers.ModelSerializer):
    control_user = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ControlValue
        fields = '__all__'

class ControlValueHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlValueHistory
        fields = '__all__'

class LocationCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationCode
        fields = '__all__'

class LocationGroupSerializer(serializers.ModelSerializer):
    codes = LocationCodeSerializer(many=True, required=False)

    class Meta:
        model = LocationGroup
        fields = [
            'group_id', 'group_name', 'description', 'timezone',
            'created_at', 'updated_at', 'codes'
        ]

    def create(self, validated_data):
        codes_data = validated_data.pop('codes', [])
        group = LocationGroup.objects.create(**validated_data)
        for code in codes_data:
            LocationCode.objects.create(group=group, **code)
        return group

    def update(self, instance, validated_data):
        codes_data = validated_data.pop('codes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if codes_data is not None:
            instance.codes.all().delete()
            for code in codes_data:
                LocationCode.objects.create(group=instance, **code)
        return instance

class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, help_text='회원가입할 사용자 이름(소문자 권장)', style={'example': 'user01'})
    email = serializers.EmailField(required=False, allow_blank=True, help_text='이메일 주소(선택)', style={'example': 'user@example.com'})
    password = serializers.CharField(write_only=True, help_text='계정 비밀번호 (보안상 출력되지 않음)')
    name = serializers.CharField(required=False, allow_blank=True, help_text='실명 또는 표시 이름(선택)', style={'example': '홍길동'})

    def validate(self, attrs):
        # normalize username and validate uniqueness case-insensitively
        username = attrs.get('username', '')
        username = username.strip().lower()
        if not username:
            raise serializers.ValidationError({'username': '사용자 이름을 입력하세요.'})
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({'username': '이미 사용 중인 사용자 이름입니다.'})
        # validate password using Django validators
        password = attrs.get('password')
        try:
            validate_password(password)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        attrs['username'] = username
        return attrs

    def create(self, validated_data):
        # create user inside a transaction and translate DB integrity errors to validation errors
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data.get('email', ''),
                    password=validated_data['password']
                )
                return user
        except IntegrityError:
            # unique constraint violation or FK issue
            raise serializers.ValidationError({'username': '이미 사용 중인 사용자 이름입니다.'})

class DeviceCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCompany
        fields = '__all__'

class UserManualSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserManual
        fields = '__all__'

class DeviceSerializer(serializers.ModelSerializer):
    manufacturer = DeviceCompanySerializer(read_only=True)
    manufacturer_id = serializers.PrimaryKeyRelatedField(queryset=DeviceCompany.objects.all(), source='manufacturer', write_only=True, allow_null=True, required=False, help_text='제조사(DeviceCompany) ID(선택)', style={'example': 2})
    user_manuals = UserManualSerializer(many=True, read_only=True)
    user_manual_ids = serializers.PrimaryKeyRelatedField(queryset=UserManual.objects.all(), source='user_manuals', many=True, write_only=True, required=False, help_text='연결할 UserManual ID 리스트(선택)', style={'example': [5,6]})

    class Meta:
        model = Device
        fields = '__all__'

class DeviceInstanceSerializer(serializers.ModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True, help_text='장비(Device) ID (선택)')
    device_detail = DeviceSerializer(source='device', read_only=True)
    adapter = serializers.PrimaryKeyRelatedField(queryset=Adapter.objects.all(), required=False, allow_null=True, help_text='어댑터(Adapter) ID (선택)')
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), required=False, allow_null=True, help_text='소속 Module ID (선택)')
    # memory_groups를 쓰기 가능하게 변경 (PK 리스트)
    memory_groups = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), many=True, required=False, help_text='연결된 MemoryGroup ID 목록(선택)')
    # 제어/계산 그룹 연결 추가
    control_groups = serializers.PrimaryKeyRelatedField(queryset=AgriseedControlGroup.objects.all(), many=True, required=False, help_text='연결된 ControlGroup ID 목록(선택)')
    calc_groups = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), many=True, required=False, help_text='연결된 CalcGroup ID 목록(선택)')

    class Meta:
        model = DeviceInstance
        fields = [
            'id', 'name', 'device', 'device_detail', 'adapter', 'module',
            'serial_number', 'status', 'last_seen', 'location_within_module', 'install_date', 'is_active',
            'memory_groups', 'control_groups', 'calc_groups',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'device_detail']

    # ModelSerializer가 M2M 필드를 자동 처리하지만, 명시적으로 set 동작을 보장하기 위해 오버라이드(선택)
    def create(self, validated_data):
        mgs = validated_data.pop('memory_groups', []) if 'memory_groups' in validated_data else []
        cgs = validated_data.pop('control_groups', []) if 'control_groups' in validated_data else []
        ags = validated_data.pop('calc_groups', []) if 'calc_groups' in validated_data else []
        instance = DeviceInstance.objects.create(**validated_data)
        if mgs:
            instance.memory_groups.set(mgs)
        if cgs:
            instance.control_groups.set(cgs)
        if ags:
            instance.calc_groups.set(ags)
        return instance

    def update(self, instance, validated_data):
        mgs = validated_data.pop('memory_groups', None)
        cgs = validated_data.pop('control_groups', None)
        ags = validated_data.pop('calc_groups', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if mgs is not None:
            instance.memory_groups.set(mgs)
        if cgs is not None:
            instance.control_groups.set(cgs)
        if ags is not None:
            instance.calc_groups.set(ags)
        return instance

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'

class AdapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adapter
        fields = '__all__'

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False, required=False, help_text='이 그룹에 포함된 변수 목록 (선택)')
    # 연결된 Device/Adapter의 id 설정 및 name 조회
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), source='Device', required=False, allow_null=True, help_text='연결된 Device ID(선택)')
    device_name = serializers.CharField(source='Device.name', read_only=True)
    deviceName = serializers.CharField(source='Device.name', read_only=True)
    adapter = serializers.PrimaryKeyRelatedField(queryset=Adapter.objects.all(), source='Adapter', required=False, allow_null=True, help_text='연결된 Adapter ID(선택)')
    adapterName = serializers.CharField(source='Adapter.name', read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'description', 'size_byte',
            'adapter', 'adapterName',
            'device', 'device_name', 'deviceName',
            'variables'
        ]

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = MemoryGroup.objects.create(**validated_data)
        for var_data in variables_data:
            Variable.objects.create(group=group, **var_data)
        return group

    def update(self, instance, validated_data):
        variables_data = validated_data.pop('variables', None)
        # 필드 업데이트 (Device/Adapter 포함)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.size_byte = validated_data.get('size_byte', instance.size_byte)
        if 'Device' in validated_data:
            instance.Device = validated_data.get('Device')
        if 'Adapter' in validated_data:
            instance.Adapter = validated_data.get('Adapter')
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                Variable.objects.create(group=instance, **var_data)
        return instance