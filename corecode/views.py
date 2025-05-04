from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import Project, ProjectVersion, MemoryGroup, Variable
from .serializers import ProjectSerializer, ProjectVersionSerializer, MemoryGroupSerializer, VariableSerializer

# ProjectViewSet
# -------------------
# 이 ViewSet은 프로젝트의 CRUD, 버전 백업(코멘트와 함께 저장), 특정 버전으로의 복구(롤백) 기능을 제공합니다.
# 주요 기능:
#   - 프로젝트 생성/조회/수정/삭제
#   - /projects/{id}/backup/ : 현재 상태를 ProjectVersion으로 저장(코멘트, 버전명 포함)
#   - /projects/{id}/restore/{version_id}/ : 특정 버전의 상태로 복구(롤백)
#   - ProjectVersion, MemoryGroup, Variable 모델과 연동하여 전체 메모리 맵 구조를 관리
#   - git과 유사한 프로젝트 이력 관리 및 복구 지원
#
# 사용 예시:
#   POST /projects/1/backup/ {"note": "설명", "version": "버전명"}
#   POST /projects/1/restore/3/ (3번 버전으로 복구)
# -------------------
#
# ProjectVersionViewSet, MemoryGroupViewSet, VariableViewSet은 각각의 모델에 대한 CRUD API를 제공합니다.
# -------------------
# ProjectVersionViewSet: 프로젝트 버전(ProjectVersion) 모델의 CRUD API를 제공합니다.
# MemoryGroupViewSet: 메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
# VariableViewSet: 변수(Variable) 모델의 CRUD API를 제공합니다.
# -------------------

# Create your views here.

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @action(detail=True, methods=['post'])
    def backup(self, request, pk=None):
        """
        ProjectVersionViewSet을 통해 버전 생성만 트리거 (실제 데이터 복사는 ProjectVersionViewSet에서 담당)
        """
        project = self.get_object()
        comment = request.data.get('note', '')
        version_str = request.data.get('version')
        if not version_str:
            from datetime import datetime
            version_str = datetime.now().strftime('%Y%m%d%H%M%S')
        # ProjectVersion 생성만 위임
        pv = ProjectVersion.objects.create(project=project, version=version_str, note=comment)
        return Response({'status': 'backup created', 'version': version_str, 'note': comment}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='restore/(?P<version_id>[^/.]+)')
    def restore(self, request, pk=None, version_id=None):
        """
        ProjectVersionViewSet을 통해 복구 트리거 (실제 데이터 복원은 ProjectVersionViewSet에서 담당)
        """
        project = self.get_object()
        try:
            pv = ProjectVersion.objects.get(pk=version_id, project=project)
        except ProjectVersion.DoesNotExist:
            return Response({'error': 'Version not found'}, status=404)
        # 복구 트리거만 전달
        pv.restore_version()  # ProjectVersion 모델에 복구 메서드 구현 필요
        return Response({'status': 'restored', 'version': pv.version})

class ProjectVersionViewSet(viewsets.ModelViewSet):
    """
    프로젝트 버전(ProjectVersion) 모델의 CRUD 및 복구/스냅샷 관리 API
    - create: 버전 생성 시 해당 시점의 MemoryGroup/Variable 전체 복사
    - restore_version: 해당 버전의 MemoryGroup/Variable을 현재로 복원
    """
    queryset = ProjectVersion.objects.all()
    serializer_class = ProjectVersionSerializer

    def perform_create(self, serializer):
        """
        버전 생성 시 해당 프로젝트의 MemoryGroup/Variable 전체 복사
        """
        pv = serializer.save()
        project = pv.project
        for group in project.memorygroup_set.all():
            new_group = MemoryGroup.objects.create(
                project_version=pv,
                group_id=group.group_id,
                start_device=group.start_device,
                start_address=group.start_address,
                size_byte=group.size_byte,
            )
            for var in group.variables.all():
                Variable.objects.create(
                    group=new_group,
                    name=var.name,
                    device=var.device,
                    address=var.address,
                    data_type=var.data_type,
                    unit=var.unit,
                    scale=var.scale,
                    offset=var.offset,
                )

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """
        해당 버전의 MemoryGroup/Variable을 현재로 복원
        """
        pv = self.get_object()
        pv.restore_version()  # ProjectVersion 모델에 복구 메서드 구현 필요
        return Response({'status': 'restored', 'version': pv.version})

# ProjectVersion 모델에 복구 메서드 추가 필요
# 예시:
# class ProjectVersion(models.Model):
#     ...existing code...
#     def restore_version(self):
#         # 현재 프로젝트의 MemoryGroup/Variable 삭제 후, 이 버전의 데이터로 복원
#         ...

class MemoryGroupViewSet(viewsets.ModelViewSet):
    """
    메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
    각 MemoryGroup 인스턴스는 project_version 필드를 통해 ProjectVersion(프로젝트 버전)과 연결되어 있습니다.
    """
    queryset = MemoryGroup.objects.all()
    serializer_class = MemoryGroupSerializer

class VariableViewSet(viewsets.ModelViewSet):
    """
    변수(Variable) 모델의 CRUD API를 제공합니다.
    각 Variable 인스턴스는 group 필드를 통해 MemoryGroup과 연결되어 있습니다.
    """
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
