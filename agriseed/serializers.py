from rest_framework import serializers
from .models import Device, Activity, ControlHistory, ControlRole, Issue, ResolvedIssue, Schedule, Facility, Zone, SensorData, ControlSettings, FacilityHistory, Crop, Variety, VarietyImage, VarietyGuide, RecipeProfile, ControlItem, RecipeItemValue

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
        fields = [
            'id', 'recipe', 'control_item', 'set_value',
            'min_value', 'max_value', 'control_logic', 'priority'
        ]
        
class RecipeProfileSerializer(serializers.ModelSerializer):
    item_values = RecipeItemValueSerializer(many=True, required=False)

    class Meta:
        model = RecipeProfile
        fields = ['id', 'crop', 'recipe_name', 'created_at', 'item_values']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        item_values_data = validated_data.pop('item_values', [])
        profile = RecipeProfile.objects.create(**validated_data)
        for iv in item_values_data:
            RecipeItemValue.objects.create(recipe=profile, **iv)
        return profile

    def update(self, instance, validated_data):
        item_values_data = validated_data.pop('item_values', None)
        instance.recipe_name = validated_data.get('recipe_name', instance.recipe_name)
        instance.save()
        if item_values_data is not None:
            instance.item_values.all().delete()
            for iv in item_values_data:
                RecipeItemValue.objects.create(recipe=instance, **iv)
        return instance