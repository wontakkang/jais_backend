from rest_framework import serializers
from .models import *
from corecode.models import DataName
from django.contrib.auth import get_user_model
User = get_user_model()

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        exclude = ('is_deleted',)

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        exclude = ('is_deleted',)

class ControlHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlHistory
        exclude = ('is_deleted',)

class ControlRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlRole
        exclude = ('is_deleted',)

class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        exclude = ('is_deleted',)

class ResolvedIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResolvedIssue
        exclude = ('is_deleted',)

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        exclude = ('is_deleted',)

class ZoneSerializer(serializers.ModelSerializer):
    facility = serializers.PrimaryKeyRelatedField(queryset=Facility.objects.all(), help_text='시설 ID (PK). 예: 12', style={'example': 12})
    crop = serializers.PrimaryKeyRelatedField(queryset=Crop.objects.all(), allow_null=True, required=False, help_text='작물 ID (선택). 예: 3', style={'example': 3})
    variety = serializers.PrimaryKeyRelatedField(queryset=Variety.objects.all(), allow_null=True, required=False, help_text='품종 ID (선택). 예: 7', style={'example': 7})

    # Zone당 하나의 레시피(ForeignKey)를 recipe_profile로 노출
    recipe_profile = serializers.PrimaryKeyRelatedField(
        queryset=RecipeProfile.objects.all(),
        required=False,
        allow_null=True,
        help_text='적용된 레시피 프로필 ID (선택). 예: 5',
        style={'example': 5}
    )

    facility_name = serializers.SerializerMethodField(read_only=True)
    crop_name = serializers.SerializerMethodField(read_only=True)
    variety_name = serializers.SerializerMethodField(read_only=True)
    name = serializers.CharField(help_text='구역 이름. 예: "동1-구역A"', style={'example': '동1-구역A'})
    area = serializers.FloatField(required=False, allow_null=True, help_text='면적(제곱미터, 선택). 예: 120.5', style={'example': 120.5})

    class Meta:
        model = Zone
        fields = ['id', 'facility', 'facility_name', 'name', 'type', 'area', 'crop', 'crop_name', 'variety', 'variety_name', 'style', 'expected_yield', 'sowing_date', 'expected_harvest_date', 'health_status', 'environment_status', 'status', 'is_deleted', 'seed_amount', 'recipe_profile']
        read_only_fields = ['id', 'facility_name', 'crop_name', 'variety_name']

    def get_facility_name(self, obj):
        return obj.facility.name if obj.facility else None

    def get_crop_name(self, obj):
        return obj.crop.name if obj.crop else None

    def get_variety_name(self, obj):
        return obj.variety.name if obj.variety else None

    def validate_name(self, value):
        # Ensure zone name is not empty
        if not value or not str(value).strip():
            raise serializers.ValidationError('Zone name must not be empty')
        return value

    def create(self, validated_data):
        # recipe_profile은 ForeignKey이므로 바로 전달
        zone = Zone.objects.create(**validated_data)
        return zone

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance

class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        exclude = ('is_deleted',)

class FacilityHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityHistory
        exclude = ('is_deleted',)

class ControlSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlSettings
        exclude = ('is_deleted',)

