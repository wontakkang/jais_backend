from sqlite3 import IntegrityError
from django.db import models, transaction
from django.db.models import JSONField
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
import json

from utils.calculation import __all__ as calculation_methods
from utils.calculation import all_dict
from utils.control import __all__ as control_methods
from utils.control import all_dict as control_methods_dict

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class ActiveLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class ActiveCommandLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
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


class ControlGroup(models.Model):
    """
    제어 그룹 모델
    """
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    size_byte = models.PositiveIntegerField(null=True, blank=True, help_text="그룹 크기 (바이트 단위)")

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"ControlGroup ({self.name})"


class ControlVariable(models.Model):
    group = models.ForeignKey(ControlGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='agriseed_control_variables_in_group')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='agriseed_as_control_variable')
    data_type = models.CharField(max_length=20, blank=True)
    applied_logic = models.ForeignKey('corecode.ControlLogic', on_delete=models.CASCADE, related_name='agriseed_applications')
    args = models.JSONField(default=list, blank=True, help_text="함수 인자값을 순서대로 저장 (리스트)")
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name.name if self.name else 'Unnamed'} using {self.applied_logic.name if self.applied_logic else 'N/A'}"


class CalcGroup(models.Model):
    """
    계산 그룹 모델 (프로젝트 버전 의존성 제거됨)
    """
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"CalcGroup ({self.name})"

class CalcVariable(models.Model):
    group = models.ForeignKey(CalcGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='agriseed_calc_variables_in_group') # related_name 변경
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='agriseed_as_calc_variable') # related_name 변경
    data_type = models.CharField(max_length=20, blank=True)
    args = models.JSONField(default=list, blank=True, help_text="함수 인자값을 순서대로 저장 (리스트)")
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name}"


class ControlValue(models.Model):
    control_user = models.ForeignKey('corecode.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='agriseed_control_values', verbose_name="제어 사용자")
    status = models.CharField(max_length=30, verbose_name="명령상태")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="업데이트 일시")
    command_name = models.CharField(max_length=100, verbose_name="명령이름")
    target = models.CharField(max_length=100, verbose_name="타겟")
    data_type = models.CharField(max_length=30, verbose_name="데이터타입")
    value = models.JSONField(verbose_name="명령값")
    control_at = models.DateTimeField(null=True, blank=True, verbose_name="제어 일시")
    env_data = models.JSONField(null=True, blank=True, verbose_name="제어환경데이터")
    response = models.JSONField(null=True, blank=True, verbose_name="명령 Response")

    def __str__(self):
        return f"{self.command_name}({self.target}) by {self.control_user}" if self.control_user else f"{self.command_name}({self.target})"

class ControlValueHistory(models.Model):
    control_value = models.ForeignKey(ControlValue, on_delete=models.CASCADE, null=True, blank=True, related_name='histories', verbose_name="제어값")
    status = models.CharField(max_length=30, verbose_name="명령상태")
    command_name = models.CharField(max_length=100, verbose_name="명령이름")
    target = models.CharField(max_length=100, verbose_name="타겟")
    data_type = models.CharField(max_length=30, verbose_name="데이터타입")
    value = models.JSONField(verbose_name="명령값")
    control_at = models.DateTimeField(null=True, blank=True, verbose_name="제어 일시")
    env_data = models.JSONField(null=True, blank=True, verbose_name="제어환경데이터")
    response = models.JSONField(null=True, blank=True, verbose_name="명령 Response")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")

    def __str__(self):
        return f"{self.command_name}({self.target}) - {self.status}"

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
    start_address = models.FloatField(default=0, help_text="메모리 그룹의 시작 주소")
    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Group {self.name}({self.size_byte})"

