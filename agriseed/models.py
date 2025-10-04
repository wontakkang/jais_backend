from django.db import models
from django.contrib.postgres.fields import RangeField
from django.db.models import JSONField
from django.conf import settings
import random
from django.utils import timezone
from corecode.models import LocationGroup as CoreLocationGroup  # use corecode LocationGroup

# backward compatibility alias (other modules may import agriseed.models.LocationGroup)
LocationGroup = CoreLocationGroup

class Facility(models.Model):
    name = models.CharField(max_length=100, default="Unknown Facility", help_text="시설 이름")
    type = models.CharField(max_length=50, default="vinyl", help_text="시설 유형 (예: vinyl, glass 등)")
    location = models.CharField(max_length=200, default="Unknown Location", help_text="시설 위치")
    area = models.FloatField(default=100.0, help_text="시설 면적 (기본값: 100 제곱미터)")
    zone_count = models.IntegerField(default=1, help_text="구역 수 (기본값: 1)")
    manager = models.CharField(max_length=100, default="Unknown Manager", help_text="시설 관리자")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    module = models.ManyToManyField('Module', blank=True, related_name='facilities', help_text="연결된 모듈")

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


    def __str__(self):
        try:
            return f"{self.name}"
        except Exception:
            return self.name
                      
class Device(models.Model):
    name = models.CharField(max_length=100)
    device_id = models.CharField(max_length=20, unique=True)
    icon = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    installed_at = models.DateField()
    status = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    info_link = models.URLField()
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class Activity(models.Model):
    time = models.DateTimeField()
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.CASCADE, related_name='activities')
    event = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    icon = models.CharField(max_length=100)
    icon_class = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class ControlHistory(models.Model):
    time = models.DateTimeField()
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.CASCADE, related_name='control_histories')
    action = models.CharField(max_length=200)
    trigger = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class ControlRole(models.Model):
    title = models.CharField(max_length=200)
    icon = models.CharField(max_length=100)
    icon_bg = models.CharField(max_length=100)
    conditions = models.JSONField()
    actions = models.JSONField()
    last_executed = models.DateTimeField()
    active = models.BooleanField()
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class Issue(models.Model):
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    time = models.DateTimeField()
    details = models.JSONField()
    button_label = models.CharField(max_length=100)
    icon = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class ResolvedIssue(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=200)
    action = models.CharField(max_length=200)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

# 캘린더형 일정(Event) 및 할일(Todo) 모델 추가
class CalendarEvent(models.Model):
    """캘린더형 이벤트 모델
    - start/end: 일정 시작/종료
    - all_day: 종일 여부
    - recurrence: 간단한 반복 규칙(JSON)
    - reminders: 알림 목록(분 단위 오프셋 리스트)
    """
    # Facility가 파일 아래쪽에 정의되므로 문자열 참조로 forward-reference 처리
    facility = models.ForeignKey('Facility', on_delete=models.CASCADE, null=True, blank=True, related_name='calendar_events', help_text="소속 시설")
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_events', help_text="관련 구역")
    title = models.CharField(max_length=200)
    description = models.TextField()
    start = models.DateTimeField(help_text="시작 시간")
    end = models.DateTimeField(help_text="종료 시간", null=True, blank=True)
    all_day = models.BooleanField(default=False)
    recurrence = models.JSONField(null=True, blank=True, help_text='예: {"freq":"DAILY","interval":1}')
    reminders = models.JSONField(null=True, blank=True, help_text='예: [60, 10]  # 시작 60분 전, 10분 전')
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='events_attending')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_calendar_events')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    class Meta:
        ordering = ['-start']

    def __str__(self):
        try:
            return f"{self.title} ({self.start:%Y-%m-%d %H:%M})"
        except Exception:
            return self.title


class TodoItem(models.Model):
    """할일/작업(Task) 모델
    - zone: 특정 구역에 연결 가능
    - assigned_to: 담당자
    - priority: 1=high,2=normal,3=low
    - reminders: 알림(분 단위 오프셋) 또는 기타 정보
    """
    # Facility가 파일 아래쪽에 정의되므로 문자열 참조로 forward-reference 처리
    facility = models.ForeignKey('Facility', on_delete=models.CASCADE, null=True, blank=True, related_name='todo_items', help_text="소속 시설")
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True, blank=True, related_name='todo_items', help_text="관련 구역")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='todos_created')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='todos_assigned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=2, help_text='1=high,2=normal,3=low')
    status = models.CharField(max_length=50, default='open')
    reminders = models.JSONField(null=True, blank=True, help_text='예: [1440, 60] # 하루 전, 1시간 전')
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    class Meta:
        ordering = ['completed', '-priority', 'due_date']

    def mark_complete(self, by_user=None):
        """작업을 완료 처리하고 완료자/완료시간을 기록합니다."""
        self.completed = True
        self.completed_at = timezone.now()
        if by_user and not self.assigned_to:
            # 선택적으로 완료자가 할당되지 않았으면 할당
            try:
                self.assigned_to = by_user
            except Exception:
                pass
        self.status = 'completed'
        self.save()

    def __str__(self):
        return f"{self.title} ({'완료' if self.completed else '진행중'})"


