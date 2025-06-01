from rest_framework import serializers
from .models import *
from utils.calculation import all_dict


class ControlLogicSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=ControlGroup.objects.all(), required=False)
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list
    )

    class Meta:
        model = ControlLogic
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

    def create(self, validated_data):
        attributes = validated_data.pop('attributes', [])
        instance = ControlLogic.objects.create(**validated_data)
        instance.attributes = attributes
        instance.save()
        return instance

    def update(self, instance, validated_data):
        attributes = validated_data.pop('attributes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if attributes is not None:
            instance.attributes = attributes
        instance.save()
        return instance

class ControlGroupSerializer(serializers.ModelSerializer):
    logics = ControlLogicSerializer(many=True, read_only=False, required=False)
    project_version = serializers.PrimaryKeyRelatedField(read_only=True)
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'description', 'logics'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        logics_data = validated_data.pop('logics', [])
        group = ControlGroup.objects.create(**validated_data)
        for logic_data in logics_data:
            ControlLogic.objects.create(group=group, **logic_data)
        return group

class CalcVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), required=False)
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list
    )

    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

    def create(self, validated_data):
        attributes = validated_data.pop('attributes', [])
        instance = CalcVariable.objects.create(**validated_data)
        instance.attributes = attributes
        instance.save()
        return instance

    def update(self, instance, validated_data):
        attributes = validated_data.pop('attributes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if attributes is not None:
            instance.attributes = attributes
        instance.save()
        return instance

class CalcGroupSerializer(serializers.ModelSerializer):
    variables = CalcVariableSerializer(many=True, read_only=False, required=False)
    project_version = serializers.PrimaryKeyRelatedField(read_only=True)
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'variables'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = CalcGroup.objects.create(**validated_data)
        for var_data in variables_data:
            CalcVariable.objects.create(group=group, **var_data)
        return group
        
class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    group = serializers.PrimaryKeyRelatedField(read_only=True)
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list
    )

    class Meta:
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes'
        ]

    def get_device_address(self, obj):
        unit_map = {'bit': 'X', 'byte': 'B', 'word': 'W', 'dword': 'D'}
        unit_symbol = unit_map.get(obj.unit, '')
        return f"%{obj.device}{unit_symbol}{int(obj.address)}"

    def create(self, validated_data):
        attributes = validated_data.pop('attributes', [])
        instance = Variable.objects.create(**validated_data)
        instance.attributes = attributes
        instance.save()
        return instance

    def update(self, instance, validated_data):
        attributes = validated_data.pop('attributes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if attributes is not None:
            instance.attributes = attributes
        instance.save()
        return instance
    
class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False)
    project_version = serializers.PrimaryKeyRelatedField(read_only=True)
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'start_device', 'start_address', 'size_byte', 'variables'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = MemoryGroup.objects.create(**validated_data)
        for var_data in variables_data:
            Variable.objects.create(group=group, **var_data)
        return group

class ProjectVersionSerializer(serializers.ModelSerializer):
    groups = MemoryGroupSerializer(many=True, read_only=False)
    calc_groups = CalcGroupSerializer(many=True, read_only=True)
    control_groups = ControlGroupSerializer(many=True, read_only=True) # 추가

    class Meta:
        model = ProjectVersion
        fields = [
            'id', 'project', 'version', 'created_at', 'updated_at', 'note', 'groups', 'calc_groups', 'control_groups' # control_groups 추가
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
            'id', 'name' ,'device', 'description', 'created_at', 'updated_at', 'versions'
        ]

    def validate_name(self, value):
        if self.instance is None and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("같은 이름의 프로젝트가 이미 존재합니다.")
        return value

class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['id', 'user', 'preferences']
        read_only_fields = ['id', 'user']

class DeviceCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCompany
        fields = '__all__'

class UserManualSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserManual
        fields = '__all__'

class DeviceSerializer(serializers.ModelSerializer):
    manufacturer = DeviceCompanySerializer(read_only=True)
    manufacturer_id = serializers.PrimaryKeyRelatedField(queryset=DeviceCompany.objects.all(), source='manufacturer', write_only=True)
    user_manuals = UserManualSerializer(many=True, read_only=True)
    user_manual_ids = serializers.PrimaryKeyRelatedField(queryset=UserManual.objects.all(), source='user_manuals', many=True, write_only=True)

    class Meta:
        model = Device
        fields = '__all__'
        # fields를 명시적으로 나열하려면 아래처럼 작성
        # fields = [ ...기존 필드..., 'manufacturer', 'manufacturer_id', 'user_manuals', 'user_manual_ids', ... ]

    def create(self, validated_data):
        user_manuals = validated_data.pop('user_manuals', [])
        instance = Device.objects.create(**validated_data)
        if user_manuals:
            instance.user_manuals.set(user_manuals)
        return instance

    def update(self, instance, validated_data):
        user_manuals = validated_data.pop('user_manuals', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if user_manuals is not None:
            instance.user_manuals.set(user_manuals)
        return instance

class DataNameSerializer(serializers.ModelSerializer):
    use_method = serializers.ChoiceField(
        choices=[(k, k) for k in all_dict.keys()],
        required=False,
        allow_blank=True,
        allow_null=True
    )
    class Meta:
        model = DataName
        fields = '__all__'

class ControlValueSerializer(serializers.ModelSerializer):
    control_user = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ControlValue
        fields = '__all__'

class ControlValueHistorySerializer(serializers.ModelSerializer):
    control_value = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = ControlValueHistory
        fields = '__all__'
