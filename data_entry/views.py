from django.shortcuts import render

from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status

# django-filters를 직접 사용
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore
FILTER_BACKENDS = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]

from . import models, serializers

from . import logger, redis_instance


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000


class BaseDataViewSet(viewsets.ModelViewSet):
    """공통 설정: 인증은 읽기 가능, 쓰기는 인증 필요
    필터링, 정렬, 검색, 페이지네이션 기본 적용
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = FILTER_BACKENDS
    ordering_fields = ['timestamp', 'client_id', 'group_id', 'var_id', 'value', 'min_value', 'max_value', 'avg_value', 'sum_value', 'count']
    ordering = ['-timestamp']
    search_fields = ['client_id', 'group_id', 'var_id']


class TwoMinuteDataViewSet(BaseDataViewSet):
    queryset = models.TwoMinuteData.objects.all()
    serializer_class = serializers.TwoMinuteDataSerializer
    filterset_fields = ['client_id', 'group_id', 'var_id', 'timestamp']


class TenMinuteDataViewSet(BaseDataViewSet):
    queryset = models.TenMinuteData.objects.all()
    serializer_class = serializers.TenMinuteDataSerializer
    filterset_fields = ['client_id', 'group_id', 'var_id', 'timestamp']


class HourlyDataViewSet(BaseDataViewSet):
    queryset = models.HourlyData.objects.all()
    serializer_class = serializers.HourlyDataSerializer
    filterset_fields = ['client_id', 'group_id', 'var_id', 'timestamp']


class DailyDataViewSet(BaseDataViewSet):
    queryset = models.DailyData.objects.all()
    serializer_class = serializers.DailyDataSerializer
    filterset_fields = ['client_id', 'group_id', 'var_id', 'timestamp']


class RedisKeyViewSet(viewsets.ViewSet):
    """Read-only ViewSet to list and retrieve Redis keys in DB0 named 'client_id:var_id'."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    _allowed_ordering = ['client_id', 'var_id', 'value', 'value_type']

    def _ensure_connected(self):
        try:
            # try to connect if not already
            if hasattr(redis_instance, 'connect'):
                try:
                    redis_instance.connect()
                except Exception:
                    pass
        except Exception:
            pass

    def _parse_key(self, key):
        parts = key.split(':')
        if len(parts) != 2:
            return None
        try:
            client_id = int(parts[0])
            var_id = int(parts[1])
            return client_id, var_id
        except Exception:
            return None

    def _value_type(self, value):
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'bool'
        if isinstance(value, int) and not isinstance(value, bool):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, str):
            return 'str'
        return type(value).__name__

    def list(self, request):
        """Supports query params:
        - pattern: redis key pattern (default '*:*')
        - q: free text search (searches client_id, var_id, value, value_type)
        - client_id, var_id: exact numeric filter
        - ordering: e.g. 'client_id' or '-client_id'
        - page_size: override default page size
        """
        self._ensure_connected()
        try:
            pattern = request.query_params.get('pattern', '*:*')
            q = request.query_params.get('q')
            ordering = request.query_params.get('ordering')

            # optional numeric filters
            filter_client = request.query_params.get('client_id')
            filter_var = request.query_params.get('var_id')

            # fetch keys (use scan style)
            keys = []
            try:
                keys = redis_instance.query_scan(pattern)
            except Exception:
                try:
                    keys = redis_instance.client.keys(pattern) if hasattr(redis_instance, 'client') and redis_instance.client else []
                except Exception:
                    keys = []

            entries = []
            for key in keys:
                parsed = self._parse_key(key)
                if not parsed:
                    continue
                client_id, var_id = parsed

                # apply numeric filters early
                if filter_client and str(client_id) != str(filter_client):
                    continue
                if filter_var and str(var_id) != str(filter_var):
                    continue

                try:
                    value = redis_instance.get_value(key)
                except Exception:
                    try:
                        raw = redis_instance.client.get(key)
                        value = raw
                    except Exception:
                        value = None

                entry = {
                    'client_id': client_id,
                    'var_id': var_id,
                    'value': value,
                    'value_type': self._value_type(value),
                }

                # apply free-text search if provided
                if q:
                    q_lower = q.lower()
                    hay = f"{entry['client_id']}|{entry['var_id']}|{entry['value']}|{entry['value_type']}".lower()
                    if q_lower not in hay:
                        continue

                entries.append(entry)

            # ordering support
            if ordering:
                reverse = ordering.startswith('-')
                field = ordering.lstrip('-')
                if field in self._allowed_ordering:
                    def sort_key(e):
                        v = e.get(field)
                        # None last
                        if v is None:
                            return (1, '')
                        # numeric types unify to float for ordering
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            return (0, float(v))
                        # bools order as ints
                        if isinstance(v, bool):
                            return (0, int(v))
                        return (0, str(v))
                    entries.sort(key=sort_key, reverse=reverse)

            # pagination
            paginator = self.pagination_class()
            page_size = request.query_params.get('page_size')
            if page_size:
                try:
                    paginator.page_size = int(page_size)
                except Exception:
                    pass

            page = paginator.paginate_queryset(entries, request, view=self)
            serializer = serializers.RedisKeySerializer(page if page is not None else entries, many=True)
            if page is not None:
                return paginator.get_paginated_response(serializer.data)

            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        self._ensure_connected()
        if pk is None:
            return Response({'detail': 'pk required'}, status=status.HTTP_400_BAD_REQUEST)

        # allow pk passed as 'client:var' or 'client/var'
        key = pk if ':' in pk else pk.replace('/', ':')
        parsed = self._parse_key(key)
        if not parsed:
            return Response({'detail': 'invalid key format'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            try:
                value = redis_instance.get_value(key)
            except Exception:
                try:
                    value = redis_instance.client.get(key)
                except Exception:
                    value = None

            data = {
                'client_id': parsed[0],
                'var_id': parsed[1],
                'value': value,
                'value_type': self._value_type(value),
            }
            serializer = serializers.RedisKeySerializer(data)
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