class Crop(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="작물 종류명")
    def __str__(self):
        return self.name

class Variety(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='varieties', help_text="작물 종류")
    name = models.CharField(max_length=100, help_text="품종명")
    category = models.CharField(max_length=100, null=True, blank=True, help_text="작물 분류 (예: 과채류)")
    origin = models.CharField(max_length=100, null=True, blank=True, help_text="원산지")
    registered_at = models.DateField(null=True, blank=True, help_text="등록일")
    seed_amount = models.CharField(max_length=50, null=True, blank=True, help_text="씨앗 보유량")
    difficulty = models.CharField(max_length=50, null=True, blank=True, help_text="재배 난이도")
    temperature = JSONField(null=True, blank=True, help_text="적정 온도 범위")
    humidity = JSONField(null=True, blank=True, help_text="적정 습도 범위")
    sunlight = JSONField(null=True, blank=True, help_text="일조량 범위")
    soil = JSONField(null=True, blank=True, help_text="토양 조건")
    sowing_period = models.CharField(max_length=100, null=True, blank=True, help_text="파종기 범위")
    harvest_period = models.CharField(max_length=100, null=True, blank=True, help_text="수확기 범위")
    growth_duration = JSONField(null=True, blank=True, help_text="생육 기간 범위")
    expected_yield = JSONField(null=True, blank=True, help_text="예상 수확량 범위")
    fruit_size = JSONField(null=True, blank=True, help_text="과실 크기 범위")
    sugar_content = JSONField(null=True, blank=True, help_text="당도 범위")
    disease_resistance = models.CharField(max_length=100, null=True, blank=True, help_text="병해충 저항성")
    note = models.CharField(max_length=200, null=True, blank=True, help_text="특이사항")
    guide = models.TextField(null=True, blank=True, help_text="재배 가이드")
    def __str__(self):
        return f"{self.crop.name} - {self.name}"

class VarietyImage(models.Model):
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name='images', help_text="연결된 품종")
    image = models.ImageField(upload_to='variety_images/', help_text="품종 이미지")
    description = models.CharField(max_length=200, null=True, blank=True, help_text="이미지 설명")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="업로드 일시")

class VarietyGuide(models.Model):
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name='guides', help_text="연결된 품종")
    guide = models.TextField(help_text="재배 가이드")
    created_at = models.DateTimeField(auto_now_add=True, help_text="작성일시")
    updated_at = models.DateTimeField(auto_now=True, help_text="수정일시")
    author = models.CharField(max_length=100, null=True, blank=True, help_text="작성자")
    note = models.CharField(max_length=200, null=True, blank=True, help_text="비고/특이사항")
    stage_tips = models.JSONField(null=True, blank=True, help_text="재배 단계별 설정값 및 팁")
    def __str__(self):
        return f"{self.variety} - {self.created_at:%Y-%m-%d}" 

class RecipeProfile(models.Model):
    variety = models.ForeignKey(
        Variety, null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='recipe_profiles',
        help_text="레시피 대상 품종"
    )
    recipe_name = models.CharField(max_length=200, help_text="레시피 이름")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_recipe_profiles',
        help_text="생성자"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_recipe_profiles',
        help_text="수정자"
    )
    is_active = models.BooleanField(default=True, null=True, blank=True, help_text="레시피 활성화 여부")
    is_deleted = models.BooleanField(default=False, null=True, blank=True, help_text="삭제 여부")
    duration_days = models.IntegerField(null=True, blank=True, help_text="기간 (일)")
    description = models.TextField(blank=True, help_text="설명")
    order = models.IntegerField(default=0, help_text="레시피 순서 (우선순위)")
    bookmark = models.BooleanField(default=False, help_text="북마크 여부")

    def __str__(self):
        creator = self.created_by.username if self.created_by else "Unknown Creator"
        return f"{creator} - {self.variety} - {self.recipe_name}"

    @property
    def average_rating(self):
        from django.db.models import Avg
        return self.ratings.aggregate(Avg('rating'))['rating__avg'] or 0

    @property
    def rating_count(self):
        return self.ratings.count()

    @property
    def average_yield(self):
        from django.db.models import Avg
        return self.performances.aggregate(Avg('yield_amount'))['yield_amount__avg'] or 0

    @property
    def success_rate(self):
        total = self.performances.count()
        if total:
            success_count = self.performances.filter(success=True).count()
            return (success_count / total) * 100
        return 0
    
