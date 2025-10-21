from rest_framework import serializers
from .models import MCUNodeConfig, IoTControllerConfig
from utils.protocol.MCU.config import DE_MCU_constants, CommandCode, get_command_format
from utils.protocol.MCU.utils import to_bytes
from utils.list_usb_ports import _list_serial_ports



class MCUNodeConfigSerializer(serializers.ModelSerializer):
    controller = serializers.PrimaryKeyRelatedField(queryset=IoTControllerConfig.objects.all(), allow_null=True, required=False)

    class Meta:
        model = MCUNodeConfig
        fields = '__all__'


class IoTControllerConfigSerializer(serializers.ModelSerializer):
    # 하위 MCU 노드 목록을 포함 (읽기 전용)
    nodes = MCUNodeConfigSerializer(many=True, read_only=True)

    class Meta:
        model = IoTControllerConfig
        fields = '__all__'

# Build command choices from CommandCode enum (only request commands ending with '_REQ')
COMMAND_CHOICES = [
    (member.name, member.name)
    for member in sorted(list(CommandCode), key=lambda m: m.name)
    if member.name.endswith("_REQ")
]

class FlexibleSerialField(serializers.Field):
    """Accept str, list, int, None from form or JSON and pass through for validation."""
    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('allow_null', True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        # Accept common types; return as-is for serializer.validate to normalize
        if data is None or data == '':
            return None
        if isinstance(data, (str, list, int)):
            return data
        # bytes may come from other places
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        raise serializers.ValidationError('serial_number must be a string, list, integer, or null')

    def to_representation(self, value):
        return value


class DE_MCUSerialRequestSerializer(serializers.Serializer):
    # default: free-text port, replaced with ChoiceField in __init__ when ports are available
    port = serializers.CharField(help_text='Serial port, e.g. COM3')
    command = serializers.ChoiceField(choices=COMMAND_CHOICES, help_text='MCU command (choice)')
    # Accept string (hex), list, int, null. Use FlexibleSerialField to avoid JSONField string-only issue in forms.
    serial_number = FlexibleSerialField(help_text='Hex string, list of ints, or integer')
    req_data = serializers.CharField(required=False, allow_blank=True, default='', help_text='Additional request data (if applicable)')
    checksum_type = serializers.CharField(required=False, default='xor_simple')
    firmware_file = serializers.FileField(required=False, allow_null=True, help_text='Firmware file for update commands')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            ports = _list_serial_ports()
            if ports:
                # replace port field with ChoiceField populated by available ports
                self.fields['port'] = serializers.ChoiceField(choices=ports, help_text='Serial port (choose from available ports)')
                # set a default initial value if not provided
                if not self.initial_data and ports:
                    self.initial_data = self.initial_data or {}
                    self.initial_data.setdefault('port', ports[0][0])
        except Exception:
            # keep default CharField if enumeration fails
            pass

    def validate(self, attrs):
        """Cross-field validation: normalize serial_number to bytes and validate its length
        against the selected command's *_FORMAT defined in DE_MCU_constants.
        """
        command = attrs.get('command')
        serial_val = attrs.get('serial_number')

        # If no serial provided, nothing to validate
        if serial_val is None or serial_val == '':
            attrs['serial_number'] = None
            return attrs

        # Normalize to bytes (raise ValidationError on failure)
        try:
            b = to_bytes(serial_val)
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError({'serial_number': str(e)})

        expected_len = 8
        if len(b) != expected_len:
            raise serializers.ValidationError({'serial_number': f'serial_number는 정확히 {expected_len}바이트여야 합니다. 전달된 길이: {len(b)}'})

        # Replace value with normalized bytes
        attrs['serial_number'] = b
        return attrs


# 새로 추가: context_store 상태를 반환하는 직렬화기
class StateEntrySerializer(serializers.Serializer):
    """Context store의 단일 장치 항목을 직렬화합니다.
    필드:
    - serial_number: 장치 식별자 (키)
    - status: STATUS 블록 (dict)
    - meta: Meta 블록 (dict)
    - job: Job 블록 (dict, 선택)
    - setup: SETUP 블록 (dict, 선택)
    """
    serial_number = serializers.CharField()
    status = serializers.JSONField(allow_null=True)
    meta = serializers.JSONField(allow_null=True)
    job = serializers.JSONField(allow_null=True, required=False)
    setup = serializers.JSONField(allow_null=True, required=False)

    def to_representation(self, instance):
        # instance는 dict 형태: {'serial_number':..., 'STATUS':..., 'Meta':..., 'Job':..., 'SETUP':...}
        return {
            'serial_number': instance.get('serial_number'),
            'status': instance.get('STATUS'),
            'meta': instance.get('Meta'),
            'job': instance.get('Job'),
            'setup': instance.get('SETUP'),
        }
