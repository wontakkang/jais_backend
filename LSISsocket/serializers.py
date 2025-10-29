from rest_framework import serializers
from .models import *
# 코어 모델 참조 (MemoryGroup/Variable/DataName/ProjectVersion/Device)
from corecode.models import DataName as CoreDataName, Device as CoreDevice, Adapter as CoreAdapter, ControlLogic as CoreControlLogic
from corecode.serializers import DataNameSerializer
from django.db import transaction
from rest_framework.exceptions import ValidationError

class SocketClientStatusSerializer(serializers.ModelSerializer):
    config = serializers.PrimaryKeyRelatedField(queryset=SocketClientConfig.objects.all())
    # 추가: 연결된 설정의 이름
    configName = serializers.CharField(source='config.name', read_only=True)
    class Meta:
        model = SocketClientStatus
        fields = '__all__'
    
class SocketClientConfigSerializer(serializers.ModelSerializer):
    detailedStatus = serializers.SerializerMethodField()
    # ManyToMany fields: accept list of PKs for write, and provide detailed nested list for read
    control_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=ControlGroup.objects.all(), required=False, allow_empty=True, help_text='연결된 ControlGroup IDs')
    control_groups_detail = serializers.SerializerMethodField()
    calc_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=CalcGroup.objects.all(), required=False, allow_empty=True, help_text='연결된 CalcGroup IDs')
    calc_groups_detail = serializers.SerializerMethodField()
    memory_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=MemoryGroup.objects.all(), required=False, allow_empty=True, help_text='연결된 MemoryGroup IDs')
    memory_groups_detail = serializers.SerializerMethodField()
    class Meta:
        model = SocketClientConfig
        exclude = ('is_deleted',)
        read_only_fields = ['id']

    def get_detailedStatus(self, obj):
        status = obj.status_logs.order_by('-updated_at').first()
        if status:
            return SocketClientStatusSerializer(status).data
        return None

    def get_control_groups_detail(self, obj):
        try:
            qs = obj.control_groups.all()
            if not qs.exists():
                qs = ControlGroup.objects.all()
            return ControlGroupSerializer(qs, many=True).data
        except Exception:
            return []

    def get_calc_groups_detail(self, obj):
        try:
            qs = obj.calc_groups.all()
            if not qs.exists():
                qs = CalcGroup.objects.all()
            return CalcGroupSerializer(qs, many=True).data
        except Exception:
            return []

    def get_memory_groups_detail(self, obj):
        try:
            return MemoryGroupSerializer(obj.memory_groups.all(), many=True).data
        except Exception:
            return []

    def create(self, validated_data):
        # Extract ManyToMany inputs before instance creation
        control_groups = validated_data.pop('control_groups', [])
        calc_groups = validated_data.pop('calc_groups', [])
        memory_groups = validated_data.pop('memory_groups', [])

        # ✅ force_insert 방지 → 명시적 save()
        instance = SocketClientConfig(**validated_data)
        instance.save()

        # assign M2M relations if provided
        try:
            if control_groups:
                instance.control_groups.set(control_groups)
        except Exception:
            pass
        try:
            if calc_groups:
                instance.calc_groups.set(calc_groups)
        except Exception:
            pass
        try:
            if memory_groups:
                instance.memory_groups.set(memory_groups)
        except Exception:
            pass

        # SocketClientStatus 생성
        SocketClientStatus.objects.create(config=instance)

        return instance

    def update(self, instance, validated_data):
        # handle ManyToMany updates explicitly
        control_groups = validated_data.pop('control_groups', None)
        calc_groups = validated_data.pop('calc_groups', None)
        memory_groups = validated_data.pop('memory_groups', None)

        # update scalar fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        try:
            if control_groups is not None:
                instance.control_groups.set(control_groups)
        except Exception:
            pass
        try:
            if calc_groups is not None:
                instance.calc_groups.set(calc_groups)
        except Exception:
            pass
        try:
            if memory_groups is not None:
                instance.memory_groups.set(memory_groups)
        except Exception:
            pass

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if not instance.calc_groups.exists():
                data['calc_groups'] = list(CalcGroup.objects.values_list('id', flat=True))
        except Exception:
            pass
        try:
            if not instance.control_groups.exists():
                data['control_groups'] = list(ControlGroup.objects.values_list('id', flat=True))
        except Exception:
            pass
        return data
    
        