class Zone(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='zones', help_text="소속된 시설")
    name = models.CharField(max_length=100, default="Default Zone", help_text="구역 이름")
    type = models.CharField(max_length=50, default="온실", help_text="구역 유형 (예: 온실, 저장고 등)")
    area = models.FloatField(default=50.0, help_text="구역 면적 (기본값: 50 제곱미터)")
    style = models.CharField(max_length=50, default="일반", null=True, blank=True, help_text="구역 스타일 (예: 일반, 특수 등)")
    health_status = models.CharField(max_length=50, default="양호", null=True, blank=True, help_text="건강 상태 (예: 양호, 주의, 위험 등)")
    environment_status = models.CharField(max_length=50, default="정상", null=True, blank=True, help_text="환경 상태 (예: 정상, 주의, 위험 등)")
    STATUS_CHOICES = [
        ("활성화", "활성화"),
        ("비활성화", "비활성화"),
        ("작업중", "작업중"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="활성화", null=True, blank=True, help_text="구역 상태 (활성화, 비활성화, 작업중)")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    # timestamps and editor
    created_at = models.DateTimeField(auto_now_add=True, help_text="생성 시각", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, help_text="수정 시각", null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_zones', help_text="최종 수정자")

class SensorData(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='sensor_data', help_text="소속된 구역")
    temperature = models.FloatField(default=24.5, help_text="온도 (기본값: 24.5°C)")
    humidity = models.FloatField(default=65.0, help_text="습도 (기본값: 65%)")
    light = models.FloatField(default=350.0, help_text="조도 (기본값: 350 lux)")
    soil_moisture = models.FloatField(default=42.0, help_text="토양 수분 (기본값: 42%)")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="데이터 생성 시간")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class ControlSettings(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='control_settings', help_text="소속된 시설", null=True, blank=True)
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
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class FacilityHistory(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='history', help_text="소속된 구역")
    temperature = models.JSONField(default=list, help_text="온도 기록")
    humidity = models.JSONField(default=list, help_text="습도 기록")
    light = models.JSONField(default=list, help_text="조도 기록")
    soil_moisture = models.JSONField(default=list, help_text="토양 수분 기록")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")


class RecipeStep(models.Model):
    recipe_profile = models.ForeignKey( RecipeProfile, on_delete=models.CASCADE, related_name='steps', help_text="레시피 프로필에 속한 단계")
    name = models.CharField(max_length=100, help_text="단계 이름 (예: 준비, 성장, 수확)")
    order = models.PositiveIntegerField(default=0, help_text="단계 순서 지정용 정수")
    duration_days = models.IntegerField(null=True, blank=True, help_text="이 단계의 기간 (일)")
    description = models.TextField(blank=True, help_text="단계 설명")
    label_icon = models.CharField(max_length=20, null=True, blank=True, help_text="단계 아이콘 (선택 사항)")
    active = models.BooleanField(default=True, help_text="단계 활성화 여부")
    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.recipe_profile.recipe_name} - {self.name}"

class ControlItem(models.Model):
    item_name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, null=True, blank=True, related_name='control_items', help_text="제어 항목명(DataName)")
    description = models.TextField(blank=True, help_text="설명")
    scada_tag_name = models.TextField(null=True, blank=True, help_text="XSCADA 태그 이름")
    order = models.PositiveIntegerField(default=0, help_text="단계 순서 지정용 정수")
    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.description}({self.item_name})-{self.scada_tag_name}"

class MeasurementItem(models.Model):
    item_name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, null=True, blank=True, related_name='measurement_items', help_text="측정 항목명(DataName)")
    description = models.TextField(blank=True, help_text="설명")

    def __str__(self):
        return f"{self.description}({self.item_name})"
    
class SensorItem(models.Model):
    item_name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, null=True, blank=True, related_name='sensor_items', help_text="센서 항목명(DataName)")
    description = models.TextField(blank=True, help_text="설명")

    def __str__(self):
        return f"{self.description}({self.item_name})"

