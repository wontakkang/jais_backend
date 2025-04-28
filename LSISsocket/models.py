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

class SocketClientLog(models.Model):
    config = models.ForeignKey(SocketClientConfig, on_delete=models.CASCADE, related_name='logs')
    detailedStatus = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True, blank=True)
    error_code = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.config.name} - {self.created_at}"
