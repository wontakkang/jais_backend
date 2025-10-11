from rest_framework import serializers
from .models import *
from corecode.models import DataName, ControlLogic
# Core Device/Adapter 참조 추가
from corecode.models import Device as CoreDevice, Adapter as CoreAdapter
from django.contrib.auth import get_user_model
from django.utils import timezone
from LSISsocket.models import MemoryGroup as LSISMemoryGroup
User = get_user_model()

# generate_serial_prefix_for_deviceinstance는 agriseed.models에 구현되어 있으므로 재사용합니다.
from .models import generate_serial_prefix_for_deviceinstance

# Core Device serializer import: use corecode's DeviceSerializer under alias to avoid name collision
from corecode.serializers import DeviceSerializer as CoreDeviceSerializer

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

class CalendarScheduleSerializer(serializers.ModelSerializer):
    facilityId = serializers.PrimaryKeyRelatedField(
        source='facility', queryset=Facility.objects.all(), allow_null=True, required=False, 
        help_text='시설 ID (Facility primary key). 예: 12', style={'type': 'integer'}
    )
    zoneId = serializers.PrimaryKeyRelatedField(
        source='zone', queryset=Zone.objects.all(), allow_null=True, required=False, 
        help_text='구역 ID (Zone primary key). 예: 5', style={'type': 'integer'}
    )
    cropId = serializers.PrimaryKeyRelatedField(
        source='crop', queryset=Crop.objects.all(), allow_null=True, required=False, 
        help_text='작물 ID (선택). 예: 3', style={'type': 'integer'}
    )
    varietyId = serializers.PrimaryKeyRelatedField(
        source='variety', queryset=Variety.objects.all(), allow_null=True, required=False, 
        help_text='품종 ID (선택). 예: 7', style={'type': 'integer'}
    )
    enabled = serializers.BooleanField(required=False, default=False, help_text='스케줄 활성화 여부', style={'example': False, 'type': 'boolean'})
    expectedYield = serializers.FloatField(source='expected_yield', required=False, allow_null=True, help_text='예상 수확량(kg)', style={'example': 120.5, 'type': 'number'})
    sowingDate = serializers.DateField(source='sowing_date', required=False, allow_null=True, help_text='파종일', style={'example': '2025-09-01', 'type': 'string', 'format': 'date'})
    expectedHarvestDate = serializers.DateField(source='expected_harvest_date', required=False, allow_null=True, help_text='예상 수확일', style={'example': '2026-02-01', 'type': 'string', 'format': 'date'})
    seedAmount = serializers.FloatField(source='seed_amount', required=False, help_text='사용 종자량 (g)', style={'example': 50.0, 'type': 'number'})
    recipeProfile = serializers.PrimaryKeyRelatedField(source='recipe_profile', queryset=RecipeProfile.objects.all(), required=False, allow_null=True, help_text='적용된 레시피 프로필 ID (선택). 예: 5', style={'example': 5, 'type': 'integer'})
    completed = serializers.BooleanField(required=False, default=False, help_text='완료 여부', style={'example': False, 'type': 'boolean'})
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True, help_text='완료 시간 (읽기전용)', style={'example': None, 'type': 'string', 'format': 'date-time'})
    createdBy = serializers.SlugRelatedField(source='created_by', slug_field='username', read_only=True, help_text='작성자 username (읽기전용)')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')

    class Meta:
        model = CalendarSchedule
        # expose public serializer field names mapped to model via 'source'
        fields = ['id', 'facilityId', 'zoneId', 'cropId', 'varietyId', 'enabled', 'expectedYield', 'sowingDate', 'expectedHarvestDate', 'seedAmount', 'recipeProfile', 'completed', 'completedAt', 'createdBy', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'completedAt', 'createdBy', 'createdAt', 'updatedAt']

    def get_crop_name(self, obj):
        return obj.crop.name if obj.crop else None

    def get_variety_name(self, obj):
        return obj.variety.name if obj.variety else None