class VarietyDataThreshold(models.Model):
    """특정 품종(variety) 및 데이터항목(data_name)에 대한 품질/임계값을 저장합니다.
    예: 온주밀감 당도 정상 범위(11.5~13.4), 경고 범위(10.0~11.4) 등

    구현 보완:
    - clean()에서 min<=max 보장, 쌍 누락 방지, 구간 겹침 방지(반-열린 구간 기준)
    - save()에서 full_clean() 호출로 저장 시 검증 수행
    - evaluate()는 반-열린 구간 [min, max) 표준을 따르며 matched_range 반환
    """
    LEVEL_LABELS = {
        'normal': ('정상', '우수'),
        'warning': ('주의', '양호'),
        'risk': ('위험', '불량'),
        'high_risk': ('고위험', '불량'),
        'critical': ('부적합', '불량'),
    }

    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name='data_thresholds')
    data_name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='variety_thresholds')

    # 정상(good) 범위
    min_good = models.FloatField(null=True, blank=True)
    max_good = models.FloatField(null=True, blank=True)

    # 경고(warning) 범위
    min_warn = models.FloatField(null=True, blank=True)
    max_warn = models.FloatField(null=True, blank=True)

    # 추가: 위험(risk) 및 고위험(high_risk) 범위
    min_risk = models.FloatField(null=True, blank=True)
    max_risk = models.FloatField(null=True, blank=True)

    min_high_risk = models.FloatField(null=True, blank=True)
    max_high_risk = models.FloatField(null=True, blank=True)

    # 우선순위
    priority = models.IntegerField(default=0)
    note = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # 라벨 필드
    level_label = models.CharField(max_length=50, null=True, blank=True,
                                   help_text="레벨 라벨 (예: normal=정상, warning=주의, critical=부적합)")
    quality_label = models.CharField(max_length=50, null=True, blank=True,
                                     help_text="품질 라벨 (예: good=우수, fair=양호, poor=불량)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('variety', 'data_name', 'priority')
        ordering = ['-priority', 'variety', 'data_name']

    def __str__(self):
        return f"{self.variety} - {self.data_name} (pri={self.priority})"

    def clean(self):
        """모델 레벨 검증
        - 각 (min, max)는 함께 있거나 함께 비워야 함
        - min <= max
        - 서로 다른 구간 간 겹침 금지 (반-열린 구간 기준: [min, max) )
        """
        from django.core.exceptions import ValidationError

        pairs = [
            ('min_good', 'max_good', 'good'),
            ('min_warn', 'max_warn', 'warn'),
            ('min_risk', 'max_risk', 'risk'),
            ('min_high_risk', 'max_high_risk', 'high_risk'),
        ]

        intervals = {}
        for lo_key, hi_key, name in pairs:
            lo = getattr(self, lo_key)
            hi = getattr(self, hi_key)
            if (lo is None) ^ (hi is None):
                raise ValidationError({lo_key: f"{lo_key}/{hi_key}는 함께 설정하거나 함께 비워두어야 합니다."})
            if lo is not None and hi is not None:
                if lo > hi:
                    raise ValidationError({lo_key: f"{lo_key} <= {hi_key} 여야 합니다."})
                intervals[name] = (float(lo), float(hi))

        # 반-열린(interv [lo, hi)) 기준으로 서로 겹치지 않는지 검사
        names = list(intervals.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                n1 = names[i]
                n2 = names[j]
                a_lo, a_hi = intervals[n1]
                b_lo, b_hi = intervals[n2]
                # overlap if a_lo < b_hi and b_lo < a_hi  (반-열린 기준에서 경계 접합은 허용)
                if (a_lo < b_hi) and (b_lo < a_hi):
                    # 허용되는 경우: 정확히 a_hi == b_lo 또는 b_hi == a_lo (경계 접합)
                    if not (a_hi == b_lo or b_hi == a_lo):
                        raise ValidationError(f"구간 '{n1}'과 '{n2}'이(가) 겹칩니다: {a_lo}-{a_hi} vs {b_lo}-{b_hi}. 경계는 접합(예: [a,b)와 [b,c))만 허용됩니다.")

    def save(self, *args, **kwargs):
        # 저장 전 검증
        try:
            self.full_clean()
        except Exception:
            raise
        super().save(*args, **kwargs)

    def evaluate(self, value):
        """주어진 값(value)에 대해 이 규칙만으로 판단한 결과를 반환합니다.
        반-열린 구간 표준: 각각 [min, max)
        반환값에 matched_range 포함(디버깅/운영용)
        """
        try:
            v = float(value)
        except Exception:
            return {'level': 'unknown', 'quality': 'unknown', 'matched_range': None}

        def resp(level_key, matched_range):
            lvl_label_default, ql_default = self.LEVEL_LABELS.get(level_key, ('Unknown', 'Unknown'))
            return {
                'level': level_key,
                'quality': ('good' if level_key == 'normal' else ('fair' if level_key == 'warning' else 'poor')),
                'label': self.level_label or lvl_label_default,
                'quality_label': self.quality_label or ql_default,
                'matched_range': matched_range
            }

        # high_risk
        if self.min_high_risk is not None and self.max_high_risk is not None:
            if self.min_high_risk <= v < self.max_high_risk:
                return resp('high_risk', {'min': self.min_high_risk, 'max': self.max_high_risk})
        # risk
        if self.min_risk is not None and self.max_risk is not None:
            if self.min_risk <= v < self.max_risk:
                return resp('risk', {'min': self.min_risk, 'max': self.max_risk})
        # warning
        if self.min_warn is not None and self.max_warn is not None:
            if self.min_warn <= v < self.max_warn:
                return resp('warning', {'min': self.min_warn, 'max': self.max_warn})
        # normal
        if self.min_good is not None and self.max_good is not None:
            if self.min_good <= v < self.max_good:
                return resp('normal', {'min': self.min_good, 'max': self.max_good})

        # 모든 구간에 속하지 않음 -> critical
        return resp('critical', None)

# 새로 추가: 평가 이벤트 로그 모델
class QualityEvent(models.Model):
    """측정값 평가 결과를 저장하는 이벤트 로그
    - source_type/source_id: 이벤트가 발생한 원본 (sensor, specimen 등)을 식별
    - variety/data_name: 어떤 품종/항목에 대해 평가했는지
    - value: 원시 측정값
    - level_name: NORMAL/INFO/WARNING/CRITICAL
    - level_severity: 정수 심각도(0..3)
    - quality: good/fair/poor
    - rule: 적용된 VarietyDataThreshold (선택)
    - message: 사람 읽을 수 있는 설명
    """
    SOURCE_CHOICES = [
        ('sensor', 'Sensor'),
        ('specimen', 'Specimen'),
        ('manual', 'Manual'),
        ('unknown', 'Unknown'),
    ]

    LEVEL_CHOICES = [
        ('NORMAL', 'Normal'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
    ]

    QUALITY_CHOICES = [
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='unknown')
    source_id = models.CharField(max_length=100, null=True, blank=True)

    variety = models.ForeignKey(Variety, on_delete=models.SET_NULL, null=True, blank=True, related_name='quality_events')
    data_name = models.ForeignKey('corecode.DataName', on_delete=models.SET_NULL, null=True, blank=True, related_name='quality_events')

    value = models.FloatField(null=True, blank=True)
    level_name = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    level_severity = models.IntegerField()  # 0..3
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES)
    rule = models.ForeignKey(VarietyDataThreshold, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.data_name}({self.value}) -> {self.level_name} ({self.quality})"

class RecipeItemValue(models.Model):
    recipe = models.ForeignKey(RecipeStep, null=True, blank=True, on_delete=models.CASCADE, related_name='item_values')
    # reference local ControlItem in agriseed app; corecode does not provide ControlItem
    control_item = models.ForeignKey('ControlItem', on_delete=models.CASCADE, null=True, blank=True, related_name='agriseed_recipe_values')
    set_value = models.FloatField(help_text="설정값 (목표값 등)")
    min_value = models.FloatField(null=True, blank=True, help_text="최소 허용값 (선택)")
    max_value = models.FloatField(null=True, blank=True, help_text="최대 허용값 (선택)")
    control_logic = models.ForeignKey('corecode.ControlLogic',null=True, blank=True, on_delete=models.CASCADE, related_name='recipe_item_values', help_text="적용할 제어 로직")
    priority = models.IntegerField(null=True, blank=True, help_text="우선순위 (선택)")

    def __str__(self):
        # recipe is now a RecipeStep, include profile name and step
        profile_name = self.recipe.recipe_profile.recipe_name
        step_name = self.recipe.name
        return f"{profile_name} - {step_name}: {self.control_item.item_name}"

class CalendarSchedule(models.Model):
    facility = models.ForeignKey('Facility', on_delete=models.CASCADE, null=True, blank=True, related_name='calendar_schedules', help_text="소속 시설")
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_schedules', help_text="관련 구역")
    crop = models.ForeignKey('Crop', on_delete=models.SET_NULL, null=True, blank=True, help_text="작물 종류")
    variety = models.ForeignKey('Variety', on_delete=models.SET_NULL, null=True, blank=True, help_text="품종")
    enabled = models.BooleanField()
    # 새로 추가된 필드: 구역별 사용 종자량
    expected_yield = models.FloatField(default=0.0, null=True, blank=True, help_text="예상 수확량(kg)")
    sowing_date = models.DateField(null=True, blank=True, help_text="파종일")
    expected_harvest_date = models.DateField(null=True, blank=True, help_text="예상 수확일")
    seed_amount = models.FloatField(default=0.0, help_text="사용 종자량 (단위: g, 기본값: 0.0)")
    recipe_profile = models.ForeignKey(RecipeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='zones', help_text="적용된 레시피 프로필 (단일)")

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_calendar_schedules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")


# 커뮤니티 피드백, 별점 및 레시피 성과 관리 기능 모델 추가
class RecipeComment(models.Model):
    recipe = models.ForeignKey(RecipeProfile, on_delete=models.CASCADE, related_name='comments', help_text="레시피에 대한 코멘트")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recipe_comments', help_text="작성자")
    content = models.TextField(help_text="코멘트 내용")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE, related_name='replies',
        help_text="부모 코멘트"
    )

    @property
    def helpful_count(self):
        return self.votes.filter(is_helpful=True).count()

    @property
    def unhelpful_count(self):
        return self.votes.filter(is_helpful=False).count()

    def __str__(self):
        return f"{self.recipe} - {self.user}: {self.content[:20]}"

class RecipeRating(models.Model):
    recipe = models.ForeignKey(RecipeProfile, on_delete=models.CASCADE, related_name='ratings', help_text="레시피에 대한 별점")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recipe_ratings', help_text="평가자")
    rating = models.PositiveSmallIntegerField(help_text="별점 (1~5)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('recipe', 'user')

    def __str__(self):
        return f"{self.recipe} - {self.rating}"

class RecipePerformance(models.Model):
    recipe = models.ForeignKey(RecipeProfile, on_delete=models.CASCADE, related_name='performances', help_text="레시피 시도 결과")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recipe_performances', help_text="시행자")
    yield_amount = models.FloatField(help_text="수확량 (kg)")
    success = models.BooleanField(help_text="성공 여부")
    notes = models.TextField(null=True, blank=True, help_text="추가 메모")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recipe} - yield={self.yield_amount}, success={self.success}"

# 코멘트 도움됨/도움안됨 표시용 모델
class RecipeCommentVote(models.Model):
    comment = models.ForeignKey(
        RecipeComment, on_delete=models.CASCADE,
        related_name='votes', help_text="코멘트에 대한 투표"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='comment_votes', help_text="투표한 사용자"
    )
    is_helpful = models.BooleanField(help_text="도움됨(True)/도움안됨(False)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('comment', 'user')

    def __str__(self):
        status = '도움됨' if self.is_helpful else '도움안됨'
        return f"{self.comment} - {self.user}: {status}"

class Tree(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='trees', help_text="소속된 구역")
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name='varieties', help_text="연결된 품종")
    tree_code = models.CharField(max_length=20, help_text="현장 표기 (예: B12-034)")
    notes = models.TextField(null=True, blank=True, help_text="특이사항")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tree_age = models.IntegerField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    height = models.FloatField(help_text="Height in meters")
    diameter = models.FloatField(help_text="Diameter in centimeters")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    def __str__(self):
        # 모델 필드에 맞게 표시값을 수정 (tree_code 우선 사용)
        return f"{self.tree_code}"
     

# 수확 전과 수확 후 기준 boolean
# Tree_tags에 영농일지 작성
class Tree_tags(models.Model):
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='tags', help_text="소속된 나무")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    barcode_type = models.CharField(max_length=20, help_text="바코드 유형 (예: QR, Code128 등)")
    barcode_value = models.CharField(max_length=100, help_text="바코드 값")
    qr_payload = models.TextField(help_text="QR 코드 페이로드 (예: URL 또는 JSON)")
    height_level = models.CharField(max_length=20, null=True, blank=True, help_text="상단, 중단, 하단 구분")
    degree = models.IntegerField(help_text="나침반 각도", null=True, blank=True)
    issue_date = models.DateField(help_text="발급일", null=True, blank=True)
    issued_by = models.CharField(max_length=100, help_text="발급자")
    valid_from = models.DateField(help_text="유효 시작일")
    valid_to = models.DateField(null=True, blank=True, help_text="유효 종료일 (빈 값이면 무한대로 간주)")
    is_active = models.BooleanField(default=True, help_text="태그 활성화 여부")
    notes = models.TextField(null=True, blank=True, help_text="특이사항")

    # 새로 추가: 수확 전/수확 후 구분 및 영농일지 관련 필드
    # 수확 상태는 단일 boolean으로 관리합니다. (True = 수확 후, False = 수확 전)
    is_post_harvest = models.BooleanField(default=False, help_text="이 태그가 수확 후 기준인지 여부 (True=수확후, False=수확전)")
    has_farm_log = models.BooleanField(default=False, help_text="영농일지 작성 여부")
    farm_log = models.TextField(null=True, blank=True, help_text="태그와 연결된 영농일지(간단 텍스트 저장)")

    def __str__(self):
        # tree.name 및 self.tag 는 모델에 존재하지 않음 -> 안전하게 tree_code와 barcode_value 사용
        return f"{self.tree.tree_code} - {self.barcode_value}"