@receiver(post_save, sender=MemoryGroup)
def _create_or_sync_device_instance_for_memory_group(sender, instance, created, **kwargs):
    """MemoryGroup 생성 또는 수정 시 agriseed.DeviceInstance 동기화.

    동작:
      - 생성(created=True): 기존과 동일하게 DeviceInstance가 없으면 하나 생성.
      - 수정(created=False): 해당 MemoryGroup을 참조하는 모든 DeviceInstance에 대해 device/adapter/name 필드를 MemoryGroup의 값으로 복사하여 동기화.
        만약 수정 시 연결된 DeviceInstance가 하나도 없으면 자동으로 하나 생성합니다.
    """
    try:
        DeviceInstance = apps.get_model('agriseed', 'DeviceInstance')
        if DeviceInstance is None:
            return
        # 생성 시: 없으면 새 DeviceInstance 생성
        if created:
            if DeviceInstance.objects.filter(memory_groups=instance).exists():
                return
            name = instance.name or (getattr(instance, 'Device').name if getattr(instance, 'Device', None) else None)
            # create without setting memory_groups via kwarg (FK assignment works)
            di = DeviceInstance.objects.create(
                device=getattr(instance, 'Device', None),
                adapter=getattr(instance, 'Adapter', None),
                memory_groups=instance,
                name=name,
                status='idle',
                is_active=True
            )
            return

        # 수정 시: 존재하는 DeviceInstance들에 대해 필드 복사
        qs = DeviceInstance.objects.filter(memory_groups=instance)
        # 연결된 DeviceInstance가 없으면 자동 생성
        if not qs.exists():
            try:
                name = instance.name or (getattr(instance, 'Device').name if getattr(instance, 'Device', None) else None)
                DeviceInstance.objects.create(
                    device=getattr(instance, 'Device', None),
                    adapter=getattr(instance, 'Adapter', None),
                    memory_groups=instance,
                    name=name,
                    status='idle',
                    is_active=True
                )
                # refresh qs after creation
                qs = DeviceInstance.objects.filter(memory_groups=instance)
            except Exception:
                qs = DeviceInstance.objects.filter(memory_groups=instance)

        for di in qs:
            changed = False
            try:
                if di.device != getattr(instance, 'Device', None):
                    di.device = getattr(instance, 'Device', None)
                    changed = True
            except Exception:
                pass
            try:
                if di.adapter != getattr(instance, 'Adapter', None):
                    di.adapter = getattr(instance, 'Adapter', None)
                    changed = True
            except Exception:
                pass
            try:
                target_name = instance.name or (getattr(instance, 'Device').name if getattr(instance, 'Device', None) else None)
                if di.name != target_name:
                    di.name = target_name
                    changed = True
            except Exception:
                pass
            if changed:
                try:
                    di.save()
                except Exception:
                    pass
    except Exception:
        # 안전하게 무시
        pass

@receiver(post_delete, sender=MemoryGroup)
def _unlink_device_instances_on_memorygroup_delete(sender, instance, **kwargs):
    """MemoryGroup 삭제 시 해당 DeviceInstance들의 memory_groups FK를 null로 설정합니다."""
    try:
        DeviceInstance = apps.get_model('agriseed', 'DeviceInstance')
        if DeviceInstance is None:
            return
        qs = DeviceInstance.objects.filter(memory_groups=instance)
        for di in qs:
            try:
                di.memory_groups = None
                di.save()
            except Exception:
                pass
    except Exception:
        pass

class Variable(models.Model):
    """
    메모리 그룹(MemoryGroup)에 속한 개별 변수 정보를 관리하는 모델
    """
    group = models.ForeignKey(MemoryGroup, on_delete=models.CASCADE, related_name='variables') # 기존 유지
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='lsissocket_physical_variables')
    device = models.CharField(max_length=2)
    address = models.FloatField(default=0)
    # 그룹의 start_address를 사용해 주소를 해석할지 여부
    use_group_base_address = models.BooleanField(default=False, help_text='이 변수의 주소가 그룹의 start_address 기준인지 여부')
    data_type = models.CharField(max_length=10, choices=[
        ('bool', 'bool'), ('sint', 'sint'), ('usint', 'usint'), ('int', 'int'),
        ('uint', 'uint'), ('dint', 'dint'), ('udint', 'udint'), ('float', 'float'),
    ])
    unit = models.CharField(max_length=10, choices=[
        ('bit', 'bit'), ('byte', 'byte'), ('word', 'word'), ('dword', 'dword'),
    ])
    scale = models.FloatField(default=1)
    offset = models.CharField(default='0', max_length=20, help_text="오프셋 값 (정수 또는 소수점 형태의 문자열)")
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")
    def __str__(self):
        return f"{self.name} ({self.device}{self.address})"


class SocketClientConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    host = models.CharField(max_length=100, help_text="클라이언트 IP", null=True, blank=True)
    port = models.IntegerField(help_text="클라이언트 포트", null=True, blank=True)
    blocks = models.JSONField(help_text='[{"address":"0","id":1,"count":700,"func_name":"continuous_read_bytes","memory":"%MB"},{"address":"700","id":2,"count":700,"func_name":"continuous_read_bytes","memory":"%MB"}]', null=True, blank=True)
    cron = models.JSONField(help_text="cron 설정값", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_used = models.BooleanField(default=True, help_text="사용 여부")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    zone_style = models.JSONField(null=True, blank=True, help_text="존 스타일 정보")
    control_groups = models.ManyToManyField(ControlGroup, blank=True, related_name='lsissocket_control_groups', help_text='연결된 제어 그룹')
    calc_groups = models.ManyToManyField(CalcGroup, blank=True, related_name='lsissocket_calc_groups', help_text='연결된 계산 그룹')
    memory_groups = models.ManyToManyField(MemoryGroup, blank=True, related_name='lsissocket_memory_groups', help_text='연결된 메모리 그룹')
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
        

class SocketClientStatus(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='status_logs')
    updated_at = models.DateTimeField(auto_now=True)
    detailedStatus = models.JSONField(null=True, blank=True)
    error_code = models.IntegerField(default=0)
    message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.system_status} (code: {self.error_code}) @ {self.updated_at}"

    def save(self, *args, **kwargs):
        """저장하기 전에 이전 상태를 조회하여 error_code 또는 detailedStatus가 변경되었는지 확인.

        변경되었으면 저장 완료 후 SocketClientLog 레코드를 생성한다.
        """
        try:
            old = None
            if self.pk:
                try:
                    old = SocketClientStatus.objects.get(pk=self.pk)
                except SocketClientStatus.DoesNotExist:
                    old = None
            changed = False
            # 신규 생성인 경우나 이전과 값이 다른 경우 변경으로 판단
            if old is None:
                changed = True
            else:
                if old.error_code != self.error_code:
                    changed = True
                else:
                    # detailedStatus는 JSONField이므로 정규화된 JSON 문자열로 비교하여 키 순서 등 형식 차이에 따른 불필요한 변경 탐지를 방지
                    try:
                        old_json = json.dumps(old.detailedStatus or {}, sort_keys=True, ensure_ascii=False, default=str)
                        new_json = json.dumps(self.detailedStatus or {}, sort_keys=True, ensure_ascii=False, default=str)
                        if old_json != new_json:
                            changed = True
                    except Exception:
                        # 직렬화 실패 시 폴더값 직접 비교
                        if old.detailedStatus != self.detailedStatus:
                            changed = True
        except Exception:
            # 안전하게 넘어감
            changed = True

        super().save(*args, **kwargs)

        if changed:
            try:
                # 트랜잭션이 커밋된 이후에 로그를 생성하도록 보장
                def _create_log():
                    try:
                        SocketClientLog.objects.create(
                            config=self.config,
                            detailedStatus=self.detailedStatus or {},
                            error_code=self.error_code,
                            message=f"{old.detailedStatus.get('SYSTEM STATUS', '')} -> {self.detailedStatus.get('SYSTEM STATUS', '')}"
                        )
                    except Exception:
                        pass

                transaction.on_commit(_create_log)
            except Exception:
                # 로깅 실패는 무시
                pass

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
