from rest_framework import serializers
from .models import *
from utils.control import __all__ as control_methods_list  # ControlLogic use_method choices
from utils.calculation import all_dict as calculation_all_dict  # DataNameSerializer choices에 사용
from utils.control import all_dict as control_all_dict
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
import inspect

User = get_user_model()

class UserPreferenceSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = UserPreference
        fields = ['user', 'preferences']

class DataNameSerializer(serializers.ModelSerializer):
    # combine calculation and control method keys for choices
    use_method = serializers.ChoiceField(
        choices=[(k, k) for k in list(calculation_all_dict.keys()) + list(control_all_dict.keys())],
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='데이터 이름에 연결된 처리 방법(선택). 예: "temperature_average"',
        style={'example': 'temperature_average'}
    )
    # JSON fields with basic validation
    method_args_desc = serializers.JSONField(required=False, allow_null=True)
    method_args_type = serializers.JSONField(required=False, allow_null=True)
    method_result = serializers.JSONField(required=False, allow_null=True)
    method_result_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = DataName
        fields = '__all__'

    def validate_method_args_desc(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('method_args_desc는 객체여야 합니다.')
        # keys should be strings and values should be string descriptions
        for k, v in value.items():
            if not isinstance(k, str):
                raise serializers.ValidationError('method_args_desc의 키는 문자열이어야 합니다.')
            if not isinstance(v, (str, int, float, bool)) and v is not None:
                raise serializers.ValidationError('method_args_desc의 값은 문자열(설명) 또는 null이어야 합니다.')
        return value

    def validate_method_args_type(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('method_args_type는 객체여야 합니다.')
        allowed = {'number', 'int', 'float', 'str', 'string', 'list', 'dict', 'bool', 'boolean'}
        for k, v in value.items():
            if not isinstance(k, str):
                raise serializers.ValidationError('method_args_type의 키는 문자열이어야 합니다.')
            if not isinstance(v, str):
                raise serializers.ValidationError('method_args_type의 값은 문자열이어야 합니다.')
            if v not in allowed:
                raise serializers.ValidationError(f"허용되지 않는 타입 '{v}' 입니다. 허용: {', '.join(sorted(allowed))}")
        return value

    def validate(self, attrs):
        # ensure use_method, if provided, matches available functions and that arg descriptions/types align with signature
        use_method = attrs.get('use_method') or getattr(self.instance, 'use_method', None)
        args_desc = attrs.get('method_args_desc', getattr(self.instance, 'method_args_desc', {}) or {})
        args_type = attrs.get('method_args_type', getattr(self.instance, 'method_args_type', {}) or {})

        if use_method:
            func = calculation_all_dict.get(use_method) or control_all_dict.get(use_method)
            if not func:
                raise serializers.ValidationError({'use_method': '지정한 메서드를 찾을 수 없습니다.'})
            try:
                sig = inspect.signature(func)
                params = [p for p in sig.parameters.keys()]
                # validate that provided arg descriptions/types reference valid parameters
                invalid_desc_keys = [k for k in args_desc.keys() if k not in params]
                if invalid_desc_keys:
                    raise serializers.ValidationError({'method_args_desc': f"존재하지 않는 인자: {invalid_desc_keys}"})
                invalid_type_keys = [k for k in args_type.keys() if k not in params]
                if invalid_type_keys:
                    raise serializers.ValidationError({'method_args_type': f"존재하지 않는 인자: {invalid_type_keys}"})
            except ValueError:
                # some builtins or C-implemented functions may not have signatures
                pass
        return attrs

class ControlLogicSerializer(serializers.ModelSerializer):
    use_method = serializers.ChoiceField(choices=[(method, method) for method in control_methods_list], help_text='제어 로직에서 사용할 메서드 이름(필수). 예: "pid_control"', style={'example': 'pid_control'})
    method_args_desc = serializers.JSONField(required=False, allow_null=True)
    method_args_type = serializers.JSONField(required=False, allow_null=True)
    method_result = serializers.JSONField(required=False, allow_null=True)
    method_result_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ControlLogic
        fields = [
            'id', 'name', 'use_method', 'method_description', 
            'method_args_desc', 'method_result', 'method_args_type', 'method_result_type'
        ]

    def validate_method_args_desc(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('method_args_desc는 객체여야 합니다.')
        for k, v in value.items():
            if not isinstance(k, str):
                raise serializers.ValidationError('method_args_desc의 키는 문자열이어야 합니다.')
            if not isinstance(v, (str, int, float, bool)) and v is not None:
                raise serializers.ValidationError('method_args_desc의 값은 문자열(설명) 또는 null이어야 합니다.')
        return value

    def validate_method_args_type(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('method_args_type는 객체여야 합니다.')
        allowed = {'number', 'int', 'float', 'str', 'string', 'list', 'dict', 'bool', 'boolean'}
        for k, v in value.items():
            if not isinstance(k, str):
                raise serializers.ValidationError('method_args_type의 키는 문자열이어야 합니다.')
            if not isinstance(v, str):
                raise serializers.ValidationError('method_args_type의 값은 문자열이어야 합니다.')
            if v not in allowed:
                raise serializers.ValidationError(f"허용되지 않는 타입 '{v}' 입니다. 허용: {', '.join(sorted(allowed))}")
        return value

    def validate(self, attrs):
        use_method = attrs.get('use_method') or getattr(self.instance, 'use_method', None)
        args_desc = attrs.get('method_args_desc', getattr(self.instance, 'method_args_desc', {}) or {})
        args_type = attrs.get('method_args_type', getattr(self.instance, 'method_args_type', {}) or {})

        if use_method:
            func = control_all_dict.get(use_method)
            if not func:
                raise serializers.ValidationError({'use_method': '지정한 제어 메서드를 찾을 수 없습니다.'})
            try:
                sig = inspect.signature(func)
                params = [p for p in sig.parameters.keys()]
                invalid_desc_keys = [k for k in args_desc.keys() if k not in params]
                if invalid_desc_keys:
                    raise serializers.ValidationError({'method_args_desc': f"존재하지 않는 인자: {invalid_desc_keys}"})
                invalid_type_keys = [k for k in args_type.keys() if k not in params]
                if invalid_type_keys:
                    raise serializers.ValidationError({'method_args_type': f"존재하지 않는 인자: {invalid_type_keys}"})
            except ValueError:
                pass
        return attrs


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
                # if 'name' supplied, save to first_name by default
                name = validated_data.get('name')
                if name:
                    user.first_name = name
                    user.save()
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
        
class AdapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adapter
        fields = '__all__'