class TreeImage(models.Model):
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='images', help_text="연결된 나무")
    image = models.ImageField(upload_to='tree_images/', help_text="나무 이미지")
    caption = models.CharField(max_length=200, null=True, blank=True, help_text="이미지 설명")
    taken_at = models.DateTimeField(null=True, blank=True, help_text="촬영 일시")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="업로드 일시")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    def __str__(self):
        return f"{self.tree.tree_code} - {self.caption or self.uploaded_at:%Y-%m-%d}"

# SpecimenData.sample_type 표본데이터의 기준값 및 범위와 분류명, 단계지수를 관리하는 테이블
# 수확 전과 수확 후 기준 boolean
class SpecimenData(models.Model):
    """표본(샘플) 데이터 저장용 모델
    - tree: 관련 나무 (있을 경우 연결)
    - specimen_code: 현장 표본 코드
    - collected_by: 채집자
    - collected_at: 채집 일시
    - sample_type: 표본 유형 (예: 잎, 토양, 씨앗 등)
    - measurements: 측정값(온도, 수분 등) JSON
    - attachments: 추가 파일(이미지 등)의 경로를 JSON으로 저장
    """
    tree = models.ForeignKey(Tree, null=True, blank=True, on_delete=models.SET_NULL, related_name='specimens', help_text="관련 나무(선택)")
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='collected_specimens', help_text="채집자(사용자, 선택)")
    collected_at = models.DateTimeField(null=True, blank=True, help_text="채집 일시")
    sample_type = models.CharField(max_length=50, null=True, blank=True, help_text="표본 유형(예: 잎, 토양)")
    measurements = models.JSONField(null=True, blank=True, help_text="측정값(JSON, 예: {'moisture': 12.3, 'ph': 6.5})")
    attachments = models.JSONField(null=True, blank=True, help_text="첨부파일 경로 목록(JSON)")
    notes = models.TextField(null=True, blank=True, help_text="비고/특이사항")

    # 새로 추가: 수확 전/수확 후 기준 boolean 값
    # 수확 상태는 단일 boolean으로 관리합니다. (True = 수확 후, False = 수확 전)
    is_post_harvest = models.BooleanField(default=False, help_text="이 표본이 수확 후 시점에 채집되었는지 여부 (Tree_tags 기준으로 동기화)")

    created_at = models.DateTimeField(auto_now_add=True, help_text="기록 생성일시")
    updated_at = models.DateTimeField(auto_now=True, help_text="기록 수정일시")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Specimen {self.specimen_code} ({self.sample_type or 'unknown'})"

    def save(self, *args, **kwargs):
        # tree가 연결되어 있을 경우 가장 최근의 Tree_tags 기준으로 수확 전/후 플래그를 동기화
        try:
            if self.tree:
                latest_tag = self.tree.tags.order_by('-created_at').first()
                if latest_tag:
                    # 태그의 is_post_harvest 값을 표본에 복사 (True=수확후, False=수확전)
                    self.is_post_harvest = bool(latest_tag.is_post_harvest)
        except Exception:
            # 안전하게 무시하고 저장되도록 함
            pass
        super().save(*args, **kwargs)