class ZoneSerializer(serializers.ModelSerializer):
    facilityId = serializers.PrimaryKeyRelatedField(source='facility', queryset=Facility.objects.all(), help_text='시설 ID (Facility primary key). 예: 12', style={}, allow_null=True)
    facility_name = serializers.SerializerMethodField(read_only=True)
    name = serializers.CharField(help_text='구역 이름. 예: "동1-구역A"', style={'example': '동1-구역A'})
    area = serializers.FloatField(required=False, allow_null=True, help_text='면적(제곱미터, 선택). 예: 120.5', style={})

    # 타임스탬프 및 수정자 노출 (읽기 전용)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')
    updatedBy = serializers.SlugRelatedField(source='updated_by', slug_field='username', read_only=True, help_text='최종 수정자 username (읽기전용)')

    class Meta:
        model = Zone
        fields = ['id', 'facilityId', 'facility_name', 'name', 'type', 'area', 'style', 'health_status', 'environment_status', 'status', 'is_deleted', 'createdAt', 'updatedAt', 'updatedBy']
        read_only_fields = ['id', 'facility_name', 'createdAt', 'updatedAt', 'updatedBy']

    def get_facility_name(self, obj):
        return obj.facility.name if obj.facility else None

    def validate_name(self, value):
        # Ensure zone name is not empty
        if not value or not str(value).strip():
            raise serializers.ValidationError('Zone name must not be empty')
        return value

    def create(self, validated_data, **kwargs):
        # allow passing updated_by via serializer.save(updated_by=...)
        updated_by = kwargs.pop('updated_by', None)
        # fallback to request.user if available
        if not updated_by:
            req = self.context.get('request') if hasattr(self, 'context') else None
            if req and getattr(req, 'user', None) and req.user.is_authenticated:
                updated_by = req.user
        zone = Zone.objects.create(**validated_data)
        if updated_by:
            try:
                zone.updated_by = updated_by
                zone.save()
            except Exception:
                pass
        return zone

    def update(self, instance, validated_data, **kwargs):
        updated_by = kwargs.pop('updated_by', None)
        if not updated_by:
            req = self.context.get('request') if hasattr(self, 'context') else None
            if req and getattr(req, 'user', None) and req.user.is_authenticated:
                updated_by = req.user
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if updated_by:
            try:
                instance.updated_by = updated_by
            except Exception:
                pass
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
    # M2M module 노출 (ID 배열)
    module = serializers.PrimaryKeyRelatedField(many=True, queryset=Module.objects.all(), required=False)
    # nested control_settings는 선택 입력으로
    control_settings = ControlSettingsSerializer(many=True, required=False)
    zones = ZoneSerializer(many=True, read_only=True)
    calendar_schedules = CalendarScheduleSerializer(many=True, read_only=True)
    class Meta:
        model = Facility
        # include model DB fields except internal 'is_deleted', and also include declared nested/M2M fields
        fields = [f.name for f in model._meta.fields if f.name != 'is_deleted'] + ['module', 'control_settings', 'zones', 'calendar_schedules']

    def create(self, validated_data):
        control_settings_data = validated_data.pop('control_settings', [])
        modules = validated_data.pop('module', [])
        facility = Facility.objects.create(**validated_data)
        if modules:
            facility.module.set(modules)
        for cs_data in control_settings_data:
            ControlSettings.objects.create(facility=facility, **cs_data)
        return facility

    def update(self, instance, validated_data):
        control_settings_data = validated_data.pop('control_settings', [])
        modules = validated_data.pop('module', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if modules is not None:
            instance.module.set(modules)
        # 기존 ControlSettings 삭제 및 재생성 (간단 구현)
        if control_settings_data is not None:
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
        fields = ['id', 'order', 'item_name', 'description', 'scada_tag_name']

# simple top-level serializer to avoid nested name resolution issues
class ControlItemSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlItem
        fields = ['id', 'item_name', 'description', 'scada_tag_name']
        read_only_fields = fields

class RecipeItemValueSerializer(serializers.ModelSerializer):
    control_item = serializers.PrimaryKeyRelatedField(queryset=ControlItem.objects.all(), help_text='ControlItem ID. 예: 2', style={})
    set_value = serializers.FloatField(help_text='설정 값 (실수). 예: 23.5', style={'example': 23.5})
    min_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최소값 (선택). 예: 10.0', style={'example': 10.0})
    max_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최대값 (선택). 예: 40.0', style={'example': 40.0})

    class Meta:
        model = RecipeItemValue
        fields = ['id', 'control_item', 'set_value', 'min_value', 'max_value', 'control_logic', 'priority']

class RecipeStepSerializer(serializers.ModelSerializer):
    item_values = RecipeItemValueSerializer(many=True, required=False, help_text='이 스텝에 포함된 항목값 목록 (선택)')
    name = serializers.CharField(help_text='스텝 이름. 예: "발아 단계"', style={'example': '발아 단계'})
    duration_days = serializers.IntegerField(required=False, allow_null=True, help_text='지속 일수 (선택). 예: 7', style={})
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
    comment = serializers.PrimaryKeyRelatedField(queryset=RecipeComment.objects.all(), help_text='댓글 ID', style={})
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
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')
    steps = RecipeStepSerializer(many=True, required=False)
    comments = RecipeCommentSerializer(many=True, read_only=True)
    performances = RecipePerformanceSerializer(many=True, read_only=True)
    ratings = RecipeRatingSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    average_yield = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    createdBy = serializers.SlugRelatedField(source='created_by', slug_field='username', read_only=True, help_text='작성자 username (읽기전용)')
    updatedBy = serializers.SlugRelatedField(source='updated_by', slug_field='username', read_only=True, help_text='최종 수정자 username (읽기전용)')
    class Meta:
        model = RecipeProfile
        fields = [
            'id', 'variety', 'recipe_name', 'description', 'duration_days',
            'order', 'is_active', 'createdAt', 'updatedAt',
            'createdBy', 'updatedBy', 'steps', 'comments', 'performances',
            'ratings', 'average_rating', 'rating_count', 'average_yield', 'success_rate', 'bookmark'
        ]
        read_only_fields = ['createdAt', 'updatedAt', 'createdBy', 'updatedBy']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        # created_by/updated_by fallback from context request if not provided
        req = self.context.get('request') if hasattr(self, 'context') else None
        user = None
        if req and getattr(req, 'user', None) and req.user.is_authenticated:
            user = req.user
        # create profile with creator if available
        if user:
            profile = RecipeProfile.objects.create(created_by=user, updated_by=user, **validated_data)
        else:
            profile = RecipeProfile.objects.create(**validated_data)
        for step_data in steps_data:
            item_values_data = step_data.pop('item_values', [])
            step = RecipeStep.objects.create(recipe_profile=profile, **step_data)
            for iv in item_values_data:
                RecipeItemValue.objects.create(recipe=step, **iv)
        return profile

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        req = self.context.get('request') if hasattr(self, 'context') else None
        user = None
        if req and getattr(req, 'user', None) and req.user.is_authenticated:
            user = req.user
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if user:
            try:
                instance.updated_by = user
            except Exception:
                pass
        instance.save()
        if steps_data is not None:
            # 간단히 전체 재배치
            instance.steps.all().delete()
            for step_data in steps_data:
                item_values_data = step_data.pop('item_values', [])
                step = RecipeStep.objects.create(recipe_profile=instance, **step_data)
                for iv in item_values_data:
                    RecipeItemValue.objects.create(recipe=step, **iv)
        return instance

class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        exclude = ('is_deleted',)

class FacilityHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityHistory
        exclude = ('is_deleted',)

# -----------------------------
# 여기부터 corecode -> agriseed로 이동한 직렬화기들
# -----------------------------

class ControlVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=ControlGroup.objects.all(), required=False, allow_null=True, help_text='속한 ControlGroup ID(선택). 예: 3', style={'example': 3})
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID. 예: 12', style={'example': 12})
    applied_logic = serializers.PrimaryKeyRelatedField(queryset=ControlLogic.objects.all(), help_text='적용할 ControlLogic ID. 예: 2', style={'example': 2})
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(예: ["감시","기록"])',
        style={'example': ['감시', '기록']}
    )

    class Meta:
        model = ControlVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'applied_logic', 'args', 'attributes'
        ]

