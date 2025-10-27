from rest_framework import serializers
from . import models
import math
import json


def _infer_value_type(value):
    """Infer a simple type string for a given value (same rules as management command).
    Returns one of: 'int', 'float', 'bool', 'str', 'null' or None if unknown.
    """
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        if math.isfinite(value) and float(value).is_integer():
            return 'int'
        return 'float'
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.lower() in ('true', 'false', 't', 'f', 'yes', 'no'):
            return 'bool'
        try:
            decoded = json.loads(s)
            return _infer_value_type(decoded)
        except Exception:
            pass
        try:
            f = float(s)
            if math.isfinite(f) and float(f).is_integer():
                return 'int'
            return 'float'
        except Exception:
            return 'str'
    # lists/dicts
    if isinstance(value, dict):
        # try common keys
        for k in ('value', 'val', 'v', 'data', 'measurement'):
            if k in value:
                return _infer_value_type(value[k])
        if len(value) == 1:
            return _infer_value_type(next(iter(value.values())))
        return None
    if isinstance(value, (list, tuple)) and value:
        return _infer_value_type(value[0])
    return None


class ValueTypeMixin:
    def _compute_value_type_from_validated(self, validated_data):
        # prefer explicit 'value' field
        if 'value' in validated_data and validated_data.get('value') is not None:
            return _infer_value_type(validated_data.get('value'))
        # fallback to aggregates
        for fld in ('min_value', 'avg_value', 'max_value', 'sum_value'):
            if fld in validated_data and validated_data.get(fld) is not None:
                return _infer_value_type(validated_data.get(fld))
        return None


class TwoMinuteDataSerializer(ValueTypeMixin, serializers.ModelSerializer):
    class Meta:
        model = models.TwoMinuteData
        fields = (
            'timestamp', 'client_id', 'group_id', 'var_id',
            'value', 'value_type', 'min_value', 'max_value', 'avg_value', 'sum_value', 'count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        vt = self._compute_value_type_from_validated(validated_data)
        if vt is not None:
            validated_data['value_type'] = vt
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # if value or aggregates provided, recompute
        if any(k in validated_data for k in ('value', 'min_value', 'avg_value', 'max_value', 'sum_value')):
            vt = self._compute_value_type_from_validated(validated_data)
            if vt is not None:
                validated_data['value_type'] = vt
        return super().update(instance, validated_data)


class TenMinuteDataSerializer(ValueTypeMixin, serializers.ModelSerializer):
    class Meta:
        model = models.TenMinuteData
        fields = (
            'timestamp', 'client_id', 'group_id', 'var_id',
            'value', 'value_type', 'min_value', 'max_value', 'avg_value', 'sum_value', 'count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        vt = self._compute_value_type_from_validated(validated_data)
        if vt is not None:
            validated_data['value_type'] = vt
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if any(k in validated_data for k in ('value', 'min_value', 'avg_value', 'max_value', 'sum_value')):
            vt = self._compute_value_type_from_validated(validated_data)
            if vt is not None:
                validated_data['value_type'] = vt
        return super().update(instance, validated_data)


class HourlyDataSerializer(ValueTypeMixin, serializers.ModelSerializer):
    class Meta:
        model = models.HourlyData
        fields = (
            'timestamp', 'client_id', 'group_id', 'var_id',
            'value', 'value_type', 'min_value', 'max_value', 'avg_value', 'sum_value', 'count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        vt = self._compute_value_type_from_validated(validated_data)
        if vt is not None:
            validated_data['value_type'] = vt
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if any(k in validated_data for k in ('value', 'min_value', 'avg_value', 'max_value', 'sum_value')):
            vt = self._compute_value_type_from_validated(validated_data)
            if vt is not None:
                validated_data['value_type'] = vt
        return super().update(instance, validated_data)


class DailyDataSerializer(ValueTypeMixin, serializers.ModelSerializer):
    class Meta:
        model = models.DailyData
        fields = (
            'timestamp', 'client_id', 'group_id', 'var_id',
            'value', 'value_type', 'min_value', 'max_value', 'avg_value', 'sum_value', 'count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        vt = self._compute_value_type_from_validated(validated_data)
        if vt is not None:
            validated_data['value_type'] = vt
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if any(k in validated_data for k in ('value', 'min_value', 'avg_value', 'max_value', 'sum_value')):
            vt = self._compute_value_type_from_validated(validated_data)
            if vt is not None:
                validated_data['value_type'] = vt
        return super().update(instance, validated_data)


class RedisKeySerializer(serializers.Serializer):
    """Redis DB0 key serializer for keys named "client_id:var_id".
    value can be bool/int/float/other JSON-serializable types.
    """
    client_id = serializers.IntegerField()
    var_id = serializers.IntegerField()
    value = serializers.JSONField()
    value_type = serializers.CharField(read_only=True)