class SpecimenAttachment(models.Model):
    """SpecimenData에 연결된 파일(이미지 등)을 저장하는 모델
    - specimen: 연결된 표본
    - file: 업로드된 파일
    - filename, content_type: 메타데이터
    - is_image: 이미지 여부 빠른 판별
    """
    specimen = models.ForeignKey(SpecimenData, on_delete=models.CASCADE, related_name='attachments_files')
    file = models.FileField(upload_to='specimen_attachments/')
    filename = models.CharField(max_length=200, null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_image = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    def __str__(self):
        return f"{self.specimen.specimen_code} - {self.filename or self.file.name}"

# --- 이전된 모델들 (corecode에서 agriseed로 이동) ---
class Module(models.Model):
    name = models.CharField(max_length=120, help_text='모듈 이름 (예: 관수 모듈 A)')
    description = models.TextField(blank=True, null=True, help_text='모듈 설명')
    
    order = models.PositiveIntegerField(default=0, help_text='모듈 정렬 순서')
    is_enabled = models.BooleanField(default=True, help_text='모듈 활성화 여부')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # DeviceInstance는 FK(module)로 연결되며, 역참조로 module.devices 를 통해 접근합니다. (M2M 제거)
    class Meta:
        indexes = [models.Index(fields=['is_enabled'])]
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name}"

