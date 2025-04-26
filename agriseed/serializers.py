from rest_framework import serializers
from .models import Device, Activity, ControlHistory, ControlRole, Issue, ResolvedIssue, Schedule, Facility, Zone, SensorData, ControlSettings, FacilityHistory

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = '__all__'

class ControlHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlHistory
        fields = '__all__'

class ControlRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlRole
        fields = '__all__'

class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = '__all__'

class ResolvedIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResolvedIssue
        fields = '__all__'

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'

class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'

class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = '__all__'

class ControlSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlSettings
        fields = '__all__'

class FacilityHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityHistory
        fields = '__all__'