class SocketClientLogSerializer(serializers.ModelSerializer):
    config = serializers.PrimaryKeyRelatedField(queryset=SocketClientConfig.objects.all())
    # 추가: 연결된 설정의 이름
    configName = serializers.CharField(source='config.name', read_only=True)
    class Meta:
        model = SocketClientLog
        exclude = ('is_deleted',)

class SocketClientCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocketClientCommand
        exclude = ('is_deleted',)

# -----------------------------
# MemoryGroup/Variable 직렬화기 (코어 모델 참조)
# -----------------------------
class VariableSerializer(serializers.ModelSerializer):
    device_address = serializers.SerializerMethodField(read_only=True)
    # 그룹 기준 주소 사용 여부 노출
    use_group_base_address = serializers.BooleanField(required=False, default=False, help_text='True이면 변수 주소가 그룹의 start_address를 기준으로 해석됩니다.')
    group = serializers.PrimaryKeyRelatedField(queryset=MemoryGroup.objects.all(), required=False, allow_null=True, help_text='소속 MemoryGroup ID(선택)')
    name = serializers.PrimaryKeyRelatedField(queryset=CoreDataName.objects.all(), help_text='연결된 DataName ID')
    attributes = serializers.ListField(
        child=serializers.ChoiceField(choices=['감시','제어','기록','경보', '연산', '설정']),
        allow_empty=True,
        required=False,
        default=list,
        help_text='변수 속성 목록(선택). 예: ["감시"]'
    )
    remark = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text='비고')
    # 모델과 동일한 타입으로 정정
    device = serializers.CharField(max_length=2, help_text='장치 종류 코드(예: D/M/R)')
    address = serializers.FloatField(help_text='장치 내 주소(숫자). 예: 100')

    class Meta:
        model = Variable
        fields = [
            'id', 'group', 'name', 'device', 'address', 'use_group_base_address', 'data_type', 'unit', 'scale', 'offset', 'device_address', 'attributes', 'remark'
        ]
        
    def get_device_address(self, obj):
        unit_map = {
            'bit': ('X', 16),
            'byte': ('B', 2),
            'word': ('W', 1),
            'dword': ('D', 0.5),
        }
        unit_key = (obj.unit or '').lower()
        unit_symbol, multiplier = unit_map.get(unit_key, ('', 1))

        try:
            if obj.offset is not None:
                if '.' not in obj.offset:
                    obj.offset = f"{obj.offset}.0"
                offset_val = int(obj.offset.split('.')[0]) * multiplier
                offset_val += int(obj.offset.split('.')[1])
            else:
                offset_val = 0.0
        except Exception:
            offset_val = 0.0
        # 그룹 기준 주소 사용이면 그룹의 start_address를 더해서 실제 주소 계산
        base = 0.0
        try:
            if getattr(obj, 'use_group_base_address', False) and getattr(obj, 'group', None) is not None:
                base = float(getattr(obj.group, 'start_address', 0) or 0)
        except Exception:
            base = 0.0

        physical_addr = float(obj.address or 0) + base
        addr_int = int(physical_addr * multiplier) + offset_val
        if unit_key != 'bit':
            addr_int = int(addr_int)
        return f"%{obj.device}{unit_symbol}{addr_int}"