class DeviceInstance(models.Model):
    # 소속 모듈 (모듈을 통해 facility 역추적 가능하나 조회 최적화를 위해 facility 별도 저장)
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices', help_text='소속 모듈')
    # 단일 물리 디바이스 FK (Option A) - 기존 M2M 제거
    device = models.ForeignKey('corecode.Device', on_delete=models.SET_NULL, null=True, blank=True, related_name='agriseed_device_instances', help_text='연결된 코어 디바이스')
    # 어댑터 (필드명 Adapter -> adapter 로 표준화)
    adapter = models.ForeignKey('corecode.Adapter', on_delete=models.SET_NULL, null=True, blank=True, related_name='agriseed_device_instances', help_text='연결된 어댑터')

    # 인스턴스 식별자
    serial_number = models.CharField(max_length=100, unique=True, help_text='장치 고유 시리얼 번호')
    name = models.CharField(max_length=150, blank=True, null=True, help_text='인스턴스별 표시명 (선택)')
    status = models.CharField(max_length=30, default='idle', help_text='상태 (예: idle, active, fault)')
    last_seen = models.DateTimeField(null=True, blank=True, help_text='마지막 응답 시각')
    location_within_module = models.CharField(max_length=200, blank=True, null=True, help_text='모듈 내 설치 위치(예: 구역A-포인트3)')
    install_date = models.DateField(null=True, blank=True, help_text='설치 일자')
    is_active = models.BooleanField(default=True, help_text='활성 여부')

    # 관련 메모리 그룹 (Adapter + Device 조합으로 자동 연결)
    memory_groups = models.ManyToManyField('corecode.MemoryGroup', blank=True, related_name='device_instances', help_text='연결된 메모리 그룹')
    # 제어 그룹
    control_groups = models.ManyToManyField('ControlGroup', blank=True, related_name='device_instances', help_text='연결된 제어 그룹')
    # 계산 그룹
    calc_groups = models.ManyToManyField('corecode.CalcGroup', blank=True, related_name='device_instances', help_text='연결된 계산 그룹')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['status']),
        ]
        ordering = ['id']

    def __str__(self):
        label = self.name or (self.device.name if self.device else 'DeviceInstance')
        return f"{label} [{self.serial_number}]"

    def save(self, *args, **kwargs):
        # 제거: module.facility 및 self.facility 는 모델에 존재하지 않음
        # facility 자동 동기화 (module 변경 시) 로직은 미사용 처리
        super().save(*args, **kwargs)
        # 메모리 그룹 자동 연결 로직
        try:
            if self.adapter and self.device:
                qs = self.adapter.memory_groups.filter(Device=self.device)
                current_ids = set(self.memory_groups.values_list('id', flat=True))
                target_ids = set(qs.values_list('id', flat=True))
                for mg_id in target_ids - current_ids:
                    self.memory_groups.add(mg_id)
                # for mg_id in current_ids - target_ids:
                #     self.memory_groups.remove(mg_id)
        except Exception:
            pass

