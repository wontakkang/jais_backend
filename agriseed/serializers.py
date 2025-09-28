from rest_framework import serializers
from .models import *
from corecode.models import DataName, CalcGroup, ControlLogic, LocationGroup as CoreLocationGroup
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# corecode 별칭 재사용 로직 제거 (역참조 유발 방지)
# 기존: corecode.serializers에서 직렬화기를 재노출하던 블록 삭제

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
    control_settings = ControlSettingsSerializer(many=True)
    zones = ZoneSerializer(many=True, read_only=True)
    calendar_schedules = CalendarScheduleSerializer(many=True, read_only=True)
    class Meta:
        model = Facility
        # include model DB fields except internal 'is_deleted', and also include declared nested serializer fields
        fields = [f.name for f in model._meta.fields if f.name != 'is_deleted'] + ['control_settings', 'zones', 'calendar_schedules']

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
    # Project 필드는 사용 안함. facility/location_group만 노출
    location_group = serializers.PrimaryKeyRelatedField(queryset=CoreLocationGroup.objects.all(), required=False, allow_null=True, help_text='LocationGroup ID (선택)')

    class Meta:
        model = Module
        fields = [
            'id', 'name', 'module_type', 'description', 'facility', 'location_group', 'control_scope', 'settings', 'order', 'is_enabled', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DeviceInstanceSerializer(serializers.ModelSerializer):
    from corecode.serializers import DeviceSerializer as CoreDeviceSerializer  # 안전한 단방향 참조
    catalog = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True, help_text='장비 카탈로그(Device) ID (선택)')
    catalog_detail = CoreDeviceSerializer(source='catalog', read_only=True)
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), required=False, allow_null=True, help_text='소속 Module ID (선택)')

    class Meta:
        model = DeviceInstance
        fields = [
            'id', 'name', 'catalog', 'catalog_detail', 'module', 'serial_number', 'hw_version', 'fw_version', 'device_id', 'mac_address',
            'status', 'last_seen', 'configuration', 'health', 'location_within_module', 'install_date', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'catalog_detail']

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
