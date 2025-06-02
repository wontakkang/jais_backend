from rest_framework import serializers
from .models import *
from utils.control import __all__ as control_methods_list # ControlLogic use_method choices


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

class ControlLogicSerializer(serializers.ModelSerializer):
    use_method = serializers.ChoiceField(choices=[(method, method) for method in control_methods_list])
    class Meta:
        model = ControlLogic
        fields = [
            'id', 'name', 'use_method', 'method_description', 
            'method_args_desc', 'method_result', 'method_args_type', 'method_result_type'
        ]

class ControlVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=ControlGroup.objects.all(), required=False, allow_null=True)
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())
    applied_logic = serializers.PrimaryKeyRelatedField(queryset=ControlLogic.objects.all())
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list
    )

    class Meta:
        model = ControlVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'applied_logic', 'args', 'attributes'
        ]

    # create, update 메서드는 기본 동작으로 충분할 수 있으나, 필요시 오버라이드

class ControlGroupSerializer(serializers.ModelSerializer):
    control_variables_in_group = ControlVariableSerializer(many=True, read_only=False, required=False)
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all())
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'description', 'control_variables_in_group'
        ]

    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

    def create(self, validated_data):
        control_variables_data = validated_data.pop('control_variables_in_group', [])
        group = ControlGroup.objects.create(**validated_data)
        for var_data in control_variables_data:
            ControlVariable.objects.create(group=group, **var_data)
        return group
    
    def update(self, instance, validated_data):
        control_variables_data = validated_data.pop('control_variables_in_group', None)
        
        # 기본 필드 업데이트
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        # project_version, group_id 등은 일반적으로 수정하지 않거나 특정 로직 필요
        instance.save()

        if control_variables_data is not None:
            # 기존 변수 삭제 후 새로 생성 (간단한 방식) 또는 개별 업데이트/삭제/생성 로직 구현
            instance.control_variables_in_group.all().delete()
            for var_data in control_variables_data:
                ControlVariable.objects.create(group=instance, **var_data)
        return instance

class CalcVariableSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=CalcGroup.objects.all(), required=False, allow_null=True)
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보']),
        allow_empty=True,
        required=False,
        default=list
    )
    # use_method는 models.py의 choices를 따름 (calculation_methods)
    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'data_type', 'use_method', 'args', 'attributes'
        ]

class CalcGroupSerializer(serializers.ModelSerializer):
    calc_variables_in_group = CalcVariableSerializer(many=True, read_only=False, required=False) # related_name 변경 반영
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all())
    project_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'project_version', 'project_id', 'group_id', 'description', 'calc_variables_in_group'
        ]
    def get_project_id(self, obj):
        return obj.project_version.project.id if obj.project_version and obj.project_version.project else None

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
        instance.save()
        if calc_variables_data is not None:
            instance.calc_variables_in_group.all().delete()
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=instance, **var_data)
        return instance

class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    group = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), required=False, allow_null=True)
    name = serializers.PrimaryKeyRelatedField(queryset=DataName.objects.all())
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

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False, required=False)
    project_version = serializers.PrimaryKeyRelatedField(queryset=ProjectVersion.objects.all())
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

    def update(self, instance, validated_data):
        variables_data = validated_data.pop('variables', None)
        instance.name = validated_data.get('name', instance.name)
        # ... other fields ...
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                Variable.objects.create(group=instance, **var_data)
        return instance

class ProjectVersionSerializer(serializers.ModelSerializer):
    groups = MemoryGroupSerializer(many=True, read_only=False, required=False)
    calc_groups = CalcGroupSerializer(many=True, read_only=False, required=False)
    control_groups = ControlGroupSerializer(many=True, read_only=False, required=False)

    class Meta:
        model = ProjectVersion
        fields = [
            'id', 'project', 'version', 'created_at', 'updated_at', 'note', 
            'groups', 'calc_groups', 'control_groups'
        ]

    def create(self, validated_data):
        groups_data = validated_data.pop('groups', [])
        calc_groups_data = validated_data.pop('calc_groups', [])
        control_groups_data = validated_data.pop('control_groups', [])
        
        project_version = ProjectVersion.objects.create(**validated_data)
        
        for group_data in groups_data:
            variables_data = group_data.pop('variables', [])
            memory_group = MemoryGroup.objects.create(project_version=project_version, **group_data)
            for var_data in variables_data:
                Variable.objects.create(group=memory_group, **var_data)
                
        for group_data in calc_groups_data:
            calc_variables_data = group_data.pop('calc_variables_in_group', [])
            calc_group = CalcGroup.objects.create(project_version=project_version, **group_data)
            for var_data in calc_variables_data:
                CalcVariable.objects.create(group=calc_group, **var_data)

        for group_data in control_groups_data:
            control_variables_data = group_data.pop('control_variables_in_group', [])
            control_group = ControlGroup.objects.create(project_version=project_version, **group_data)
            for var_data in control_variables_data:
                ControlVariable.objects.create(group=control_group, **var_data)
                
        return project_version

class ProjectSerializer(serializers.ModelSerializer):
    versions = ProjectVersionSerializer(many=True, read_only=True)
    # device 필드는 ForeignKey이므로, 필요시 DeviceSerializer 등으로 표현 가능
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Project
        fields = [
            'id', 'name' ,'device', 'description', 'created_at', 'updated_at', 'versions'
        ]

    def validate_name(self, value):
        # 인스턴스가 존재하고 (업데이트 시) 이름이 변경되지 않았으면 유효성 검사 통과
        if self.instance and self.instance.name == value:
            return value
        # 새 프로젝트 생성 시 또는 이름 변경 시 중복 검사
        if Project.objects.filter(name=value).exists():
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
    manufacturer_id = serializers.PrimaryKeyRelatedField(queryset=DeviceCompany.objects.all(), source='manufacturer', write_only=True, allow_null=True, required=False)
    user_manuals = UserManualSerializer(many=True, read_only=True)
    user_manual_ids = serializers.PrimaryKeyRelatedField(queryset=UserManual.objects.all(), source='user_manuals', many=True, write_only=True, required=False)

    class Meta:
        model = Device
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
