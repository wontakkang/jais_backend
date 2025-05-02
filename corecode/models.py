from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ProjectVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'version')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} - v{self.version}"

class MemoryGroup(models.Model):
    project_version = models.ForeignKey(ProjectVersion, on_delete=models.CASCADE, related_name='groups')
    group_id = models.PositiveIntegerField()
    start_device = models.CharField(max_length=2, choices=[('D', 'D'), ('M', 'M'), ('R', 'R')])
    start_address = models.PositiveIntegerField()
    size_byte = models.PositiveIntegerField()

    class Meta:
        unique_together = ('project_version', 'group_id')
        ordering = ['group_id']

    def __str__(self):
        return f"Group {self.group_id} ({self.start_device}{self.start_address})"

class Variable(models.Model):
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
