from rest_framework import serializers
from .models import Device, Activity, ControlHistory, ControlRole, Issue, ResolvedIssue, Schedule, Facility, Zone, SensorData, ControlSettings, FacilityHistory, Crop, Variety, VarietyImage, VarietyGuide, RecipeProfile, ControlItem, RecipeItemValue, RecipeStep, RecipeComment, RecipeCommentVote, RecipePerformance, RecipeRating, Tree, Tree_tags, TreeImage, SpecimenData, SpecimenAttachment, SensorItem, MeasurementItem, VarietyDataThreshold, QualityEvent
from corecode.models import DataName

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
    class Meta:
        model = Zone
        exclude = ('is_deleted',)

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
    class Meta:
        model = RecipeItemValue
        fields = ['id', 'control_item', 'set_value', 'min_value', 'max_value', 'control_logic', 'priority']

class RecipeStepSerializer(serializers.ModelSerializer):
    item_values = RecipeItemValueSerializer(many=True, required=False)
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
    recipe = serializers.PrimaryKeyRelatedField(queryset=RecipeProfile.objects.all())
    class Meta:
        model = RecipePerformance
        fields = ['id', 'recipe', 'user', 'yield_amount', 'success', 'notes', 'created_at']

class RecipeRatingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    recipe = serializers.PrimaryKeyRelatedField(queryset=RecipeProfile.objects.all())
    class Meta:
        model = RecipeRating
        fields = ['id', 'recipe', 'user', 'rating', 'created_at']

class RecipeCommentVoteSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    comment = serializers.PrimaryKeyRelatedField(queryset=RecipeComment.objects.all())
    class Meta:
        model = RecipeCommentVote
        fields = ['id', 'comment', 'user', 'is_helpful', 'created_at']

class RecipeCommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    replies = serializers.SerializerMethodField()
    helpful_count = serializers.IntegerField(read_only=True)
    unhelpful_count = serializers.IntegerField(read_only=True)
    votes = RecipeCommentVoteSerializer(many=True, read_only=True)

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
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), required=False, allow_null=True)
    # 단일 boolean 필드로 수확 상태를 관리 (True=수확후)
    is_post_harvest = serializers.BooleanField(required=False, default=False)
    has_farm_log = serializers.BooleanField(required=False, default=False)

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
    tree = serializers.PrimaryKeyRelatedField(queryset=Tree.objects.all(), allow_null=True, required=False)
    collected_by = serializers.StringRelatedField(read_only=True)
    attachments_files = SpecimenAttachmentSerializer(many=True, read_only=True)
    # Specimen의 수확 상태는 Tree_tags에서 동기화되므로 API 기본 동작에서는 읽기 전용으로 노출
    is_post_harvest = serializers.BooleanField(read_only=True)

    class Meta:
        model = SpecimenData
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at',)

class SensorItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())

    class Meta:
        model = SensorItem
        fields = ['id', 'item_name', 'description']


class MeasurementItemSerializer(serializers.ModelSerializer):
    item_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())

    class Meta:
        model = MeasurementItem
        fields = ['id', 'item_name', 'description']

class VarietyDataThresholdSerializer(serializers.ModelSerializer):
    variety = serializers.PrimaryKeyRelatedField(queryset=Variety.objects.all())
    data_name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())

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
