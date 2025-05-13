from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='corecode_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='corecode_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
    preferences = models.JSONField(default=dict, blank=True, help_text="개인화 설정(예: 테마, 알림 등)")

    def __str__(self):
        return f"{self.user.username}의 환경설정"

class Project(models.Model):
    """
    프로젝트의 메타 정보(이름, 설명 등)를 관리하는 모델
    여러 개의 ProjectVersion(버전)과 1:N 관계
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    device = models.ForeignKey('Device', on_delete=models.CASCADE, null=True, blank=True, related_name='projects')
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # 프로젝트 생성 시 version=0.0인 ProjectVersion 자동 생성
            if not self.versions.filter(version='0.0').exists():
                ProjectVersion.objects.create(project=self, version='0.0', note='프로젝트 최초 생성')

    def __str__(self):
        return self.name

class ProjectVersion(models.Model):
    """
    프로젝트의 특정 시점(스냅샷, 버전)을 관리하는 모델
    각 버전은 여러 MemoryGroup(메모리 그룹)과 1:N 관계
    복구(restore_version) 메서드로 해당 버전의 상태로 프로젝트를 복원할 수 있음
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'version')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.project.name} - v{self.version}"

    def restore_version(self):
        self.save()  # 이 줄이 있으면 updated_at이 현재 시각으로 갱신됨

class MemoryGroup(models.Model):
    """
    프로젝트 버전(ProjectVersion)에 속한 메모리 그룹을 관리하는 모델
    각 그룹은 여러 Variable(변수)과 1:N 관계
    """
    project_version = models.ForeignKey(ProjectVersion, on_delete=models.CASCADE, related_name='groups')
    group_id = models.PositiveIntegerField()
    name = models.CharField(max_length=50, null=True, blank=True)
    start_device = models.CharField(max_length=2, choices=[('D', 'D'), ('M', 'M'), ('R', 'R')])
    start_address = models.PositiveIntegerField()
    size_byte = models.PositiveIntegerField()

    class Meta:
        unique_together = ('project_version', 'group_id')
        ordering = ['group_id']

    def __str__(self):
        return f"Group {self.group_id} ({self.start_device}{self.start_address})"


class UserManual(models.Model):
    """
    사용자 취급 메뉴얼 정보를 관리하는 모델
    """
    title = models.CharField(max_length=200, help_text="메뉴얼 제목")
    file = models.FileField(upload_to='user_manuals/', help_text="사용자 취급 메뉴얼 파일")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

#데이터 명칭, 단위
class DataName(models.Model):
    name = models.CharField(max_length=100, unique=True)
    dtype = models.CharField(max_length=10, blank=True)
    unit = models.CharField(max_length=10, blank=True)
    DATA_TYPE_CHOICES = [
        ('status', 'Status'),
        ('upper', 'Upper'),
        ('lower', 'Lower'),
        ('reference', 'Reference'),
        ('difference', 'Difference'),
    ]
    attributes = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, null=True, blank=True)
    def __str__(self):
        return self.name


class Variable(models.Model):
    """
    메모리 그룹(MemoryGroup)에 속한 개별 변수 정보를 관리하는 모델
    """
    group = models.ForeignKey(MemoryGroup, on_delete=models.CASCADE, related_name='variables')
    name = models.ForeignKey(DataName, on_delete=models.CASCADE, related_name='data_names')
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
    offset = models.PositiveIntegerField(default=0)
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name} ({self.device}{self.address})"

class DeviceCompany(models.Model):
    """
    장비 제조사 정보를 관리하는 모델
    """
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.name
    
class Device(models.Model):
    name = models.CharField(max_length=100, unique=True)
    DEVICE_TYPE_CHOICES = [
        ('sensor', 'Sensor'),
        ('actuator', 'Actuator'),
        ('controller', 'Controller'),
        ('other', 'Other'),
    ]
    device_code = models.CharField(max_length=20, null=True, blank=True)
    device_name_korean = models.CharField(max_length=200, null=True, blank=True, help_text="단체표준 장비명(국문)")
    device_name_english = models.CharField(max_length=200, null=True, blank=True, help_text="Standardized device name (English)")
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPE_CHOICES)
    icon = models.ImageField(upload_to='device_icons/', null=True, blank=True)
    alert_icon = models.ImageField(upload_to='device_icons/alert/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    manufacturer = models.ForeignKey('DeviceCompany', on_delete=models.CASCADE, null=True, blank=True, related_name='devices')
    
    CONNECTOR_TYPE_CHOICES = [
        ('LSIS-socket', 'LSIS-socket'),
    ]
    connector = models.CharField(max_length=50, null=True, blank=True, choices=CONNECTOR_TYPE_CHOICES)
    catalog = models.FileField(upload_to='device_catalogs/', null=True, blank=True, help_text="장비 카탈로그 파일")
    user_manuals = models.ManyToManyField('UserManual', null=True, blank=True, related_name='devices', help_text="사용자 취급 메뉴얼 파일들")

    def __str__(self):
        return self.name

