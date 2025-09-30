from sqlite3 import IntegrityError
from django.db import models
from django.db.models import JSONField
from django.utils import timezone

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SocketClientConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    host = models.CharField(max_length=100, help_text="클라이언트 IP", null=True, blank=True)
    port = models.IntegerField(help_text="클라이언트 포트", null=True, blank=True)
    blocks = models.JSONField(help_text='[{"count": 700, "memory": "%MB", "address": "0", "func_name": "continuous_read_bytes"}]', null=True, blank=True)
    cron = models.JSONField(help_text="cron 설정값", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_used = models.BooleanField(default=True, help_text="사용 여부")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    zone_style = models.JSONField(null=True, blank=True, help_text="존 스타일 정보")

    objects = ActiveManager()  # 기본 매니저: 삭제되지 않은 것만
    all_objects = models.Manager()  # 전체(삭제 포함) 매니저

    def __str__(self):
        return self.name

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()
        
class ActiveLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SocketClientStatus(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='status_logs')
    updated_at = models.DateTimeField(auto_now=True)
    detailedStatus = models.JSONField(null=True, blank=True)
    error_code = models.IntegerField(default=0)
    message = models.TextField(null=True, blank=True)
    values= models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.system_status} (code: {self.error_code}) @ {self.updated_at}"

class SocketClientLog(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='logs')
    detailedStatus = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True, blank=True)
    error_code = models.IntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    objects = ActiveLogManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()  # 전체(삭제 포함) 조회

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

    def __str__(self):
        return f"{self.config.name} - {self.created_at}"

class ActiveCommandLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SocketClientCommand(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='command_logs')
    user = models.CharField(max_length=40, null=True, blank=True, verbose_name='보낸 유저')
    command = models.CharField(max_length=100, help_text="제어항목 또는 명령 이름")
    value = models.CharField(max_length=255, null=True, blank=True, help_text="제어값")
    control_time = models.DateTimeField(auto_now_add=True, verbose_name='제어시각')
    payload = models.JSONField(null=True, blank=True, help_text="보낸 명령의 상세 데이터(바이트 등)")
    response = models.JSONField(null=True, blank=True, help_text="기기로부터 받은 응답(있다면)")
    message = models.TextField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    objects = ActiveCommandLogManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()       # 전체(삭제 포함) 조회

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

    def __str__(self):
        return f"{self.config.name} - {self.command} - {self.control_time}"

class ActiveSensorNodeManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SensorNodeConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    gateway = models.ForeignKey(
        'SocketClientConfig',
        on_delete=models.SET_NULL,
        related_name='sensor_nodes',
        null=True, blank=True,
        help_text="게이트웨이 노드(없으면 단독형)"
    )
    ip = models.CharField(max_length=100, help_text="센서노드 IP", null=True, blank=True)
    port = models.IntegerField(help_text="센서노드 포트", null=True, blank=True)
    sensor_type = models.CharField(max_length=50, help_text="센서 타입", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    adapter = models.ForeignKey(
        'corecode.Adapter',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="데이터 읽기/쓰기 어댑터(프로토콜) 선택"
    )

    objects = ActiveSensorNodeManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()       # 전체(삭제 포함) 조회

    def get_ip(self):
        if self.gateway:
            return self.gateway.host
        return self.ip

    def get_port(self):
        if self.gateway:
            return self.gateway.port
        return self.port

    def __str__(self):
        return self.name

class ActiveControlNodeManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class ControlNodeConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    gateway = models.ForeignKey(
        'SocketClientConfig',
        on_delete=models.SET_NULL,
        related_name='control_nodes',
        null=True, blank=True,
        help_text="게이트웨이 노드(없으면 단독형)"
    )
    ip = models.CharField(max_length=100, help_text="제어노드 IP", null=True, blank=True)
    port = models.IntegerField(help_text="제어노드 포트", null=True, blank=True)
    control_type = models.CharField(max_length=50, help_text="제어 타입", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveControlNodeManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()        # 전체(삭제 포함) 조회

    def get_ip(self):
        if self.gateway:
            return self.gateway.host
        return self.ip

    def get_port(self):
        if self.gateway:
            return self.gateway.port
        return self.port

    def __str__(self):
        return self.name


class MemoryGroup(models.Model):
    """
    메모리 그룹 모델 (프로젝트 버전 의존성 제거됨)
    각 그룹은 여러 Variable(변수)과 1:N 관계
    """
    # corecode 앱의 Adapter 모델을 명시적으로 참조하고 related_name을 고유하게 변경하여 충돌 방지
    Adapter = models.ForeignKey('corecode.Adapter', on_delete=models.SET_NULL, null=True, blank=True, related_name='lsissocket_memory_groups', help_text="이 그룹이 속한 어댑터")
    # corecode.Device와의 reverse accessor 이름이 corecode 앱과 충돌하므로 고유한 related_name 사용
    Device = models.ForeignKey('corecode.Device', on_delete=models.SET_NULL, null=True, blank=True, related_name='lsissocket_memory_groups')
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    size_byte = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Group {self.name}({self.size_byte})"

class Variable(models.Model):
    """
    메모리 그룹(MemoryGroup)에 속한 개별 변수 정보를 관리하는 모델
    """
    group = models.ForeignKey(MemoryGroup, on_delete=models.CASCADE, related_name='variables') # 기존 유지
    # corecode.DataName의 physical_variables 관련명이 corecode 앱과 충돌하므로 고유한 이름 사용
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='lsissocket_physical_variables')
    device = models.CharField(max_length=2)
    address = models.FloatField()
    data_type = models.CharField(max_length=10, choices=[
        ('bool', 'bool'), ('sint', 'sint'), ('usint', 'usint'), ('int', 'int'),
        ('uint', 'uint'), ('dint', 'dint'), ('udint', 'udint'), ('float', 'float'),
    ])
    unit = models.CharField(max_length=10, choices=[
        ('bit', 'bit'), ('byte', 'byte'), ('word', 'word'), ('dword', 'dword'),
    ])
    scale = models.FloatField(default=1)
    offset = models.FloatField(default=0)
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name} ({self.device}{self.address})"
