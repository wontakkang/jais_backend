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
        현재 프로젝트의 상태를 코멘트와 함께 백업(버전 생성)
        변수(Variable) 변경/삭제 내역을 자동으로 Note에 요약
        """
        project = self.get_object()
        comment = request.data.get('note', '')
        version_str = request.data.get('version')
        if not version_str:
            from datetime import datetime
            version_str = datetime.now().strftime('%Y%m%d%H%M%S')

        # diff 분석: 이전 버전과 현재 상태 비교
        prev_version = project.versions.last() if project.versions.exists() else None
        prev_vars = {}
        if prev_version:
            for group in prev_version.groups.all():
                for var in group.variables.all():
                    prev_vars[(group.group_id, var.name)] = var
        curr_vars = {}
        for group in project.memorygroup_set.all():
            for var in group.variables.all():
                curr_vars[(group.group_id, var.name)] = var

        # 수정/삭제 변수 추출
        modified = []
        deleted = []
        for key, prev_var in prev_vars.items():
            curr_var = curr_vars.get(key)
            if curr_var is None:
                deleted.append(f"{prev_var.name}(group:{prev_var.group.group_id})")
            else:
                changes = []
                for field in ['address', 'data_type', 'unit', 'scale', 'offset']:
                    prev_val = getattr(prev_var, field)
                    curr_val = getattr(curr_var, field)
                    if prev_val != curr_val:
                        changes.append(f"{field}: {prev_val}→{curr_val}")
                if changes:
                    modified.append(f"{prev_var.name}(group:{prev_var.group.group_id}, {'/'.join(changes)})")

        # Note 자동 생성
        auto_note = []
        if modified:
            auto_note.append("수정된 변수: " + ", ".join(modified))
        if deleted:
            auto_note.append("삭제된 변수: " + ", ".join(deleted))
        if auto_note:
            if comment:
                comment += "\n"
            comment += "\n".join(auto_note)

        with transaction.atomic():
            pv = ProjectVersion.objects.create(project=project, version=version_str, note=comment)
            for group in project.versions.last().groups.all() if project.versions.exists() else []:
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
        return Response({'status': 'backup created', 'version': version_str, 'note': comment}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='restore/(?P<version_id>[^/.]+)')
    def restore(self, request, pk=None, version_id=None):
        """
        특정 버전으로 프로젝트 상태 복구
        """
        project = self.get_object()
        try:
            pv = ProjectVersion.objects.get(pk=version_id, project=project)
        except ProjectVersion.DoesNotExist:
            return Response({'error': 'Version not found'}, status=404)
        with transaction.atomic():
            # 기존 그룹/변수 삭제
            for v in project.versions.last().groups.all() if project.versions.exists() else []:
                v.variables.all().delete()
                v.delete()
            # 복구
            for group in pv.groups.all():
                new_group = MemoryGroup.objects.create(
                    project_version=project.versions.last(),
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
        return Response({'status': 'restored', 'version': pv.version})

class ProjectVersionViewSet(viewsets.ModelViewSet):
    """
    프로젝트 버전(ProjectVersion) 모델의 CRUD API를 제공합니다.
    """
    queryset = ProjectVersion.objects.all()
    serializer_class = ProjectVersionSerializer

class MemoryGroupViewSet(viewsets.ModelViewSet):
    """
    메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
    -------------------
    각 MemoryGroup 인스턴스는 project_version 필드를 통해 ProjectVersion(프로젝트 버전)과 연결되어 있습니다.
    즉, 메모리 그룹은 자신이 속한 프로젝트 버전 정보를 ForeignKey로 참조합니다.
    
    주요 활용:
      - 특정 ProjectVersion에 속한 MemoryGroup만 조회: /memorygroups/?project_version=3
      - 직렬화/조회 시 project_version 필드를 통해 버전 정보 접근 가능
      - ViewSet에서 project_version 필드를 활용해 다양한 필터링 및 연동 처리 가능
    -------------------
    """
    queryset = MemoryGroup.objects.all()
    serializer_class = MemoryGroupSerializer

class VariableViewSet(viewsets.ModelViewSet):
    """
    변수(Variable) 모델의 CRUD API를 제공합니다.
    """
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