class FacilitySerializer(serializers.ModelSerializer):
    control_settings = ControlSettingsSerializer(many=True)
    zones = ZoneSerializer(many=True, read_only=True)
    class Meta:
        model = Facility
        exclude = ('is_deleted',)

    def create(self, validated_data):
        control_settings_data = validated_data.pop('control_settings', [])
        facility = Facility.objects.create(**validated_data)
        for cs_data in control_settings_data:
            ControlSettings.objects.create(facility=facility, **cs_data)
        return facility

    def update(self, instance, validated_data):
        control_settings_data = validated_data.pop('control_settings', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        # 기존 ControlSettings 삭제 및 재생성 (간단 구현)
        instance.control_settings.all().delete()
        for cs_data in control_settings_data:
            ControlSettings.objects.create(facility=instance, **cs_data)
        return instance


class VarietyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VarietyImage
        fields = '__all__'

class VarietyGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = VarietyGuide
        fields = '__all__'



class VarietySerializer(serializers.ModelSerializer):
    images = VarietyImageSerializer(many=True, read_only=True)

    class Meta:
        model = Variety
        fields = '__all__'

class CropSerializer(serializers.ModelSerializer):
    varieties = VarietySerializer(many=True, read_only=True)

    class Meta:
        model = Crop
        fields = '__all__'


class ControlItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlItem
        fields = ['id', 'item_name', 'description']

class RecipeItemValueSerializer(serializers.ModelSerializer):
    control_item = serializers.PrimaryKeyRelatedField(queryset=ControlItem.objects.all(), help_text='ControlItem ID. 예: 2', style={'example': 2})
    set_value = serializers.FloatField(help_text='설정 값 (실수). 예: 23.5', style={'example': 23.5})
    min_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최소값 (선택). 예: 10.0', style={'example': 10.0})
    max_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최대값 (선택). 예: 40.0', style={'example': 40.0})

    class Meta:
        model = RecipeItemValue
        fields = ['id', 'control_item', 'set_value', 'min_value', 'max_value', 'control_logic', 'priority']

class RecipeStepSerializer(serializers.ModelSerializer):
    item_values = RecipeItemValueSerializer(many=True, required=False, help_text='이 스텝에 포함된 항목값 목록 (선택)')
    name = serializers.CharField(help_text='스텝 이름. 예: "발아 단계"', style={'example': '발아 단계'})
    duration_days = serializers.IntegerField(required=False, allow_null=True, help_text='지속 일수 (선택). 예: 7', style={'example': 7})
    class Meta:
        model = RecipeStep
        fields = ['id', 'recipe_profile', 'name', 'order', 'duration_days', 'description', 'item_values', 'label_icon', 'active']

    def create(self, validated_data):
        item_values_data = validated_data.pop('item_values', [])
        step = RecipeStep.objects.create(**validated_data)
        for iv in item_values_data:
            RecipeItemValue.objects.create(recipe=step, **iv)
        return step

    def update(self, instance, validated_data):
        item_values_data = validated_data.pop('item_values', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if item_values_data is not None:
            # 간단 구현: 기존 항목값 삭제 후 재생성
            instance.item_values.all().delete()
            for iv in item_values_data:
                RecipeItemValue.objects.create(recipe=instance, **iv)
        return instance

class RecipePerformanceSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    recipe = serializers.PrimaryKeyRelatedField(queryset=RecipeProfile.objects.all(), help_text='레시피 프로필 ID', style={'example': 5})
    class Meta:
        model = RecipePerformance
        fields = ['id', 'recipe', 'user', 'yield_amount', 'success', 'notes', 'created_at']

class RecipeRatingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    recipe = serializers.PrimaryKeyRelatedField(queryset=RecipeProfile.objects.all(), help_text='레시피 프로필 ID', style={'example': 5})
    class Meta:
        model = RecipeRating
        fields = ['id', 'recipe', 'user', 'rating', 'created_at']

class RecipeCommentVoteSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    comment = serializers.PrimaryKeyRelatedField(queryset=RecipeComment.objects.all(), help_text='댓글 ID', style={'example': 11})
    class Meta:
        model = RecipeCommentVote
        fields = ['id', 'comment', 'user', 'is_helpful', 'created_at']

class RecipeCommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    replies = serializers.SerializerMethodField()
    helpful_count = serializers.IntegerField(read_only=True)
    unhelpful_count = serializers.IntegerField(read_only=True)
    votes = RecipeCommentVoteSerializer(many=True, read_only=True)
    content = serializers.CharField(help_text='댓글 내용', style={'example': '유용한 레시피입니다.'})

    class Meta:
        model = RecipeComment
        fields = ['id', 'recipe', 'user', 'content', 'created_at', 'updated_at', 'parent',
                  'helpful_count', 'unhelpful_count', 'replies', 'votes']

    def get_replies(self, obj):
        qs = obj.replies.all()
        return RecipeCommentSerializer(qs, many=True).data

class RecipeProfileSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)
    steps = RecipeStepSerializer(many=True, required=False)
    comments = RecipeCommentSerializer(many=True, read_only=True)
    performances = RecipePerformanceSerializer(many=True, read_only=True)
    ratings = RecipeRatingSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    average_yield = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    class Meta:
        model = RecipeProfile
        fields = [
            'id', 'variety', 'recipe_name', 'description', 'duration_days',
            'order', 'is_active', 'created_at', 'updated_at',
            'created_by', 'updated_by', 'steps', 'comments', 'performances',
            'ratings', 'average_rating', 'rating_count', 'average_yield', 'success_rate', 'bookmark'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        profile = RecipeProfile.objects.create(**validated_data)
        for step_data in steps_data:
            item_values_data = step_data.pop('item_values', [])
            step = RecipeStep.objects.create(recipe_profile=profile, **step_data)
            for iv in item_values_data:
                RecipeItemValue.objects.create(recipe=step, **iv)
        return profile

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if steps_data is not None:
            instance.steps.all().delete()
            for step_data in steps_data:
                item_values_data = step_data.pop('item_values', [])
                step = RecipeStep.objects.create(recipe_profile=instance, **step_data)
                for iv in item_values_data:
                    RecipeItemValue.objects.create(recipe=step, **iv)
        return instance

# Tree 및 Tree_tags 직렬화기 추가
class TreeTagsSerializer(serializers.ModelSerializer):
    # tree를 nested 생성시 생략할 수 있도록 선택적으로 만듭니다.
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), required=False, allow_null=True, help_text='연결된 Tree ID (선택)', style={'example': 42})
    # 단일 boolean 필드로 수확 상태를 관리 (True=수확후)
    is_post_harvest = serializers.BooleanField(required=False, default=False, help_text='수확 후 여부 (True=수확후)', style={'example': False})
    has_farm_log = serializers.BooleanField(required=False, default=False, help_text='농장일지 포함 여부 (선택)', style={'example': False})

    class Meta:
        model = Tree_tags
        fields = '__all__'

