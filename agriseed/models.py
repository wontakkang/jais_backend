from django.db import models

class Device(models.Model):
    name = models.CharField(max_length=100)
    device_id = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=100)
    battery = models.IntegerField()
    firmware = models.CharField(max_length=50)
    last_data = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    installed_at = models.DateField()
    status = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    info_link = models.URLField()
    is_deleted = models.BooleanField(default=False)

class Activity(models.Model):
    time = models.DateTimeField()
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='activities')
    event = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    icon = models.CharField(max_length=100)
    icon_class = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)

class ControlHistory(models.Model):
    time = models.DateTimeField()
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='control_histories')
    action = models.CharField(max_length=200)
    trigger = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    is_deleted = models.BooleanField(default=False)

class ControlRole(models.Model):
    title = models.CharField(max_length=200)
    icon = models.CharField(max_length=100)
    icon_bg = models.CharField(max_length=100)
    conditions = models.JSONField()
    actions = models.JSONField()
    last_executed = models.DateTimeField()
    active = models.BooleanField()
    is_deleted = models.BooleanField(default=False)

class Issue(models.Model):
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    time = models.DateTimeField()
    details = models.JSONField()
    button_label = models.CharField(max_length=100)
    icon = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)

class ResolvedIssue(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=200)
    action = models.CharField(max_length=200)
    is_deleted = models.BooleanField(default=False)

class Schedule(models.Model):
    icon = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    schedule = models.CharField(max_length=200)
    description = models.TextField()
    enabled = models.BooleanField()
    is_deleted = models.BooleanField(default=False)

class Facility(models.Model):
    name = models.CharField(max_length=100, default="Unknown Facility", help_text="시설 이름")
    type = models.CharField(max_length=50, default="vinyl", help_text="시설 유형 (예: vinyl, glass 등)")
    location = models.CharField(max_length=200, default="Unknown Location", help_text="시설 위치")
    area = models.FloatField(default=100.0, help_text="시설 면적 (기본값: 100 제곱미터)")
    zone_count = models.IntegerField(default=1, help_text="구역 수 (기본값: 1)")
    manager = models.CharField(max_length=100, default="Unknown Manager", help_text="시설 관리자")
    is_deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_zone_count = None
        if not is_new:
            old = Facility.objects.get(pk=self.pk)
            old_zone_count = old.zone_count
        super().save(*args, **kwargs)
        # Zone 자동 동기화
        if is_new:
            for i in range(1, self.zone_count + 1):
                Zone.objects.create(facility=self, name=f"구역 {i}")
        else:
            zones = list(self.zones.order_by('id'))
            diff = self.zone_count - len(zones)
            if diff > 0:
                # Zone 추가
                for i in range(len(zones) + 1, self.zone_count + 1):
                    Zone.objects.create(facility=self, name=f"구역 {i}")
            elif diff < 0:
                # Zone 삭제 (마지막부터)
                for z in zones[diff:]:
                    z.delete()

class Zone(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='zones', help_text="소속된 시설")
    name = models.CharField(max_length=100, default="Default Zone", help_text="구역 이름")
    type = models.CharField(max_length=50, default="온실", help_text="구역 유형 (예: 온실, 저장고 등)")
    area = models.FloatField(default=50.0, help_text="구역 면적 (기본값: 50 제곱미터)")
    is_deleted = models.BooleanField(default=False)

class SensorData(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='sensor_data', help_text="소속된 구역")
    temperature = models.FloatField(default=24.5, help_text="온도 (기본값: 24.5°C)")
    humidity = models.FloatField(default=65.0, help_text="습도 (기본값: 65%)")
    light = models.FloatField(default=350.0, help_text="조도 (기본값: 350 lux)")
    soil_moisture = models.FloatField(default=42.0, help_text="토양 수분 (기본값: 42%)")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="데이터 생성 시간")
    is_deleted = models.BooleanField(default=False)

class ControlSettings(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='control_settings', help_text="소속된 시설", default="0", null=True, blank=True)
    fan_is_on = models.BooleanField(default=False, help_text="팬 작동 여부 (기본값: 꺼짐)")
    fan_speed = models.IntegerField(default=50, help_text="팬 속도 (기본값: 50%)")
    water_is_on = models.BooleanField(default=False, help_text="물 공급 여부 (기본값: 꺼짐)")
    water_flow = models.FloatField(default=2.5, help_text="물 흐름 속도 (기본값: 2.5 L/min)")
    vent_open = models.IntegerField(default=50, help_text="환기구 개방 정도 (기본값: 50%)")
    light_is_on = models.BooleanField(default=False, help_text="조명 작동 여부 (기본값: 꺼짐)")
    light_intensity = models.IntegerField(default=50, help_text="조명 강도 (기본값: 50%)")
    auto_mode = models.BooleanField(default=True, help_text="자동 모드 여부 (기본값: 켜짐)")
    schedule_start = models.TimeField(default="06:00", help_text="스케줄 시작 시간 (기본값: 06:00)")
    schedule_end = models.TimeField(default="18:00", help_text="스케줄 종료 시간 (기본값: 18:00)")
    abnormal_temp_alert = models.BooleanField(default=True, help_text="이상온도 알림 (기본값: 켜짐)")
    abnormal_humidity_alert = models.BooleanField(default=True, help_text="이상습도 알림 (기본값: 켜짐)")
    water_alert = models.BooleanField(default=True, help_text="급수알림 (기본값: 켜짐)")
    fault_alert = models.BooleanField(default=True, help_text="고장알림 (기본값: 켜짐)")
    is_deleted = models.BooleanField(default=False)

class FacilityHistory(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='history', help_text="소속된 구역")
    temperature = models.JSONField(default=list, help_text="온도 기록")
    humidity = models.JSONField(default=list, help_text="습도 기록")
    light = models.JSONField(default=list, help_text="조도 기록")
    soil_moisture = models.JSONField(default=list, help_text="토양 수분 기록")
    is_deleted = models.BooleanField(default=False)