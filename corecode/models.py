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
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'version')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} - v{self.version}"

    def restore_version(self):
        """
        현재 프로젝트의 MemoryGroup/Variable을 모두 삭제하고,
        이 버전(ProjectVersion)의 MemoryGroup/Variable을 복제하여 현재로 복원합니다.
        (실제 서비스 상황에 맞게 트랜잭션 처리, 예외 처리 등 보완 필요)
        """
        from django.db import transaction
        with transaction.atomic():
            project = self.project
            # 1. 기존 모든 버전의 MemoryGroup/Variable 삭제
            for v in project.versions.all():
                v.groups.all().delete()
            # 2. 이 버전(self)의 MemoryGroup/Variable을 복제
            for group in self.groups.all():
                new_group = MemoryGroup.objects.create(
                    project_version=self,
                    group_id=group.group_id,
                    start_device=group.start_device,
                    start_address=group.start_address,
                    size_byte=group.size_byte,
                )
                for var in group.variable_set.all():
                    Variable.objects.create(
                        group=new_group,
                        name=var.name,
                        device=var.device,
                        address=var.address,
                        data_type=var.data_type,
                        unit=var.unit,
                        scale=var.scale,
                        offset=var.offset,
                    )

class MemoryGroup(models.Model):
    """
    프로젝트 버전(ProjectVersion)에 속한 메모리 그룹을 관리하는 모델
    각 그룹은 여러 Variable(변수)과 1:N 관계
    """
    project_version = models.ForeignKey(ProjectVersion, on_delete=models.CASCADE, related_name='groups')
    group_id = models.PositiveIntegerField()
    vergroup_name = models.CharField(max_length=50, null=True, blank=True)
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

    def __str__(self):
        return f"{self.name} ({self.device}{self.address})"
