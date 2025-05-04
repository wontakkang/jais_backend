from django.db import models

class Project(models.Model):
    """
    프로젝트의 메타 정보(이름, 설명 등)를 관리하는 모델
    여러 개의 ProjectVersion(버전)과 1:N 관계
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

class Variable(models.Model):
    """
    메모리 그룹(MemoryGroup)에 속한 개별 변수 정보를 관리하는 모델
    """
    group = models.ForeignKey(MemoryGroup, on_delete=models.CASCADE, related_name='variables')
    name = models.CharField(max_length=100)
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
