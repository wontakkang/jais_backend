from django.db import models, transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
import json

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class ControlGroup(models.Model):
    """
    제어 그룹 모델
    """
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"ControlGroup ({self.name})"


class AlartGroup(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"AlartGroup ({self.name})"


class ControlValue(models.Model):
    control_user = models.ForeignKey('corecode.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='lsissocket_control_values', verbose_name="제어 사용자")
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
    Adapter = models.ForeignKey('corecode.Adapter', on_delete=models.SET_NULL, null=True, blank=True, related_name='lsissocket_memory_groups', help_text="이 그룹이 속한 어댑터")
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
    try:
        DeviceInstance = apps.get_model('agriseed', 'DeviceInstance')
        if DeviceInstance is None:
            return
        if created:
            if DeviceInstance.objects.filter(memory_groups=instance).exists():
                return
            name = instance.name or (getattr(instance, 'Device').name if getattr(instance, 'Device', None) else None)
            di = DeviceInstance.objects.create(
                device=getattr(instance, 'Device', None),
                adapter=getattr(instance, 'Adapter', None),
                memory_groups=instance,
                name=name,
                status='idle',
                is_active=True
            )
            return

        qs = DeviceInstance.objects.filter(memory_groups=instance)
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
        pass

@receiver(post_delete, sender=MemoryGroup)
def _unlink_device_instances_on_memorygroup_delete(sender, instance, **kwargs):
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
    group = models.ForeignKey(MemoryGroup, on_delete=models.CASCADE, related_name='variables')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='lsissocket_physical_variables')
    device = models.CharField(max_length=2)
    address = models.FloatField(default=0)
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
    remark = models.TextField(null=True, blank=True, help_text='비고')
    def __str__(self):
        return f"{self.name} ({self.device}{self.address})"


class CalcGroup(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"CalcGroup ({self.name})"

class ControlVariable(models.Model):
    group = models.ForeignKey(ControlGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='lsissocket_control_variables_in_group')
    applied_logic = models.ForeignKey('corecode.ControlLogic', on_delete=models.CASCADE, related_name='lsissocket_applications')
    data_type = models.CharField(max_length=20, blank=True)
    args = models.JSONField(default=list, blank=True, help_text="함수 인자값을 순서대로 저장 (리스트)")
    result = models.ForeignKey(Variable, null=True, blank=True, on_delete=models.CASCADE, related_name='lsissocket_as_control_result')

    def __str__(self):
        return f" using {self.applied_logic.name if self.applied_logic else 'N/A'}"


class AlartVariable(models.Model):
    group = models.ForeignKey(AlartGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='lsissocket_alart_variables_in_group')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='lsissocket_as_alart_variable')
    data_type = models.CharField(max_length=20, blank=True)
    args = models.JSONField(default=list, null=True, blank=True, help_text="알림 변수 인자값을 순서대로 저장 (리스트)")
    result = models.ForeignKey(Variable, null=True, blank=True, on_delete=models.CASCADE, related_name='lsissocket_as_alart_result')

    def __str__(self):
        return f"AlartVar:{self.name} (group={self.group.name if self.group else 'None'})"

class CalcVariable(models.Model):
    group = models.ForeignKey(CalcGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='lsissocket_calc_variables_in_group')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='lsissocket_as_calc_variable')
    data_type = models.CharField(max_length=20, blank=True)
    args = models.JSONField(default=list, null=True, blank=True, help_text="연산 변수 인자값을 순서대로 저장 (리스트)")
    result = models.ForeignKey(Variable, null=True, blank=True, on_delete=models.CASCADE, related_name='lsissocket_as_calc_result')
    def __str__(self):
        return f"{self.name}"
    
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
        try:
            old = None
            if self.pk:
                try:
                    old = SocketClientStatus.objects.get(pk=self.pk)
                except SocketClientStatus.DoesNotExist:
                    old = None
            changed = False
            if old is None:
                changed = True
            else:
                if old.error_code != self.error_code:
                    changed = True
                else:
                    try:
                        old_json = json.dumps(old.detailedStatus or {}, sort_keys=True, ensure_ascii=False, default=str)
                        new_json = json.dumps(self.detailedStatus or {}, sort_keys=True, ensure_ascii=False, default=str)
                        if old_json != new_json:
                            changed = True
                    except Exception:
                        if old.detailedStatus != self.detailedStatus:
                            changed = True
        except Exception:
            changed = True

        super().save(*args, **kwargs)

        if changed:
            try:
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
                pass

class SocketClientLog(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='logs')
    detailedStatus = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True, blank=True)
    error_code = models.IntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    objects = ActiveManager()  # 삭제되지 않은 것만 조회

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

    objects = ActiveManager()  # 삭제되지 않은 것만 조회

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

    def __str__(self):
        return f"{self.config.name} - {self.command} - {self.control_time}"