class ControlGroupSerializer(serializers.ModelSerializer):
    control_variables_in_group = ControlVariableSerializer(
        many=True,
        read_only=False,
        required=False,
        help_text='그룹에 포함된 ControlVariable의 중첩 리스트 (선택)',
        source='agriseed_control_variables_in_group'
    )
    
    class Meta:
        model = ControlGroup
        fields = [
            'id', 'group_id', 'name', 'description', 'control_variables_in_group'
        ]

    def create(self, validated_data):
        control_variables_data = validated_data.pop('agriseed_control_variables_in_group', [])
        group = ControlGroup.objects.create(**validated_data)
        for var_data in control_variables_data:
            ControlVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        control_variables_data = validated_data.pop('agriseed_control_variables_in_group', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        # group_id 업데이트 허용
        if 'group_id' in validated_data:
            instance.group_id = validated_data['group_id']
        instance.save()
        if control_variables_data is not None:
            instance.agriseed_control_variables_in_group.all().delete()
            for var_data in control_variables_data:
                ControlVariable.objects.create(group=instance, **var_data)
        return instance

class CalcVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), required=False, allow_null=True, help_text='소속 CalcGroup ID(선택). 예: 4', style={'example': 4})
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID. 예: 8', style={'example': 8})
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]',
        style={'example': ['감시']}
    )
    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

class CalcGroupSerializer(serializers.ModelSerializer):
    calc_variables_in_group = CalcVariableSerializer(
        many=True,
        read_only=False,
        required=False,
        source='agriseed_calc_variables_in_group'
    )

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'description', 'size_byte', 'calc_variables_in_group'
        ]

    def create(self, validated_data):
        calc_variables_data = validated_data.pop('agriseed_calc_variables_in_group', [])
        group = CalcGroup.objects.create(**validated_data)
        for var_data in calc_variables_data:
            CalcVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        calc_variables_data = validated_data.pop('agriseed_calc_variables_in_group', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        if 'size_byte' in validated_data:
            instance.size_byte = validated_data['size_byte']
        instance.save()
        if calc_variables_data is not None:
            instance.agriseed_calc_variables_in_group.all().delete()
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=instance, **var_data)
        return instance