class ControlGroup(models.Model):
    # project_version 의존 제거 및 독립 그룹으로 변경
    # ...existing code...
    group_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    name = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        # group_id가 없을 수도 있으므로 id로 보조 정렬
        ordering = ['group_id', 'id']

    def __str__(self):
        gid = self.group_id if self.group_id is not None else '-'
        return f"ControlGroup {gid} ({self.name})"


class ControlVariable(models.Model):
    group = models.ForeignKey(ControlGroup, on_delete=models.CASCADE, blank=True, null=True, related_name='agriseed_control_variables_in_group')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='agriseed_as_control_variable')
    data_type = models.CharField(max_length=20, blank=True)
    applied_logic = models.ForeignKey('corecode.ControlLogic', on_delete=models.CASCADE, related_name='agriseed_applications')
    args = models.JSONField(default=list, blank=True, help_text="함수 인자값을 순서대로 저장 (리스트)")
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name.name if self.name else 'Unnamed'} using {self.applied_logic.name if self.applied_logic else 'N/A'}"


class CalcVariable(models.Model):
    group = models.ForeignKey('corecode.CalcGroup', on_delete=models.CASCADE, blank=True, null=True, related_name='agriseed_calc_variables_in_group')
    name = models.ForeignKey('corecode.DataName', on_delete=models.CASCADE, related_name='agriseed_as_calc_variable')
    data_type = models.CharField(max_length=20, blank=True)
    use_method = models.CharField(max_length=40, null=True, blank=True)
    args = models.JSONField(default=list, blank=True, help_text="함수 인자값을 순서대로 저장 (리스트)")
    attributes = models.JSONField(default=list, blank=True, help_text="['감시','제어','기록','경보'] 중 복수 선택")

    def __str__(self):
        return f"{self.name}"

