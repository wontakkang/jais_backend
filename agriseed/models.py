from django.db import models
from django.contrib.postgres.fields import RangeField
from django.db.models import JSONField
from corecode.models import DataName, ControlLogic  # ensure ControlLogic imported
from django.conf import settings

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

class Schedule(models.Model):
    icon = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    schedule = models.CharField(max_length=200)
    description = models.TextField()
    enabled = models.BooleanField()
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

class Facility(models.Model):
    name = models.CharField(max_length=100, default="Unknown Facility", help_text="시설 이름")
    type = models.CharField(max_length=50, default="vinyl", help_text="시설 유형 (예: vinyl, glass 등)")
    location = models.CharField(max_length=200, default="Unknown Location", help_text="시설 위치")
    area = models.FloatField(default=100.0, help_text="시설 면적 (기본값: 100 제곱미터)")
    zone_count = models.IntegerField(default=1, help_text="구역 수 (기본값: 1)")
    manager = models.CharField(max_length=100, default="Unknown Manager", help_text="시설 관리자")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    LSIS = JSONField(null=True, blank=True, help_text="토양 조건")

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

class Zone(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='zones', help_text="소속된 시설")
    name = models.CharField(max_length=100, default="Default Zone", help_text="구역 이름")
    type = models.CharField(max_length=50, default="온실", help_text="구역 유형 (예: 온실, 저장고 등)")
    area = models.FloatField(default=50.0, help_text="구역 면적 (기본값: 50 제곱미터)")
    crop = models.ForeignKey('Crop', on_delete=models.SET_NULL, null=True, blank=True, help_text="작물 종류")
    variety = models.ForeignKey('Variety', on_delete=models.SET_NULL, null=True, blank=True, help_text="품종")
    style = models.CharField(max_length=50, default="일반", null=True, blank=True, help_text="구역 스타일 (예: 일반, 특수 등)")
    expected_yield = models.FloatField(default=0.0, null=True, blank=True, help_text="예상 수확량(kg)")
    sowing_date = models.DateField(null=True, blank=True, help_text="파종일")
    expected_harvest_date = models.DateField(null=True, blank=True, help_text="예상 수확일")
    health_status = models.CharField(max_length=50, default="양호", null=True, blank=True, help_text="건강 상태 (예: 양호, 주의, 위험 등)")
    environment_status = models.CharField(max_length=50, default="정상", null=True, blank=True, help_text="환경 상태 (예: 정상, 주의, 위험 등)")
    STATUS_CHOICES = [
        ("활성화", "활성화"),
        ("비활성화", "비활성화"),
        ("작업중", "작업중"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="활성화", null=True, blank=True, help_text="구역 상태 (활성화, 비활성화, 작업중)")
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")
    watering_amount_per_time = models.FloatField(default=0.0, help_text="1회 급수량 (L)")
    daily_watering_count = models.IntegerField(default=1, help_text="일일 급수 횟수")
    watering_interval = models.CharField(max_length=50, default="매일", help_text="공급 주기 (예: 매일, 격일 등)")
    watering_amount = models.FloatField(default=0.0, help_text="공급량 (mL)")

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
    item_name = models.ForeignKey(DataName, on_delete=models.CASCADE, null=True, blank=True, related_name='control_items', help_text="제어 항목명(DataName)")
    description = models.TextField(blank=True, help_text="설명")

    def __str__(self):
        return f"{self.description}({self.item_name})"

class RecipeItemValue(models.Model):
    recipe = models.ForeignKey(RecipeStep, null=True, blank=True, on_delete=models.CASCADE, related_name='item_values')
    control_item = models.ForeignKey(ControlItem, on_delete=models.CASCADE, null=True, blank=True, related_name='recipe_values')
    set_value = models.FloatField(help_text="설정값 (목표값 등)")
    min_value = models.FloatField(null=True, blank=True, help_text="최소 허용값 (선택)")
    max_value = models.FloatField(null=True, blank=True, help_text="최대 허용값 (선택)")
    control_logic = models.ForeignKey(ControlLogic,null=True, blank=True, on_delete=models.CASCADE, related_name='recipe_item_values', help_text="적용할 제어 로직")
    priority = models.IntegerField(null=True, blank=True, help_text="우선순위 (선택)")

    def __str__(self):
        # recipe is now a RecipeStep, include profile name and step
        profile_name = self.recipe.recipe_profile.recipe_name
        step_name = self.recipe.name
        return f"{profile_name} - {step_name}: {self.control_item.item_name}"

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