class ModuleSerializer(serializers.ModelSerializer):
    # agriseed.models.Module 스키마에 맞게 단순화
    # 연결된 DeviceInstance 목록을 읽기전용으로 노출 (SerializerMethodField 사용하여 forward reference 안전 처리)
    deviceInstances = serializers.SerializerMethodField(read_only=True, help_text='모듈에 연결된 DeviceInstance 목록 (읽기전용)')
    class Meta:
        model = Module
        fields = [
            'id', 'name', 'facilitys', 'description', 'order', 'is_enabled', 'created_at', 'updated_at', 'deviceInstances'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_deviceInstances(self, obj):
        """
        모듈에 연결된 DeviceInstance 쿼리셋을 직렬화하여 반환합니다.
        모듈 직렬화기가 DeviceInstanceSerializer보다 먼저 정의될 수 있으므로 globals()를 사용해 런타임에 검색합니다.
        """
        try:
            # ViewSet에서 Prefetch로 'devices'를 미리 가져오면 obj.devices.all()의 캐시를 사용합니다.
            rel = getattr(obj, 'devices', None)
            if rel is not None:
                qs = rel.all()
            else:
                qs = DeviceInstance.objects.filter(module=obj)
            serializer_cls = globals().get('DeviceInstanceSerializer')
            if serializer_cls:
                return serializer_cls(qs, many=True, context=self.context).data
            # DeviceInstanceSerializer가 없으면 PK 목록 반환
            return list(qs.values_list('id', flat=True))
        except Exception:
            return []

# Core MemoryGroup용 간단 직렬화기 추가
class MemoryGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = LSISMemoryGroup
        fields = '__all__'

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
        fields = ['id', 'order', 'item_name', 'description', 'scada_tag_name']

# simple top-level serializer to avoid nested name resolution issues
class ControlItemSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlItem
        fields = ['id', 'item_name', 'description', 'scada_tag_name']
        read_only_fields = fields

class RecipeItemValueSerializer(serializers.ModelSerializer):
    control_item = serializers.PrimaryKeyRelatedField(queryset=ControlItem.objects.all(), help_text='ControlItem ID. 예: 2', style={})
    set_value = serializers.FloatField(help_text='설정 값 (실수). 예: 23.5', style={'example': 23.5})
    min_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최소값 (선택). 예: 10.0', style={'example': 10.0})
    max_value = serializers.FloatField(required=False, allow_null=True, help_text='허용 최대값 (선택). 예: 40.0', style={'example': 40.0})

    class Meta:
        model = RecipeItemValue
        fields = ['id', 'control_item', 'set_value', 'min_value', 'max_value', 'control_logic', 'priority']

class RecipeStepSerializer(serializers.ModelSerializer):
    item_values = RecipeItemValueSerializer(many=True, required=False, help_text='이 스텝에 포함된 항목값 목록 (선택)')
    name = serializers.CharField(help_text='스텥 이름. 예: "발아 단계"', style={'example': '발아 단계'})
    duration_days = serializers.IntegerField(required=False, allow_null=True, help_text='지속 일수 (선택). 예: 7', style={})
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
    comment = serializers.PrimaryKeyRelatedField(queryset=RecipeComment.objects.all(), help_text='댓글 ID', style={})
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
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')
    steps = RecipeStepSerializer(many=True, required=False)
    comments = RecipeCommentSerializer(many=True, read_only=True)
    performances = RecipePerformanceSerializer(many=True, read_only=True)
    ratings = RecipeRatingSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    average_yield = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    createdBy = serializers.SlugRelatedField(source='created_by', slug_field='username', read_only=True, help_text='작성자 username (읽기전용)')
    updatedBy = serializers.SlugRelatedField(source='updated_by', slug_field='username', read_only=True, help_text='최종 수정자 username (읽기전용)')
    class Meta:
        model = RecipeProfile
        fields = [
            'id', 'variety', 'recipe_name', 'description', 'duration_days',
            'order', 'is_active', 'createdAt', 'updatedAt',
            'createdBy', 'updatedBy', 'steps', 'comments', 'performances',
            'ratings', 'average_rating', 'rating_count', 'average_yield', 'success_rate', 'bookmark'
        ]
        read_only_fields = ['createdAt', 'updatedAt', 'createdBy', 'updatedBy']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        # created_by/updated_by fallback from context request if not provided
        req = self.context.get('request') if hasattr(self, 'context') else None
        user = None
        if req and getattr(req, 'user', None) and req.user.is_authenticated:
            user = req.user
        # create profile with creator if available
        if user:
            profile = RecipeProfile.objects.create(created_by=user, updated_by=user, **validated_data)
        else:
            profile = RecipeProfile.objects.create(**validated_data)
        for step_data in steps_data:
            item_values_data = step_data.pop('item_values', [])
            step = RecipeStep.objects.create(recipe_profile=profile, **step_data)
            for iv in item_values_data:
                RecipeItemValue.objects.create(recipe=step, **iv)
        return profile

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        req = self.context.get('request') if hasattr(self, 'context') else None
        user = None
        if req and getattr(req, 'user', None) and req.user.is_authenticated:
            user = req.user
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if user:
            try:
                instance.updated_by = user
            except Exception:
                pass
        instance.save()
        if steps_data is not None:
            # 간단히 전체 재배치
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
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), required=False, allow_null=True, help_text='연결된 Tree ID (선택)', style={})
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
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), allow_null=True, required=False, help_text='연결된 Tree ID (선택)', style={})
    collected_by = serializers.StringRelatedField(read_only=True)
    attachments_files = SpecimenAttachmentSerializer(many=True, read_only=True, help_text='첨부 파일 리스트 (읽기전용)')
    # Specimen의 수확 상태는 Tree_tags에서 동기화되므로 API 기본 동작에서는 읽기 전용으로 노출
    is_post_harvest = serializers.BooleanField(read_only=True, help_text='수확 후 여부 (읽기전용)')

    class Meta:
        model = SpecimenData
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at',)

class SensorItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID (예: 온도). 예: 8', style={})

    class Meta:
        model = SensorItem
        fields = ['id', 'item_name', 'description']


class MeasurementItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID (예: 측정값). 예: 9', style={})

    class Meta:
        model = MeasurementItem
        fields = ['id', 'item_name', 'description']

