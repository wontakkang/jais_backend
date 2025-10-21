import logging
logger = logging.getLogger(__name__)
from utils.protocol.context import CONTEXT_REGISTRY



def sensor_node_job():
    """
    CONTEXT_REGISTRY에 등록된 모든 센서 노드의 상태를 점검하는 작업 함수
    MCUnode.context_store.state.json 파일에 저장된 센서 노드 상태를 불러와
    CONTEXT_REGISTRY에 반영합니다.
    첫번째 키값은 제품시리얼 번호
    두번째 키값에서 Meta를 찾아 명령어를 실행합니다.
    1. CONTEXT_REGISTRY에서 모든 센서 노드 컨텍스트를 순회
    2. 각 컨텍스트에서 저장된 상태를 불러옴
    3. 상태에 따라 필요한 명령어를 실행
    """
    