class MemoryGroupSerializer(serializers.ModelSerializer):
    variables = VariableSerializer(many=True, read_only=False, required=False, help_text='이 그룹에 포함된 변수 목록 (선택)')
    # 추가: Adapter/Device FK 노출 (모델 필드는 대문자이므로 source로 매핑)
    adapter = serializers.PrimaryKeyRelatedField(queryset=CoreAdapter.objects.all(), required=False, allow_null=True, source='Adapter', help_text='연결 어댑터 ID(선택)')
    device = serializers.PrimaryKeyRelatedField(queryset=CoreDevice.objects.all(), required=False, allow_null=True, source='Device', help_text='연결 장치 ID(선택)')
    # 추가: 이름 필드 노출
    adapterName = serializers.CharField(source='Adapter.name', read_only=True)
    deviceName = serializers.CharField(source='Device.name', read_only=True)

    class Meta:
        model = MemoryGroup
        fields = [
            'id', 'name', 'description', 'size_byte', 'start_address', 'adapter', 'adapterName', 'device', 'deviceName', 'variables'
        ]

    def _resolve_dataname(self, name_val):
        # name_val은 PK(int) 또는 객체일 수 있음
        if name_val is None:
            return None
        if isinstance(name_val, CoreDataName):
            return name_val
        try:
            return CoreDataName.objects.get(pk=name_val)
        except Exception:
            raise serializers.ValidationError({ 'name': f"DataName (id={name_val})을(를) 찾을 수 없습니다." })

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        group = MemoryGroup.objects.create(**validated_data)

        # 1) 명시 변수가 오면 그대로 생성
        if variables_data:
            for var_data in variables_data:
                name_val = var_data.get('name')
                name_obj = self._resolve_dataname(name_val)
                Variable.objects.create(
                    group=group,
                    name=name_obj,
                    device=var_data.get('device'),
                    address=var_data.get('address'),
                    use_group_base_address=var_data.get('use_group_base_address', False),
                    data_type=var_data.get('data_type'),
                    unit=var_data.get('unit'),
                    scale=var_data.get('scale', 1),
                    offset=var_data.get('offset', '0'),
                    attributes=var_data.get('attributes', []),
                    remark=var_data.get('remark')
                )
            return group


    def update(self, instance, validated_data):
        variables_data = validated_data.pop('variables', None)
        # 기본 필드 업데이트
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                name_val = var_data.get('name')
                name_obj = self._resolve_dataname(name_val)
                Variable.objects.create(
                    group=instance,
                    name=name_obj,
                    device=var_data.get('device'),
                    address=var_data.get('address'),
                    use_group_base_address=var_data.get('use_group_base_address', False),
                    data_type=var_data.get('data_type'),
                    unit=var_data.get('unit'),
                    scale=var_data.get('scale', 1),
                    offset=var_data.get('offset', '0'),
                    attributes=var_data.get('attributes', []),
                    remark=var_data.get('remark')
                )
        return instance



class ControlHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlValueHistory
        exclude = ('is_deleted',)
        
class ControlVariableSerializer(serializers.ModelSerializer):
    # ControlVariable은 name을 가지지 않음. 제어 로직과 결과 변수만 가짐.
    applied_logic = serializers.PrimaryKeyRelatedField(queryset=CoreControlLogic.objects.all(), required=True, help_text='연결된 ControlLogic ID')
    # 읽기 편의를 위한 로직 이름 노출(선택)
    applied_logic_name = serializers.CharField(source='applied_logic.name', read_only=True)
    result = serializers.PrimaryKeyRelatedField(queryset=Variable.objects.all(), required=False, allow_null=True, help_text='제어 결과가 기록될 Variable ID')

    class Meta:
        model = ControlVariable
        fields = [
            'id', 'group', 'applied_logic', 'applied_logic_name', 'data_type', 'args', 'result'
        ]

    def to_internal_value(self, data):
        # applied_logic가 중첩 객체 {id:...} 형태로 들어오는 경우 허용
        if isinstance(data, dict) and 'applied_logic' in data and isinstance(data.get('applied_logic'), dict) and 'id' in data.get('applied_logic'):
            data = dict(data)
            data['applied_logic'] = data['applied_logic']['id']
        # result도 중첩 객체 {id:...} 허용
        if isinstance(data, dict) and 'result' in data and isinstance(data.get('result'), dict) and 'id' in data.get('result'):
            data = dict(data)
            data['result'] = data['result']['id']
        return super().to_internal_value(data)