class VarietyDataThresholdSerializer(serializers.ModelSerializer):
    variety = serializers.PrimaryKeyRelatedField(queryset=Variety.objects.all(), help_text='품종 ID', style={})
    data_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='DataName ID', style={})

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
    facilityId = serializers.PrimaryKeyRelatedField(source='facility', queryset=Facility.objects.all(), allow_null=True, required=False, default=None, help_text='시설 ID (Facility primary key)')
    zoneId = serializers.PrimaryKeyRelatedField(source='zone', queryset=Zone.objects.all(), allow_null=True, required=False, help_text='구역 ID (Zone primary key). 예: 5')
    title = serializers.CharField(required=True, help_text='이벤트 제목. 예: "수확 준비"', style={'example': '수확 준비'})
    description = serializers.CharField(required=False, allow_blank=True, default='', help_text='상세 설명. 예: "수확 관련 미팅 및 준비사항"', style={'example': '수확 관련 미팅 및 준비사항'})
    start = serializers.DateTimeField(required=True, help_text='시작 시간 (ISO 8601, Asia/Seoul +09:00). 예: 2025-09-11T10:00:00+09:00', style={'example': timezone.localtime(timezone.now()).isoformat()})
    end = serializers.DateTimeField(required=True, help_text='종료 시간 (ISO 8601, Asia/Seoul +09:00). 예: 2025-09-11T12:00:00+09:00', style={'example': timezone.localtime(timezone.now()).isoformat()})
    allDay = serializers.BooleanField(source='all_day', required=False, default=False, help_text='종일 여부 (True/False). 예: False', style={'example': False})
    recurrence = serializers.JSONField(allow_null=True, required=False, default=None, help_text='반복 규칙(JSON, 선택).', style={'type':'object'})
    reminders = serializers.JSONField(allow_null=True, required=False, default=None, help_text='알림 설정(JSON 배열, 선택).', style={'type':'array','itemType':'object'})
    attendeeIds = serializers.PrimaryKeyRelatedField(source='attendees', many=True, queryset=User.objects.all(), required=False, default=[], help_text='참석자 사용자 ID 리스트.')
    # createdBy : 외부에는 username으로 노출하고, 입력 시 username을 받아 내부적으로 User FK로 저장합니다.
    createdBy = serializers.SlugRelatedField(source='created_by', slug_field='username', queryset=User.objects.all(), required=False, allow_null=True, help_text='작성자 username (예: "alice"). 값이 주어지지 않으면 요청자의 계정이 사용됩니다.')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')

    class Meta:
        model = CalendarEvent
        # 내부 필드(is_deleted 등)는 노출하지 않음
        fields = ['id', 'facilityId', 'title', 'description', 'start', 'end', 'allDay', 'zoneId', 'recurrence', 'reminders', 'attendeeIds', 'createdBy', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt']

    def create(self, validated_data):
        # attendees는 M2M이므로 인스턴스 생성 후 설정
        attendees = validated_data.pop('attendees', [])
        created_by = validated_data.pop('created_by', None)
        # fallback to request.user when created_by not provided
        if not created_by:
            req = self.context.get('request') if hasattr(self, 'context') else None
            if req and getattr(req, 'user', None) and req.user.is_authenticated:
                created_by = req.user
        event = CalendarEvent.objects.create(created_by=created_by, **validated_data)
        if attendees:
            event.attendees.set(attendees)
        return event

    def update(self, instance, validated_data):
        attendees = validated_data.pop('attendees', None)
        # allow updating created_by if explicitly provided; otherwise keep existing
        created_by = validated_data.pop('created_by', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if created_by is not None:
            try:
                instance.created_by = created_by
            except Exception:
                pass
        instance.save()
        if attendees is not None:
            instance.attendees.set(attendees)
        return instance

class TodoItemSerializer(serializers.ModelSerializer):
    facilityId = serializers.PrimaryKeyRelatedField(
        source='facility', queryset=Facility.objects.all(), allow_null=True, required=False,
        help_text='시설 ID (Facility PK). 예: 12',
        style={'type': 'integer'}
    )
    zoneId = serializers.PrimaryKeyRelatedField(
        source='zone', queryset=Zone.objects.all(), allow_null=True, required=False,
        help_text='구역 ID (Zone PK). 예: 5',
        style={'type': 'integer'}
    )
    title = serializers.CharField(
        help_text='할일 제목. 예: "관수 점검"',
        style={'example': '관수 점검', 'type': 'string'}
    )
    description = serializers.CharField(
        allow_blank=True, required=False,
        help_text='상세 설명(선택). 예: "펌프 점검 및 호스 교체 필요"',
        style={'example': '펌프 점검 및 호스 교체 필요', 'type': 'string'}
    )
    # createdBy : 외부에는 username으로 노출하고, 입력 시 username을 받아 내부적으로 User FK로 저장합니다.
    createdBy = serializers.SlugRelatedField(
        source='created_by', slug_field='username', queryset=User.objects.all(), required=False, allow_null=True,
        help_text='작성자 username (예: "alice"). 값이 주어지지 않으면 요청자의 계정이 사용됩니다.',
        style={'type': 'string'}
    )
    assignedTo = serializers.PrimaryKeyRelatedField(
        source='assigned_to', queryset=User.objects.all(), allow_null=True, required=False,
        help_text='담당자 사용자 ID(선택). 예: 3',
        style={'type': 'integer'}
    )
    dueDate = serializers.DateTimeField(
        source='due_date', allow_null=True, required=False,
        help_text='마감일 (ISO 8601, Asia/Seoul +09:00). 예: 2025-09-15T18:00:00+09:00',
        style={'example': '2025-09-15T18:00:00+09:00', 'type': 'string', 'format': 'date-time'}
    )
    completed = serializers.BooleanField(
        default=False,
        help_text='완료 여부 (True/False).',
        style={'example': False, 'type': 'boolean'}
    )
    completedAt = serializers.DateTimeField(
        source='completed_at', read_only=True,
        help_text='완료 시각 (읽기전용)',
        style={'example': None, 'type': 'string', 'format': 'date-time'}
    )
    priority = serializers.IntegerField(
        default=2,
        help_text='우선순위(정수). 1=높음,2=중간,3=낮음',
        style={'example': 2, 'type': 'integer'}
    )
    status = serializers.CharField(
        default='open',
        help_text='상태 문자열. 예: "open" 또는 "closed"',
        style={'example': 'open', 'type': 'string'}
    )
    reminders = serializers.JSONField(
        allow_null=True, required=False,
        help_text='알림 설정(JSON 배열, 분 단위 오프셋 예: [1440, 60])',
        style={'type': 'array', 'itemType': 'integer', 'example': [1440, 60]}
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='생성 시각 (읽기전용)')
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True, help_text='수정 시각 (읽기전용)')

    class Meta:
        model = TodoItem
        # 내부 필드(is_deleted 등)는 노출하지 않음
        fields = ['id', 'facilityId', 'zoneId', 'title', 'description', 'createdBy', 'assignedTo', 'dueDate', 'completed', 'completedAt', 'priority', 'status', 'reminders', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt', 'completedAt']

    def create(self, validated_data):
        created_by = validated_data.pop('created_by', None)
        if not created_by:
            req = self.context.get('request') if hasattr(self, 'context') else None
            if req and getattr(req, 'user', None) and req.user.is_authenticated:
                created_by = req.user
        todo = TodoItem.objects.create(created_by=created_by, **validated_data)
        return todo

    def update(self, instance, validated_data):
        created_by = validated_data.pop('created_by', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        # do not override created_by unless explicitly provided
        if created_by is not None:
            try:
                instance.created_by = created_by
            except Exception:
                pass
        instance.save()
        return instance
    
class RecipeByZoneSerializer(serializers.ModelSerializer):
    # human-readable names instead of PKs
    facilityName = serializers.SerializerMethodField(read_only=True)
    zoneName = serializers.SerializerMethodField(read_only=True)
    cropName = serializers.SerializerMethodField(read_only=True)
    varietyName = serializers.SerializerMethodField(read_only=True)
    recipeProfileName = serializers.SerializerMethodField(read_only=True)

    # dates (read-only, follow existing naming convention)
    sowingDate = serializers.DateField(source='sowing_date', read_only=True)
    expectedHarvestDate = serializers.DateField(source='expected_harvest_date', read_only=True)

    # elapsed / remaining days computed from dates
    elapsedDays = serializers.SerializerMethodField(read_only=True)
    remainingDays = serializers.SerializerMethodField(read_only=True)

    # nested recipe profile with steps -> item_values -> control_item (all read-only)
    recipeProfile = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CalendarSchedule
        # expose only read-only, name-based and computed fields
        fields = [
            'id',
            'facilityName', 'zoneName', 'cropName', 'varietyName',
            'recipeProfileName', 'sowingDate', 'expectedHarvestDate',
            'elapsedDays', 'remainingDays',
            'recipeProfile'
        ]
        read_only_fields = fields

    # Nested helpers ------------------------------------------------------

    class _RecipeItemValueNestedSerializer(serializers.ModelSerializer):
        # expose control_item's description and scada_tag_name directly on the item_values level
        set_value = serializers.FloatField(read_only=True)
        control_description = serializers.SerializerMethodField(read_only=True)
        control_scada_tag_name = serializers.SerializerMethodField(read_only=True)

        class Meta:
            model = RecipeItemValue
            # intentionally hide RecipeItemValue.id and priority; expose set_value and control fields
            fields = ['set_value', 'control_description', 'control_scada_tag_name']
            read_only_fields = fields

        def get_control_description(self, obj):
            return obj.control_item.description if getattr(obj, 'control_item', None) else None

        def get_control_scada_tag_name(self, obj):
            return obj.control_item.scada_tag_name if getattr(obj, 'control_item', None) else None

    class _RecipeStepNestedSerializer(serializers.ModelSerializer):
        # hide id, order, description as requested
        item_values = serializers.SerializerMethodField(read_only=True)
        cumulative_days = serializers.SerializerMethodField(read_only=True)

        class Meta:
            model = RecipeStep
            fields = ['name', 'duration_days', 'cumulative_days', 'item_values']
            read_only_fields = fields

        def get_item_values(self, step):
            qs = step.item_values.all()
            qs = qs.order_by('priority') if hasattr(qs, 'order_by') else sorted(qs, key=lambda x: (x.priority if x.priority is not None else 0))
            return RecipeByZoneSerializer._RecipeItemValueNestedSerializer(qs, many=True).data

        def get_cumulative_days(self, step):
            # expect that step has an attribute '__cumulative_days' set by owner when computing sequence
            return getattr(step, '__cumulative_days', None)

    class _RecipeProfileNestedSerializer(serializers.ModelSerializer):
        # expose recipe_name as recipeName (camelCase) for API consumers
        recipeName = serializers.CharField(source='recipe_name', read_only=True)
        steps = serializers.SerializerMethodField(read_only=True)

        class Meta:
            model = RecipeProfile
            # use recipeName instead of recipe_name
            fields = ['recipeName', 'duration_days', 'steps']
            read_only_fields = fields

        def get_steps(self, profile):
            # compute cumulative duration for steps and determine current active step using elapsedDays passed via context
            elapsed = self.context.get('elapsedDays') if isinstance(self.context, dict) else None
            steps_qs = list(profile.steps.all())
            # order by 'order' attribute
            try:
                steps_qs = sorted(steps_qs, key=lambda x: (x.order if x.order is not None else 0))
            except Exception:
                pass

            cum = 0
            active_index = None
            for idx, s in enumerate(steps_qs):
                dur = s.duration_days if getattr(s, 'duration_days', None) is not None else 0
                cum += dur
                # annotate step instance with cumulative value for serializer access
                try:
                    setattr(s, '__cumulative_days', cum)
                except Exception:
                    pass
                # determine active step when elapsed is available
                if elapsed is not None and active_index is None:
                    prev_cum = cum - (dur or 0)
                    # if elapsed falls into this step's window -> this is current
                    if elapsed >= prev_cum and elapsed < cum:
                        active_index = idx

            # if elapsed provided and active_index found, return only that step
            if elapsed is not None and active_index is not None and 0 <= active_index < len(steps_qs):
                current = steps_qs[active_index]
                # mark active flag on current step instance if possible
                try:
                    current.active = True
                except Exception:
                    pass
                return RecipeByZoneSerializer._RecipeStepNestedSerializer(current, many=False, context=self.context).data

            # fallback: return all steps
            return RecipeByZoneSerializer._RecipeStepNestedSerializer(steps_qs, many=True, context=self.context).data

    # --------------------------------------------------------------------

    def get_facilityName(self, obj):
        return obj.facility.name if getattr(obj, 'facility', None) else None

    def get_zoneName(self, obj):
        return obj.zone.name if getattr(obj, 'zone', None) else None

    def get_cropName(self, obj):
        return obj.crop.name if getattr(obj, 'crop', None) else None

    def get_varietyName(self, obj):
        return obj.variety.name if getattr(obj, 'variety', None) else None

    def get_recipeProfileName(self, obj):
        return obj.recipe_profile.recipe_name if getattr(obj, 'recipe_profile', None) else None

    def get_elapsedDays(self, obj):
        if not getattr(obj, 'sowing_date', None):
            return None
        now = timezone.localtime(timezone.now()).date()
        sd = obj.sowing_date if isinstance(obj.sowing_date, type(now)) else obj.sowing_date
        try:
            return (now - sd).days
        except Exception:
            return None

    def get_remainingDays(self, obj):
        if not getattr(obj, 'expected_harvest_date', None):
            return None
        now = timezone.localtime(timezone.now()).date()
        ed = obj.expected_harvest_date if isinstance(obj.expected_harvest_date, type(now)) else obj.expected_harvest_date
        try:
            return (ed - now).days
        except Exception:
            return None

    def get_recipeProfile(self, obj):
        profile = getattr(obj, 'recipe_profile', None)
        if not profile:
            return None
        # pass elapsedDays in context so nested serializer can compute current active step
        elapsed = self.get_elapsedDays(obj)
        ctx = {'elapsedDays': elapsed}
        return RecipeByZoneSerializer._RecipeProfileNestedSerializer(profile, context=ctx).data

# corecode.ControlGroup은 현재 변수 중첩이 없고 project_version/group_id 필드도 없음
class ControlGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'description', 'size_byte'
        ]

class CalcVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), required=False, allow_null=True, help_text='소속 CalcGroup ID(선택). 예: 4', style={'example': 4})
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all(), help_text='연결된 DataName ID. 예: 8', style={'example': 8})
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]',
        style={'example': ['감시']}
    )
    # use_method는 models.py의 choices를 따름 (calculation_methods)
    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

