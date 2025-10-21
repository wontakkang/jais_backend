from django.db import models
from django.core.validators import RegexValidator

class MCUNodeConfig(models.Model):
    """MCU 노드 설정 모델

    - node_type: 'sensor' 또는 'control' 중 선택
    - serial: MCU와 통신하는 시리얼 데이터를 16진수 문자열로 저장 (예: '4653500D004C003C')
    - rs485_channel / baudrate: RS-485 통신 구성 정보
    """

    TYPE_SENSOR = 'sensor'
    TYPE_CONTROL = 'control'
    TYPE_CHOICES = [
        (TYPE_SENSOR, 'Sensor'),
        (TYPE_CONTROL, 'Control'),
    ]

    name = models.CharField(max_length=100, help_text='노드 이름')
    node_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_SENSOR)

    # 소속 통합제어기(옵션): IoTControllerConfig와 FK 연결
    controller = models.ForeignKey('IoTControllerConfig', null=True, blank=True, on_delete=models.CASCADE, related_name='nodes', help_text='소속 통합제어기 (옵션)')

    # HEX 문자열만 허용하도록 정규표현식 검증기 사용
    hex_validator = RegexValidator(regex=r'^[0-9A-Fa-f]+$', message='16진수 문자열만 허용합니다.')
    serial = models.CharField(
        max_length=256,
        validators=[hex_validator],
        help_text="예: 4653500D004C003C (HEX 문자열, 바이트 단위로 저장됩니다)"
    )

    rs485_channel = models.PositiveIntegerField(null=True, blank=True, help_text='RS-485 채널 번호 (옵션)')
    baudrate = models.PositiveIntegerField(default=19200, help_text='통신 속도 (예: 9600)')

    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'MCU 노드 설정'
        verbose_name_plural = 'MCU 노드 설정'

    def clean(self):
        """추가 검증: HEX 문자열 길이는 바이트 단위로 짝수여야 함."""
        super().clean()
        if self.serial and len(self.serial) % 2 != 0:
            from django.core.exceptions import ValidationError
            raise ValidationError({'serial': 'HEX 문자열 길이는 짝수여야 합니다 (바이트 단위).'})

    def get_serial_bytes(self):
        """저장된 HEX 문자열을 바이트로 반환합니다."""
        try:
            return bytes.fromhex(self.serial)
        except ValueError:
            return b''

    def __str__(self):
        return f"{self.name} ({self.node_type})"

class IoTControllerConfig(models.Model):
    """통합제어기(IoT Controller) 모델

    - serial: HEX 문자열로 저장
    - latitude / longitude: 설치 위치 (GPS)
    - installation_address: 설치 주소(문자열)
    - 하위 MCU 노드는 MCUNodeConfig.controller FK로 연결됨
    """

    name = models.CharField(max_length=100, help_text='통합제어기 이름')

    # 별도 hex validator 사용 (중복 정의는 허용)
    controller_hex_validator = RegexValidator(regex=r'^[0-9A-Fa-f]+$', message='16진수 문자열만 허용합니다.')
    serial = models.CharField(
        max_length=256,
        validators=[controller_hex_validator],
        help_text='예: 4653500D004C003C (HEX 문자열, 바이트 단위로 저장됩니다)'
    )

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text='위도 (예: 37.123456)')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text='경도 (예: 127.123456)')
    installation_address = models.TextField(null=True, blank=True, help_text='설치 주소')

    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '통합제어기 설정'
        verbose_name_plural = '통합제어기 설정'

    def clean(self):
        """추가 검증: HEX 문자열 길이는 바이트 단위로 짝수여야 함."""
        super().clean()
        if self.serial and len(self.serial) % 2 != 0:
            from django.core.exceptions import ValidationError
            raise ValidationError({'serial': 'HEX 문자열 길이는 짝수여야 합니다 (바이트 단위).'})

    def get_serial_bytes(self):
        """저장된 HEX 문자열을 바이트로 반환합니다."""
        try:
            return bytes.fromhex(self.serial)
        except ValueError:
            return b''

    def __str__(self):
        return f"{self.name}"