class TreeSerializer(serializers.ModelSerializer):
    tags = TreeTagsSerializer(many=True, required=False)
    variety = serializers.PrimaryKeyRelatedField(queryset=Variety.objects.all())
    zone = serializers.PrimaryKeyRelatedField(queryset=Zone.objects.all())
    class Meta:
        model = Tree
        fields = '__all__'
    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        tree = Tree.objects.create(**validated_data)
        for tag_data in tags_data:
            Tree_tags.objects.create(tree=tree, **tag_data)
        return tree

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags_data is not None:
            instance.tags.all().delete()
            for tag_data in tags_data:
                Tree_tags.objects.create(tree=instance, **tag_data)
        return instance

# 새로 추가: TreeImage 및 SpecimenData 직렬화기
class TreeImageSerializer(serializers.ModelSerializer):
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all())
    class Meta:
        model = TreeImage
        fields = '__all__'

# 새로 추가: SpecimenAttachment 직렬화기
class SpecimenAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SpecimenAttachment
        fields = ['id', 'file', 'file_url', 'filename', 'content_type', 'uploaded_at', 'is_image', 'is_deleted']
        read_only_fields = ('uploaded_at', 'is_image', 'content_type', 'filename')

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None

class SpecimenDataSerializer(serializers.ModelSerializer):
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), allow_null=True, required=False, help_text='연결된 Tree ID (선택)', style={'example': 42})
    collected_by = serializers.StringRelatedField(read_only=True)
    attachments_files = SpecimenAttachmentSerializer(many=True, read_only=True, help_text='첨부 파일 리스트 (읽기전용)')
    # Specimen의 수확 상태는 Tree_tags에서 동기화되므로 API 기본 동작에서는 읽기 전용으로 노출
    is_post_harvest = serializers.BooleanField(read_only=True, help_text='수확 후 여부 (읽기전용)')

    class Meta:
        model = SpecimenData
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at',)

class SensorItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID (예: 온도). 예: 8', style={'example': 8})

    class Meta:
        model = SensorItem
        fields = ['id', 'item_name', 'description']


class MeasurementItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID (예: 측정값). 예: 9', style={'example': 9})

    class Meta:
        model = MeasurementItem
        fields = ['id', 'item_name', 'description']

class VarietyDataThresholdSerializer(serializers.ModelSerializer):
    variety = serializers.PrimaryKeyRelatedField(queryset=Variety.objects.all(), help_text='품종 ID', style={'example': 7})
    data_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID', style={'example': 8})

    class Meta:
        model = VarietyDataThreshold
        fields = ['id', 'variety', 'data_name', 'min_good', 'max_good', 'min_warn', 'max_warn', 'min_risk', 'max_risk', 'min_high_risk', 'max_high_risk', 'priority', 'note', 'is_active', 'level_label', 'quality_label', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        # 범위 논리 검증
        def check_pair(a_key, b_key, name):
            a = attrs.get(a_key) if a_key in attrs else None
            b = attrs.get(b_key) if b_key in attrs else None
            if a is not None and b is not None and a > b:
                raise serializers.ValidationError(f'{a_key} must be <= {b_key} for {name}')

        check_pair('min_good', 'max_good', 'good')
        check_pair('min_warn', 'max_warn', 'warn')
        check_pair('min_risk', 'max_risk', 'risk')
        check_pair('min_high_risk', 'max_high_risk', 'high_risk')
        return attrs

class QualityEventSerializer(serializers.ModelSerializer):
    variety = serializers.StringRelatedField()
    data_name = serializers.StringRelatedField()

    class Meta:
        model = QualityEvent
        fields = ['id', 'source_type', 'source_id', 'variety', 'data_name', 'value', 'level_name', 'level_severity', 'quality', 'rule', 'message', 'created_at']
        read_only_fields = ['created_at']


class EvaluateMeasurementInputSerializer(serializers.Serializer):
    data_name = serializers.IntegerField()
    variety = serializers.IntegerField(required=False, allow_null=True)
    value = serializers.FloatField()
    source_type = serializers.ChoiceField(choices=[('sensor','Sensor'),('specimen','Specimen'),('manual','Manual')], required=False, default='unknown')
    source_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

# CalendarEvent 및 TodoItem 직렬화기 추가 (공개 필드명과 내부 필드명 분리: source= 사용)
class CalendarEventSerializer(serializers.ModelSerializer):
    facilityId = serializers.PrimaryKeyRelatedField(source='facility', queryset=Facility.objects.all(), allow_null=True, required=False, help_text='시설 ID (Facility primary key). 예: 12')
    title = serializers.CharField(help_text='이벤트 제목. 예: "수확 준비"', style={'example': '수확 준비'})
    description = serializers.CharField(allow_blank=True, required=False, help_text='상세 설명. 예: "수확 관련 미팅 및 준비사항"', style={'example': '수확 관련 미팅 및 준비사항'})
    start = serializers.DateTimeField(help_text='시작 시간 (ISO 8601, Asia/Seoul +09:00). 예: 2025-09-11T10:00:00+09:00', style={'example': '2025-09-11T10:00:00+09:00'})
    end = serializers.DateTimeField(allow_null=True, required=False, help_text='종료 시간 (ISO 8601, 선택, Asia/Seoul +09:00). 예: 2025-09-11T12:00:00+09:00', style={'example': '2025-09-11T12:00:00+09:00'})
    allDay = serializers.BooleanField(source='all_day', default=False, help_text='종일 여부 (True/False). 예: False', style={'example': False})
    location = serializers.CharField(allow_blank=True, allow_null=True, required=False, help_text='장소(선택). 예: "온실 A 동"', style={'example': '온실 A 동'})
    recurrence = serializers.JSONField(allow_null=True, required=False, help_text='반복 규칙(JSON, 선택).', style={'type':'object'})
    reminders = serializers.JSONField(allow_null=True, required=False, help_text='알림 설정(JSON 배열, 선택).', style={'type':'array','itemType':'object'})
    attendeeIds = serializers.PrimaryKeyRelatedField(source='attendees', many=True, queryset=User.objects.all(), required=False, help_text='참석자 사용자 ID 리스트.')
    createdBy = serializers.PrimaryKeyRelatedField(source='created_by', read_only=True, help_text='작성자(읽기전용). 사용자 ID')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')

    class Meta:
        model = CalendarEvent
        # 내부 필드(is_deleted 등)는 노출하지 않음
        fields = ['id', 'facilityId', 'title', 'description', 'start', 'end', 'allDay', 'location', 'recurrence', 'reminders', 'attendeeIds', 'createdBy', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdBy', 'createdAt', 'updatedAt']

    def create(self, validated_data):
        # attendees는 M2M이므로 인스턴스 생성 후 설정
        attendees = validated_data.pop('attendees', [])
        event = CalendarEvent.objects.create(**validated_data)
        if attendees:
            event.attendees.set(attendees)
        return event

    def update(self, instance, validated_data):
        attendees = validated_data.pop('attendees', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if attendees is not None:
            instance.attendees.set(attendees)
        return instance

class TodoItemSerializer(serializers.ModelSerializer):
    facilityId = serializers.PrimaryKeyRelatedField(source='facility', queryset=Facility.objects.all(), allow_null=True, required=False, help_text='시설 ID (Facility primary key). 예: 12')
    zoneId = serializers.PrimaryKeyRelatedField(source='zone', queryset=Zone.objects.all(), allow_null=True, required=False, help_text='구역 ID (Zone primary key). 예: 5')
    title = serializers.CharField(help_text='할일 제목. 예: "관수 점검"', style={'example': '관수 점검'})
    description = serializers.CharField(allow_blank=True, required=False, help_text='상세 설명(선택). 예: "펌프 점검 및 호스 교체 필요"', style={'example': '펌프 점검 및 호스 교체 필요'})
    createdBy = serializers.PrimaryKeyRelatedField(source='created_by', read_only=True, help_text='작성자(읽기전용). 사용자 ID')
    assignedTo = serializers.PrimaryKeyRelatedField(source='assigned_to', queryset=User.objects.all(), allow_null=True, required=False, help_text='담당자 사용자 ID(선택). 예: 3')
    dueDate = serializers.DateTimeField(source='due_date', allow_null=True, required=False, help_text='마감일 (ISO 8601, 선택, Asia/Seoul +09:00). 예: 2025-09-15T18:00:00+09:00', style={'example': '2025-09-15T18:00:00+09:00'})
    completed = serializers.BooleanField(default=False, help_text='완료 여부. True/False', style={'example': False})
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True, help_text='완료 시각 (읽기전용)')
    priority = serializers.IntegerField(default=2, help_text='우선순위(숫자). 예: 1=높음,2=중간,3=낮음', style={'example': 2})
    status = serializers.CharField(default='open', help_text='상태 문자열. 예: "open" 또는 "closed"', style={'example': 'open'})
    reminders = serializers.JSONField(allow_null=True, required=False, help_text='알림 설정(JSON 배열, 선택).', style={'type':'array','itemType':'object'})
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')

    class Meta:
        model = TodoItem
        # 내부 필드(is_deleted 등)는 노출하지 않음
        fields = ['id', 'facilityId', 'zoneId', 'title', 'description', 'createdBy', 'assignedTo', 'dueDate', 'completed', 'completedAt', 'priority', 'status', 'reminders', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdBy', 'createdAt', 'updatedAt', 'completedAt']