class ControlGroupSerializer(serializers.ModelSerializer):
    # expose nested variables under 'variables' and map to model related_name
    variables = ControlVariableSerializer(
        many=True,
        read_only=False,
        required=False,
        source='lsissocket_control_variables_in_group',
        help_text='그룹에 포함된 ControlVariable의 중첩 리스트 (선택)'
    )
    
    class Meta:
        model = ControlGroup
        fields = [
            'id', 'name', 'description', 'variables'
        ]

    def create(self, validated_data):
        # Accept nested variables under several keys for backward compatibility
        control_variables_data = []
        for key in ('variables', 'control_variables_in_group', 'lsissocket_control_variables_in_group'):
            if key in validated_data:
                control_variables_data = validated_data.pop(key)
                break

        allowed = {f.name for f in ControlGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        create_kwargs = {k: v for k, v in validated_data.items() if k in allowed}

        with transaction.atomic():
            # applied_logic 존재 검증
            for var_data in control_variables_data:
                logic_val = var_data.get('applied_logic')
                if logic_val is None:
                    raise ValidationError({'variables': '각 variable은 applied_logic을 포함해야 합니다.'})
                try:
                    if not isinstance(logic_val, CoreControlLogic):
                        CoreControlLogic.objects.get(pk=logic_val)
                except CoreControlLogic.DoesNotExist:
                    raise ValidationError({'variables': f'ControlLogic id={logic_val}을(를) 찾을 수 없습니다.'})

            group = ControlGroup.objects.create(**create_kwargs)
            for var_data in control_variables_data:
                logic_val = var_data.get('applied_logic')
                logic_obj = CoreControlLogic.objects.get(pk=logic_val) if not isinstance(logic_val, CoreControlLogic) else logic_val

                # result를 Variable instance로 해석
                res = var_data.get('result')
                result_obj = None
                if res is None or res == []:
                    result_obj = None
                elif isinstance(res, Variable):
                    result_obj = res
                elif isinstance(res, dict):
                    res_id = res.get('id') or res.get('pk')
                    result_obj = Variable.objects.filter(pk=res_id).first()
                else:
                    try:
                        res_id = int(res)
                        result_obj = Variable.objects.filter(pk=res_id).first()
                    except Exception:
                        result_obj = None

                ControlVariable.objects.create(
                    group=group,
                    applied_logic=logic_obj,
                    data_type=var_data.get('data_type', ''),
                    args=var_data.get('args', []),
                    result=result_obj,
                )
        return group

    def update(self, instance, validated_data):
        control_variables_data = None
        for key in ('variables', 'control_variables_in_group', 'lsissocket_control_variables_in_group'):
            if key in validated_data:
                control_variables_data = validated_data.pop(key)
                break
        # Update only concrete model fields
        allowed = {f.name for f in ControlGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        for attr, val in list(validated_data.items()):
            if attr in allowed:
                setattr(instance, attr, val)
        instance.save()

        if control_variables_data is not None:
            with transaction.atomic():
                # applied_logic 존재 검증
                for var_data in control_variables_data:
                    logic_val = var_data.get('applied_logic')
                    if logic_val is None:
                        raise ValidationError({'variables': '각 variable은 applied_logic을 포함해야 합니다.'})
                    try:
                        if not isinstance(logic_val, CoreControlLogic):
                            CoreControlLogic.objects.get(pk=logic_val)
                    except CoreControlLogic.DoesNotExist:
                        raise ValidationError({'variables': f'ControlLogic id={logic_val}을(를) 찾을 수 없습니다.'})

                instance.lsissocket_control_variables_in_group.all().delete()
                for var_data in control_variables_data:
                    logic_val = var_data.get('applied_logic')
                    logic_obj = CoreControlLogic.objects.get(pk=logic_val) if not isinstance(logic_val, CoreControlLogic) else logic_val

                    # result를 Variable instance로 해석
                    res = var_data.get('result')
                    result_obj = None
                    if res is None or res == []:
                        result_obj = None
                    elif isinstance(res, Variable):
                        result_obj = res
                    elif isinstance(res, dict):
                        res_id = res.get('id') or res.get('pk')
                        result_obj = Variable.objects.filter(pk=res_id).first()
                    else:
                        try:
                            res_id = int(res)
                            result_obj = Variable.objects.filter(pk=res_id).first()
                        except Exception:
                            result_obj = None

                    ControlVariable.objects.create(
                        group=instance,
                        applied_logic=logic_obj,
                        data_type=var_data.get('data_type', ''),
                        args=var_data.get('args', []),
                        result=result_obj,
                    )
        return instance

class CalcVariableSerializer(serializers.ModelSerializer):
    # Expose nested DataName details for read, accept PK for write via name_id
    name = DataNameSerializer(read_only=True)
    name_id = serializers.PrimaryKeyRelatedField(source='name', queryset=CoreDataName.objects.all(), write_only=True, required=True, help_text='연결된 DataName ID. 예: 8', style={'example': 8})
    
    # result: 연산 결과값은 이제 Variable FK (Variable id 또는 null 허용)
    result = serializers.PrimaryKeyRelatedField(queryset=Variable.objects.all(), required=False, allow_null=True, help_text='연산 결과 Variable ID (예: 422)')
    class Meta:
        model = CalcVariable
        fields = [
            'id', 'group', 'name', 'name_id', 'data_type', 'args', 'result'
        ]

    def to_internal_value(self, data):
        # Allow clients to send 'name' as either nested object or id; normalize to name_id
        if isinstance(data, dict) and 'name' in data and isinstance(data.get('name'), dict) and 'id' in data.get('name'):
            data = dict(data)
            data['name_id'] = data['name']['id']
        return super().to_internal_value(data)

class CalcGroupSerializer(serializers.ModelSerializer):
    # expose nested variables under 'variables' and map to model related_name
    variables = CalcVariableSerializer(
        many=True,
        read_only=False,
        required=False,
        source='lsissocket_calc_variables_in_group'
    )

    class Meta:
        model = CalcGroup
        fields = [
            'id', 'name', 'description', 'variables'
        ]

    def create(self, validated_data):
        # Accept nested variables under several possible keys for backward compatibility
        calc_variables_data = []
        for key in ('variables', 'calc_variables_in_group', 'lsissocket_calc_variables_in_group'):
            if key in validated_data:
                calc_variables_data = validated_data.pop(key)
                break
        # Only keep concrete model fields when creating model to avoid unexpected kwargs
        allowed = {f.name for f in CalcGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        create_kwargs = {k: v for k, v in validated_data.items() if k in allowed}

        with transaction.atomic():
            # validate referenced DataName ids
            for var_data in calc_variables_data:
                name_val = var_data.get('name') or var_data.get('name_id')
                if name_val is None:
                    raise ValidationError({'variables': '각 variable은 name 또는 name_id를 포함해야 합니다.'})
                try:
                    if not isinstance(name_val, CoreDataName):
                        CoreDataName.objects.get(pk=name_val)
                except CoreDataName.DoesNotExist:
                    raise ValidationError({'variables': f'DataName id={name_val}을(를) 찾을 수 없습니다.'})

            group = CalcGroup.objects.create(**create_kwargs)
            for var_data in calc_variables_data:
                name_val = var_data.get('name') or var_data.get('name_id')
                name_obj = CoreDataName.objects.get(pk=name_val) if not isinstance(name_val, CoreDataName) else name_val
                # Resolve result to Variable instance if provided (allow id or nested dict)
                res = var_data.get('result')
                result_obj = None
                # Accept Variable instance, dict with id, numeric id (int/str) or None
                if res is None or res == []:
                    result_obj = None
                elif isinstance(res, Variable):
                    result_obj = res
                elif isinstance(res, dict):
                    res_id = res.get('id') or res.get('pk')
                    try:
                        result_obj = Variable.objects.filter(pk=res_id).first()
                    except Exception:
                        result_obj = None
                else:
                    # res may be an int or numeric string
                    try:
                        res_id = int(res)
                        result_obj = Variable.objects.filter(pk=res_id).first()
                    except Exception:
                        result_obj = None

                CalcVariable.objects.create(
                    group=group,
                    name=name_obj,
                    data_type=var_data.get('data_type', ''),
                    args=var_data.get('args', []),
                    result=result_obj,
                )
        return group
    
    def update(self, instance, validated_data):
        calc_variables_data = None
        for key in ('variables', 'calc_variables_in_group', 'lsissocket_calc_variables_in_group'):
            if key in validated_data:
                calc_variables_data = validated_data.pop(key)
                break
        # Update only concrete model fields
        allowed = {f.name for f in CalcGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        for attr, val in list(validated_data.items()):
            if attr in allowed:
                setattr(instance, attr, val)
        instance.save()
        if calc_variables_data is not None:
            with transaction.atomic():
                for var_data in calc_variables_data:
                    name_val = var_data.get('name') or var_data.get('name_id')
                    if name_val is None:
                        raise ValidationError({'variables': '각 variable은 name 또는 name_id를 포함해야 합니다.'})
                    try:
                        if not isinstance(name_val, CoreDataName):
                            CoreDataName.objects.get(pk=name_val)
                    except CoreDataName.DoesNotExist:
                        raise ValidationError({'variables': f'DataName id={name_val}을(를) 찾을 수 없습니다.'})

                instance.lsissocket_calc_variables_in_group.all().delete()
                for var_data in calc_variables_data:
                    name_val = var_data.get('name') or var_data.get('name_id')
                    name_obj = CoreDataName.objects.get(pk=name_val) if not isinstance(name_val, CoreDataName) else name_val
                    # Resolve result id/nested to Variable instance
                    res = var_data.get('result')
                    result_obj = None
                    if res is None or res == []:
                        result_obj = None
                    elif isinstance(res, Variable):
                        result_obj = res
                    elif isinstance(res, dict):
                        res_id = res.get('id') or res.get('pk')
                        try:
                            result_obj = Variable.objects.filter(pk=res_id).first()
                        except Exception:
                            result_obj = None
                    else:
                        try:
                            res_id = int(res)
                            result_obj = Variable.objects.filter(pk=res_id).first()
                        except Exception:
                            result_obj = None

                    CalcVariable.objects.create(
                        group=instance,
                        name=name_obj,
                        data_type=var_data.get('data_type', ''),
                        args=var_data.get('args', []),
                        result=result_obj,
                    )
        return instance

class AlartVariableSerializer(serializers.ModelSerializer):
    
    # Expose nested DataName details for read, accept PK for write via name_id
    name = DataNameSerializer(read_only=True)
    name_id = serializers.PrimaryKeyRelatedField(source='name', queryset=CoreDataName.objects.all(), write_only=True, required=True, help_text='연결된 DataName ID. 예: 8', style={'example': 8})
    
    # result: 연산 결과값은 이제 Variable FK (Variable id 또는 null 허용)
    result = serializers.PrimaryKeyRelatedField(queryset=Variable.objects.all(), required=False, allow_null=True, help_text='연산 결과 Variable ID (예: 422)')
    class Meta:
        model = AlartVariable
        fields = [
            'id', 'group', 'name', 'name_id', 'data_type', 'args', 'result'
        ]

    def to_internal_value(self, data):
        if isinstance(data, dict) and 'name' in data and isinstance(data.get('name'), dict) and 'id' in data.get('name'):
            data = dict(data)
            data['name_id'] = data['name']['id']
        return super().to_internal_value(data)


class AlartGroupSerializer(serializers.ModelSerializer):
    variables = AlartVariableSerializer(
        many=True,
        read_only=False,
        required=False,
        source='lsissocket_alart_variables_in_group'
    )

    class Meta:
        model = AlartGroup
        fields = ['id', 'name', 'description', 'variables']

    def create(self, validated_data):
        variables_data = []
        for key in ('variables', 'alart_variables_in_group', 'lsissocket_alart_variables_in_group'):
            if key in validated_data:
                variables_data = validated_data.pop(key)
                break
        allowed = {f.name for f in AlartGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        create_kwargs = {k: v for k, v in validated_data.items() if k in allowed}

        with transaction.atomic():
            for var_data in variables_data:
                name_val = var_data.get('name') or var_data.get('name_id')
                if name_val is None:
                    raise ValidationError({'variables': '각 variable은 name 또는 name_id를 포함해야 합니다.'})
                try:
                    if not isinstance(name_val, CoreDataName):
                        CoreDataName.objects.get(pk=name_val)
                except CoreDataName.DoesNotExist:
                    raise ValidationError({'variables': f'DataName id={name_val}을(를) 찾을 수 없습니다.'})

            group = AlartGroup.objects.create(**create_kwargs)
            for var_data in variables_data:
                name_val = var_data.get('name') or var_data.get('name_id')
                name_obj = CoreDataName.objects.get(pk=name_val) if not isinstance(name_val, CoreDataName) else name_val
                AlartVariable.objects.create(
                    group=group,
                    name=name_obj,
                    data_type=var_data.get('data_type', ''),
                    threshold=var_data.get('threshold', {}),
                    args=var_data.get('args', []),
                    attributes=var_data.get('attributes', []),
                )
        return group

    def update(self, instance, validated_data):
        variables_data = None
        for key in ('variables', 'alart_variables_in_group', 'lsissocket_alart_variables_in_group'):
            if key in validated_data:
                variables_data = validated_data.pop(key)
                break
        allowed = {f.name for f in AlartGroup._meta.get_fields() if getattr(f, 'concrete', True) and not getattr(f, 'auto_created', False)}
        for attr, val in list(validated_data.items()):
            if attr in allowed:
                setattr(instance, attr, val)
        instance.save()
        if variables_data is not None:
            with transaction.atomic():
                for var_data in variables_data:
                    name_val = var_data.get('name') or var_data.get('name_id')
                    if name_val is None:
                        raise ValidationError({'variables': '각 variable은 name 또는 name_id를 포함해야 합니다.'})
                    try:
                        if not isinstance(name_val, CoreDataName):
                            CoreDataName.objects.get(pk=name_val)
                    except CoreDataName.DoesNotExist:
                        raise ValidationError({'variables': f'DataName id={name_val}을(를) 찾을 수 없습니다.'})

                instance.lsissocket_alart_variables_in_group.all().delete()
                for var_data in variables_data:
                    name_val = var_data.get('name') or var_data.get('name_id')
                    name_obj = CoreDataName.objects.get(pk=name_val) if not isinstance(name_val, CoreDataName) else name_val
                    AlartVariable.objects.create(
                        group=instance,
                        name=name_obj,
                        data_type=var_data.get('data_type', ''),
                        threshold=var_data.get('threshold', {}),
                        args=var_data.get('args', []),
                        attributes=var_data.get('attributes', []),
                    )
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

class SetupGroupSerializer(serializers.ModelSerializer):
    # 선택: 변수 PK 목록으로 쓰기/수정, 상세는 읽기용 별도 필드 제공
    variables = serializers.PrimaryKeyRelatedField(many=True, queryset=Variable.objects.all(), required=False, allow_empty=True)
    variables_detail = VariableSerializer(source='variables', many=True, read_only=True)

    class Meta:
        model = SetupGroup
        exclude = ('is_deleted',)

    # write_mode, interval_seconds 제거에 따라 별도 검증 로직 제거
    def validate(self, attrs):
        return attrs

# 제거: SetupVariableSerializer (SetupGroup에서 Variable을 직접 선택)
# class SetupVariableSerializer(serializers.ModelSerializer):
#     ...removed...
