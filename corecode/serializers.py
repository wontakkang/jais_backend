from rest_framework import serializers
from .models import *
from utils.control import __all__ as control_methods_list # ControlLogic use_method choices
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

User = get_user_model()

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

class ControlVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=ControlGroup.objects.all(), required=False, allow_null=True, help_text='속한 ControlGroup ID(선택). 예: 3', style={'example': 3})
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID. 예: 12', style={'example': 12})
    applied_logic = serializers.PrimaryKeyRelatedField(queryset=ControlLogic.objects.all(), help_text='적용할 ControlLogic ID. 예: 2', style={'example': 2})
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(예: ["감시","기록"])',
        style={'example': ['감시', '기록']}
    )

    class Meta:
        model = ControlVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'applied_logic', 'args', 'attributes'
        ]

    # create, update 메서드는 기본 동작으로 충분할 수 있으나, 필요시 오버라이드

class ControlGroupSerializer(serializers.ModelSerializer):
    control_variables_in_group = ControlVariableSerializer(many=True, read_only=False, required=False, help_text='그룹에 포함된 ControlVariable의 중첩 리스트 (선택)')
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all(), help_text='소속 ProjectVersion ID')
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'description', 'control_variables_in_group'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        control_variables_data = validated_data.pop('control_variables_in_group', [])
        group = ControlGroup.objects.create(**validated_data)
        for var_data in control_variables_data:
            ControlVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        control_variables_data = validated_data.pop('control_variables_in_group', None)
        
        # 기본 필드 업데이트
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        # project_version, group_id 등은 일반적으로 수정하지 않거나 특정 로직 필요
        instance.save()

        if control_variables_data is not None:
            # 기존 변수 삭제 후 새로 생성 (간단한 방식) 또는 개별 업데이트/삭제/생성 로직 구현
            instance.control_variables_in_group.all().delete()
            for var_data in control_variables_data:
                ControlVariable.objects.create(group=instance, **var_data)
        return instance

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
    calc_variables_in_group = CalcVariableSerializer(many=True, read_only=False, required=False) # related_name 변경 반영
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all(), help_text='소속 ProjectVersion ID')
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'description', 'calc_variables_in_group'
        ]
    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

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
        instance.save()
        if calc_variables_data is not None:
            instance.calc_variables_in_group.all().delete()
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=instance, **var_data)
        return instance

class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True, help_text='표현형 장치 주소 문자열. 예: "%DeviceW100"')
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
    # 명시적으로 device 필드를 노출하여 help_text 제공
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True, help_text='연결된 장치(Device) ID')
    address = serializers.IntegerField(help_text='장치 내 주소(정수). 예: 100', style={'example': 100})
    class Meta:
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes'
        ]
    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        return f"%{obj.device}{unit_symbol}{int(obj.address)}"

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False, required=False, help_text='이 그룹에 포함된 변수 목록 (선택)')
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all(), help_text='소속 ProjectVersion ID. 예: 7', style={'example': 7})
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'start_device', 'start_address', 'size_byte', 'variables'
        ]
    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = MemoryGroup.objects.create(**validated_data)
        for var_data in variables_data:
            Variable.objects.create(group=group, **var_data)
        return group

    def update(self, instance, validated_data):
        variables_data = validated_data.pop('variables', None)
        instance.name = validated_data.get('name', instance.name)
        # ... other fields ...
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                Variable.objects.create(group=instance, **var_data)
        return instance

class ProjectVersionSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), help_text='소속 Project ID. 예: 2', style={'example': 2})
    groups = MemoryGroupSerializer(many=True, read_only=False, required=False, help_text='메모리 그룹(선택)')
    calc_groups = CalcGroupSerializer(many=True, read_only=False, required=False, help_text='계산 그룹(선택)')
    control_groups = ControlGroupSerializer(many=True, read_only=False, required=False, help_text='제어 그룹(선택)')

    class Meta:
        model = ProjectVersion
        fields = [
            'id', 'project', 'version', 'created_at', 'updated_at', 'note', 
            'groups', 'calc_groups', 'control_groups'
        ]

    def create(self, validated_data):
        groups_data = validated_data.pop('groups', [])
        calc_groups_data = validated_data.pop('calc_groups', [])
        control_groups_data = validated_data.pop('control_groups', [])
        
        project_version = ProjectVersion.objects.create(**validated_data)
        
        for group_data in groups_data:
            variables_data = group_data.pop('variables', [])
            memory_group = MemoryGroup.objects.create(project_version=project_version, **group_data)
            for var_data in variables_data:
                Variable.objects.create(group=memory_group, **var_data)
                
        for group_data in calc_groups_data:
            calc_variables_data = group_data.pop('calc_variables_in_group', [])
            calc_group = CalcGroup.objects.create(project_version=project_version, **group_data)
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=calc_group, **var_data)

        for group_data in control_groups_data:
            control_variables_data = group_data.pop('control_variables_in_group', [])
            control_group = ControlGroup.objects.create(project_version=project_version, **group_data)
            for var_data in control_variables_data:
                ControlVariable.objects.create(group=control_group, **var_data)
                
        return project_version

class ProjectSerializer(serializers.ModelSerializer):
    versions = ProjectVersionSerializer(many=True, read_only=True)
    # device 필드는 ForeignKey이므로, 필요시 DeviceSerializer 등으로 표현 가능
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), allow_null=True, required=False, help_text='연결된 Device ID(선택)', style={'example': 4})

    class Meta:
        model = Project
        fields = [
            'id', 'name' ,'device', 'description', 'created_at', 'updated_at', 'versions'
        ]

    def validate_name(self, value):
        # 인스턴스가 존재하고 (업데이트 시) 이름이 변경되지 않았으면 유효성 검사 통과
        if self.instance and self.instance.name == value:
            return value
        # 새 프로젝트 생성 시 또는 이름 변경 시 중복 검사
        if Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("같은 이름의 프로젝트가 이미 존재합니다.")
        return value

class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['id', 'user', 'preferences']
        read_only_fields = ['id', 'user']

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
