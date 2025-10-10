from rest_framework import serializers
from .models import *
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
        
class AdapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adapter
        fields = '__all__'
