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
    detailedStatus = models.JSONField(null=True, blank=True)
    comm_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=True, help_text="사용 여부")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    zone_style = models.JSONField(null=True, blank=True, help_text="존 스타일 정보")

    objects = ActiveManager()  # 기본 매니저: 삭제되지 않은 것만
    all_objects = models.Manager()  # 전체(삭제 포함) 매니저

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        log_data = None
        if self.pk:
            orig = SocketClientConfig.objects.get(pk=self.pk)
            if self.detailedStatus['ERROR CODE'] == 0:
                if orig.detailedStatus != self.detailedStatus:
                    self.comm_at = timezone.now()
                    log_data = {
                        "detailedStatus": self.detailedStatus,
                    }
            else:
                if orig.detailedStatus != self.detailedStatus:
                    self.comm_at = timezone.now()
                    log_data = {
                        "detailedStatus": self.detailedStatus,
                        "message": self.detailedStatus['message'],
                        "error_code": self.detailedStatus['ERROR CODE'],
                    }
        else:
            if self.detailedStatus is not None:
                self.comm_at = timezone.now()
                log_data = {
                    "detailedStatus": self.detailedStatus,
                    "message": "First communication"
                }
        super().save(*args, **kwargs)
        if log_data:
            self.logs.create(**log_data)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

class ActiveLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

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
        'Adapter',
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

class ActiveAdapterManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Adapter(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="어댑터 이름")
    description = models.TextField(null=True, blank=True, help_text="설명")
    protocol = models.CharField(max_length=50, help_text="프로토콜 종류 (예: TCP, MQTT, HTTP 등)")
    config = models.JSONField(null=True, blank=True, help_text="어댑터별 추가 설정값")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    objects = ActiveAdapterManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()    # 전체(삭제 포함) 조회

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

    def __str__(self):
        return self.name