class CalcGroupSerializer(serializers.ModelSerializer):
    # corecode.CalcGroup의 related_name은 calc_variables_in_group
    calc_variables_in_group = CalcVariableSerializer(
        many=True,
        read_only=False,
        required=False
    )

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'description', 'size_byte', 'calc_variables_in_group'
        ]

    def create(self, validated_data):
        calc_variables_data = validated_data.pop('calc_variables_in_group', [])
        group = CalcGroup.objects.create(**validated_data)
        for var_data in calc_variables_data:
            CalcVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        calc_variables_data = validated_data.pop('calc_variables_in_group', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.size_byte = validated_data.get('size_byte', instance.size_byte)
        instance.save()
        if calc_variables_data is not None:
            instance.calc_variables_in_group.all().delete()
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=instance, **var_data)
        return instance


class ControlValueSerializer(serializers.ModelSerializer):
    control_user = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ControlValue
        fields = '__all__'

class ControlValueHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlValueHistory
        fields = '__all__'

class LocationCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationCode
        fields = '__all__'

class LocationGroupSerializer(serializers.ModelSerializer):
    codes = LocationCodeSerializer(many=True, required=False)

    class Meta:
        model = LocationGroup
        fields = [
            'group_id', 'group_name', 'description', 'timezone',
            'created_at', 'updated_at', 'codes'
        ]

    def create(self, validated_data):
        codes_data = validated_data.pop('codes', [])
        group = LocationGroup.objects.create(**validated_data)
        for code in codes_data:
            LocationCode.objects.create(group=group, **code)
        return group

    def update(self, instance, validated_data):
        codes_data = validated_data.pop('codes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if codes_data is not None:
            instance.codes.all().delete()
            for code in codes_data:
                LocationCode.objects.create(group=instance, **code)
        return instance

    
class DeviceInstanceSerializer(serializers.ModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=CoreDevice.objects.all(), required=False, allow_null=True, help_text='장비(Device) ID (선택)')
    device_detail = CoreDeviceSerializer(source='device', read_only=True)
    # model의 편의 속성(device_id, facility)을 serializer로 제공
    device_id = serializers.SerializerMethodField(read_only=True, help_text='연결된 코어 장비의 고유 코드(device_code) 또는 시리얼 대체값')
    facilityId = serializers.SerializerMethodField(read_only=True, help_text='연결된 Facility ID (module을 통해 역추적된 첫 번째 Facility)')
    facility_detail = serializers.SerializerMethodField(read_only=True, help_text='연결된 Facility의 직렬화된 상세 정보 (module을 통해 역추적된 첫 번째 Facility)')
    adapter = serializers.PrimaryKeyRelatedField(queryset=CoreAdapter.objects.all(), required=False, allow_null=True, help_text='어댑터(Adapter) ID (선택)')
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), required=False, allow_null=True, help_text='소속 Module ID (선택)')
    # 모델 변경: memory_groups는 이제 FK입니다 (단일 값)
    memory_groups = serializers.PrimaryKeyRelatedField(queryset=LSISMemoryGroup.objects.all(), required=False, allow_null=True, help_text='연결된 MemoryGroup ID(선택)')
    
    class Meta:
        model = DeviceInstance
        fields = [
            'id', 'name', 'device', 'device_detail', 'device_id', 'adapter', 'module', 'facilityId', 'facility_detail',
            'serial_number', 'status', 'last_seen', 'location_within_module', 'install_date', 'is_active',
            'memory_groups','created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'device_detail', 'device_id', 'facilityId', 'facility_detail']

    def get_device_id(self, obj):
        # 우선 연결된 core Device의 device_code, device_id, pk 순으로 반환
        try:
            dev = getattr(obj, 'device', None)
            if dev:
                return getattr(dev, 'device_code', None) or getattr(dev, 'device_id', None) or str(getattr(dev, 'pk', None))
        except Exception:
            pass
        # fallback: DeviceInstance.serial_number
        return getattr(obj, 'serial_number', None)

    def _module_first_facility(self, obj):
        try:
            mod = getattr(obj, 'module', None)
            if not mod:
                return None
            fac_qs = getattr(mod, 'facilities', None)
            if fac_qs is None:
                return None
            return fac_qs.first()
        except Exception:
            return None

    def get_facilityId(self, obj):
        fac = self._module_first_facility(obj)
        return fac.pk if fac is not None else None

    def get_facility_detail(self, obj):
        fac = self._module_first_facility(obj)
        if not fac:
            return None
        return FacilitySerializer(fac, context=self.context).data

    # ModelSerializer가 M2M 필드를 자동 처리하지만, 명시적으로 set 동작을 보장하기 위해 오버라이드(선택)
    def create(self, validated_data):
        # serial_number가 빈 문자열('')로 들어오면 시그널에 의해 자동 생성되도록 제거
        if 'serial_number' in validated_data and (validated_data.get('serial_number') in (None, '') or str(validated_data.get('serial_number')).strip() == ''):
            validated_data.pop('serial_number', None)

        mg = validated_data.pop('memory_groups', None) if 'memory_groups' in validated_data else None
        instance = DeviceInstance.objects.create(memory_groups=mg, **validated_data) if mg is not None else DeviceInstance.objects.create(**validated_data)

        # 동기적으로 serial_number 생성: 인스턴스에 값이 없으면 즉시 생성하여 DB에 반영
        try:
            if not instance.serial_number:
                prefix = generate_serial_prefix_for_deviceinstance(instance)
                generated = f"{prefix}-{instance.id:06d}"
                DeviceInstance.objects.filter(pk=instance.pk, serial_number__isnull=True).update(serial_number=generated)
                instance.refresh_from_db()
        except Exception:
            # 실패해도 시그널에 의해 생성될 수 있으므로 무시
            pass
        return instance

    def update(self, instance, validated_data):
        # serial_number 빈값 처리: 빈 문자열로 덮어쓰지 않도록 제거
        if 'serial_number' in validated_data and (validated_data.get('serial_number') in (None, '') or str(validated_data.get('serial_number')).strip() == ''):
            validated_data.pop('serial_number', None)
        # 변경 전 식별자 저장
        old_device_id = getattr(instance, 'device_id', None)
        old_adapter_id = getattr(getattr(instance, 'adapter', None), 'id', None)
        old_module_id = getattr(getattr(instance, 'module', None), 'id', None)

        mg = validated_data.pop('memory_groups', None) if 'memory_groups' in validated_data else None
        # allow client to force regeneration with regenerate_serial flag (internal use)
        force_regen = bool(validated_data.pop('regenerate_serial', False))

        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if mg is not None:
            instance.memory_groups = mg
        instance.save()

        # 변경 후 식별자
        new_device_id = getattr(instance, 'device_id', None)
        new_adapter_id = getattr(getattr(instance, 'adapter', None), 'id', None)
        new_module_id = getattr(getattr(instance, 'module', None), 'id', None)

        try:
            # 필요시 serial 생성/재생성 판단
            need_regen = False
            # 빈 값이면 생성
            if not instance.serial_number:
                need_regen = True
            # 강제 재생성 요청이 있으면 생성
            if force_regen:
                need_regen = True
            # device/adapter/module 변경으로 접두사가 달라질 가능성이 있으면 접두사 비교
            if not need_regen and (old_device_id != new_device_id or old_adapter_id != new_adapter_id or old_module_id != new_module_id):
                new_prefix = generate_serial_prefix_for_deviceinstance(instance)
                cur_sn = getattr(instance, 'serial_number', '') or ''
                cur_prefix = cur_sn.split('-')[0] if '-' in cur_sn else cur_sn
                if cur_prefix.upper() != (new_prefix or '').upper():
                    need_regen = True

            if need_regen:
                prefix = generate_serial_prefix_for_deviceinstance(instance)
                generated = f"{prefix}-{instance.id:06d}"
                DeviceInstance.objects.filter(pk=instance.pk).update(serial_number=generated)
                instance.refresh_from_db()
        except Exception:
            # 실패해도 무시(기존 시그널로 대체될 수 있음)
            pass
        return instance
