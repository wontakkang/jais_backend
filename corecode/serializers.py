from rest_framework import serializers
from .models import Project, ProjectVersion, MemoryGroup, Variable

class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Variable
        fields = [
            'id', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address'
        ]

    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        return f"%{obj.device}{unit_symbol}{int(obj.address)}"

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'project_version', 'group_id', 'start_device', 'start_address', 'size_byte', 'variables'
        ]

class ProjectVersionSerializer(serializers.ModelSerializer):
    groups = MemoryGroupSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectVersion
        fields = [
            'id', 'project', 'version', 'created_at', 'note', 'groups'
        ]

class ProjectSerializer(serializers.ModelSerializer):
    versions = ProjectVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'created_at', 'updated_at', 'versions'
        ]
