from rest_framework import serializers
from .models import Project, ProjectVersion, MemoryGroup, Variable

class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    group = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address'
        ]

    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        return f"%{obj.device}{unit_symbol}{int(obj.address)}"

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False)
    project_version = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'project_version', 'group_id', 'start_device', 'start_address', 'size_byte', 'variables'
        ]

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = MemoryGroup.objects.create(**validated_data)
        for var_data in variables_data:
            Variable.objects.create(group=group, **var_data)
        return group

class ProjectVersionSerializer(serializers.ModelSerializer):
    groups = MemoryGroupSerializer(many=True, read_only=False)

    class Meta:
        model = ProjectVersion
        fields = [
            'id', 'project', 'version', 'created_at', 'updated_at', 'note', 'groups'
        ]

    def create(self, validated_data):
        groups_data = validated_data.pop('groups', [])
        version = ProjectVersion.objects.create(**validated_data)
        for group_data in groups_data:
            variables_data = group_data.pop('variables', [])
            group = MemoryGroup.objects.create(project_version=version, **group_data)
            for var_data in variables_data:
                Variable.objects.create(group=group, **var_data)
        return version

class ProjectSerializer(serializers.ModelSerializer):
    versions = ProjectVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'created_at', 'updated_at', 'versions'
        ]

    def validate_name(self, value):
        if self.instance is None and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("같은 이름의 프로젝트가 이미 존재합니다.")
        return value