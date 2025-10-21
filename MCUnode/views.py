# 상세 주석 추가: 파일 상단에 모듈 목적과 주요 동작 요약을 한글로 설명합니다.
# 이 파일은 DE-MCU 직렬 통신을 위한 DRF 뷰셋을 정의합니다.
# - MCUNodeConfigViewSet, IoTControllerConfigViewSet: 모델 CRUD용
# - DE_MCUSerialViewSet: POST 요청으로 DE-MCU 명령을 직렬 포트에 전송하고 응답을 반환하거나 없으면 시뮬레이션 응답을 반환
# - 에러 상황에서는 가능한 경우 클라이언트의 last_error를 우선 사용해 503을 반환합니다

import logging
import json
from rest_framework import viewsets, filters

from utils.protocol.context import CONTEXT_REGISTRY
from .models import MCUNodeConfig, IoTControllerConfig
from .serializers import MCUNodeConfigSerializer, IoTControllerConfigSerializer, DE_MCUSerialRequestSerializer, StateEntrySerializer
from utils.protocol.MCU.client.base import DE_MCU_SerialClient
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from utils.protocol.context.manager import get_or_create_registry_entry, persist_registry_state, save_status_with_meta, save_status_nested, save_status_path, save_block_top_level, save_setup, ensure_context_store_for_apps, load_most_recent_json_block_for_app, restore_json_blocks_to_slave_context
from pathlib import Path
from datetime import datetime

def _iso_parse(s):
    """Try to parse ISO datetime strings robustly without external dependencies.
    Returns a datetime or None on failure.
    """
    if not s:
        return None
    try:
        # datetime.fromisoformat supports many ISO forms (Python 3.7+)
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # strip trailing Z (UTC) and retry
            if isinstance(s, str) and s.endswith('Z'):
                return datetime.fromisoformat(s[:-1])
        except Exception:
            return None
    return None

logger = logging.getLogger('MCUnode')
class MCUNodeConfigViewSet(viewsets.ModelViewSet):
    # MCUNodeConfig 모델에 대한 표준 CRUD 뷰셋입니다.
    # queryset / serializer_class를 통해 기본 동작을 제공하므로 별도 커스터마이징이 필요 없을 때 사용합니다.
    queryset = MCUNodeConfig.objects.all()
    serializer_class = MCUNodeConfigSerializer


class IoTControllerConfigViewSet(viewsets.ModelViewSet):
    # IoTControllerConfig 모델에 대한 표준 CRUD 뷰셋입니다.
    queryset = IoTControllerConfig.objects.all()
    serializer_class = IoTControllerConfigSerializer


class DE_MCUSerialViewSet(viewsets.ViewSet):
    """DE-MCU 직렬 클라이언트용 ViewSet

    설명:
    - 클라이언트에서 POST로 요청 시, 전달된 포트와 명령을 사용해 DE-MCU PDU를 생성하고 직렬 포트로 전송합니다.
    - 실제 장치로부터 응답이 오면 이를 파싱하여 반환합니다. 응답이 없을 경우 내부적으로 시뮬레이션된 응답을 생성해 반환합니다.
    - 오류 처리: 직렬 통신 관련 오류(SerialException 또는 client.last_error 발생)는 503으로 반환하여 호출자가 재시도/대체 처리를 할 수 있도록 합니다.

    요청 예시 JSON:
    {
        "port": "COM6",
        "command": "NODE_SELECT_REQ",
        "serial_number": "4653500D004C003C"
        "req_data": ""
    }
    # SERIAL_SETUP : req_data(DDI) : {'Channel' : 1, 'Baudrate': 'BAUD_1200', 'SerialType': 'SDI', 'DataBits': 'SEVEN_BITS', 'Parity': 'EVEN', 'StopBits': 'ONE_BIT', 'FlowControl': 'NONE'}
    # SERIAL_WRITE : req_data(DDI) : {'Channel' : 1, 'Timeout': 1000, 'Data': '0I!'}
    # SERIAL_SETUP : req_data(RS485) : {'Channel' : 1, 'Baudrate': 9600, 'Type': 'RS485', 'Data_Bit': '8 Bit', 'Parity': 'NONE', 'Stop_Bit': '1 Bit', 'Flow_Control': 'NONE'}
    # SERIAL_WRITE : req_data(RS485) : {'Channel' : 1, 'Timeout': 1000, 'Data': '01 04 08 12 34 56 78 9A BC DE F0 CB FF'}
    """
    serializer_class = DE_MCUSerialRequestSerializer

    def list(self, request):
        # 브라우저에서 DRF의 Browsable API를 통해 POST 폼을 렌더링하기 위해 빈 200 응답을 반환.
        # 실제 목록 조회 기능은 필요하지 않으므로 간단히 200을 반환합니다.
        return Response(status=status.HTTP_200_OK)

    def create(self, request):
        # 최소한의 뷰 레벨 유효성 검증만 수행하고 상태 저장/직렬화는 context.manager로 위임합니다.
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        port = data.get('port')
        command = data.get('command')
        serial_bytes = data.get('serial_number')
        req_data = data.get('req_data')
        firmware_file = data.get('firmware_file', None)
        if firmware_file:
            try:
                req_data = firmware_file.read()
            except Exception as e:
                return Response({'detail': f'펌웨어 파일 읽기 실패: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        checksum_type = data.get('checksum_type', 'xor_simple')

        # 간단한 직렬 처리
        client = None
        try:
            # create client and perform transact. Keep kwargs structure as requested (serial_number passed through)
            client = DE_MCU_SerialClient(port=port)
            kwargs = {'command': command, 'checksum_type': checksum_type, 'serial_number': serial_bytes}
            if req_data not in (None, ''):
                kwargs['req_data'] = req_data
            # perform transact (may return object or dict). We normalize serial key separately below.
            res = client.transact(**kwargs)

            # Normalize serial identifier to a consistent key (hex uppercase string) for all save_* calls
            key = None
            try:
                if isinstance(serial_bytes, (bytes, bytearray)):
                    key = serial_bytes.hex().upper()
                else:
                    key = str(serial_bytes).upper() if serial_bytes is not None else 'UNKNOWN_SERIAL'
            except Exception:
                key = 'UNKNOWN_SERIAL'

            # Extract processed_data preferentially from the response object/dict.
            # res may be an object with attribute processed_data, or a dict containing 'processed_data',
            # or an object providing to_json(). Preserve a dict form for downstream logic.
            state_value = None
            try:
                if hasattr(res, 'processed_data'):
                    state_value = res.processed_data
                elif isinstance(res, dict) and 'processed_data' in res:
                    state_value = res.get('processed_data')
                elif hasattr(res, 'to_json') and callable(getattr(res, 'to_json')):
                    state_value = res.to_json()
                elif isinstance(res, dict):
                    state_value = res
                else:
                    state_value = {'result': str(res)}
            except Exception:
                # fallback: use empty dict
                state_value = {}

            # If incoming HTTP payload provided processed_data and the response didn't include it,
            # prefer the explicit payload's processed_data so clients can simulate device responses.
            try:
                incoming_pd = data.get('processed_data') if isinstance(data, dict) else None
                if isinstance(incoming_pd, dict) and (not isinstance(state_value, dict) or not state_value):
                    state_value = incoming_pd
            except Exception:
                pass

            # ensure we have a dict for downstream logic
            if not isinstance(state_value, dict):
                state_value = {'result': state_value}

            state_data = {command.replace('_REQ', ''): state_value}

            try:
                handled = False
                save_results = []
                # detect STATUS and SETUP blocks separately
                status_block = None
                setup_block = None
                try:
                    if isinstance(state_value, dict):
                        if 'STATUS' in state_value and isinstance(state_value['STATUS'], dict):
                            status_block = state_value['STATUS']
                        else:
                            for v in state_value.values():
                                if isinstance(v, dict) and 'STATUS' in v:
                                    status_block = v.get('STATUS')
                                    break

                        if 'SETUP' in state_value and isinstance(state_value['SETUP'], dict):
                            setup_block = state_value['SETUP']
                        else:
                            for v in state_value.values():
                                if isinstance(v, dict) and 'SETUP' in v:
                                    setup_block = v.get('SETUP')
                                    break
                except Exception:
                    status_block = None
                    setup_block = None

                # dynamic policy by depth: look for depth at top-level, or inside processed_data, or inside nested dicts
                depth = None
                try:
                    if isinstance(state_value, dict) and 'depth' in state_value:
                        depth = int(state_value.get('depth'))
                    elif isinstance(state_value, dict) and 'processed_data' in state_value and isinstance(state_value.get('processed_data'), dict) and 'depth' in state_value.get('processed_data'):
                        depth = int(state_value.get('processed_data').get('depth'))
                    else:
                        # search one level deep for a dict containing 'depth'
                        if isinstance(state_value, dict):
                            for v in state_value.values():
                                if isinstance(v, dict) and 'depth' in v:
                                    try:
                                        depth = int(v.get('depth'))
                                        break
                                    except Exception:
                                        continue
                except Exception:
                    depth = None

                # If depth present, derive candidate top-level blocks (like SETUP) regardless of STATUS presence
                derived_blocks = None
                if depth is not None and isinstance(state_value, dict):
                    # exclude common metadata keys
                    meta_keys = {'depth', 'request', 'response', 'selected_node', 'Index', 'Status', 'Error_Code', 'Setup'}
                    derived = {}
                    for k, v in state_value.items():
                        if k in meta_keys:
                            continue
                        if isinstance(v, dict):
                            derived[k] = v
                    if derived:
                        # mark derived top-level blocks separately
                        derived_blocks = derived
                        # keep status_block as-is; derived_blocks will be saved as top-level sibling blocks

                try:
                    if depth is not None:
                        # depth >=3 : save per leaf (category/subkey)
                        if depth >= 3 and isinstance(status_block, dict):
                            for cat, cat_v in status_block.items():
                                if isinstance(cat_v, dict):
                                    for subk, subv in cat_v.items():
                                        try:
                                            res = save_status_path('MCUnode', key, [cat, subk], subv, command_name=command.replace('_REQ',''))
                                            save_results.append(res)
                                        except Exception:
                                            logger.exception(f'DE_MCUSerialViewSet: save_status_path failed for {cat}/{subk}')
                            handled = True
                        # depth ==2 : save per mid-category
                        elif depth == 2 and isinstance(status_block, dict):
                            for cat, cat_v in status_block.items():
                                try:
                                    res = save_status_path('MCUnode', key, [cat], cat_v, command_name=command.replace('_REQ',''))
                                    save_results.append(res)
                                except Exception:
                                    logger.exception(f'DE_MCUSerialViewSet: save_status_path failed for {cat}')
                            handled = True
                    # If derived top-level blocks exist, save them as top-level blocks (not under STATUS)
                    if derived_blocks and isinstance(derived_blocks, dict):
                        for block_name, block_value in derived_blocks.items():
                            try:
                                # use normalized key (hex string) for saving
                                if isinstance(block_name, str) and block_name.lower() == 'setup':
                                    res = save_setup('MCUnode', key, block_value, command_name=command.replace('_REQ',''))
                                else:
                                    res = save_block_top_level('MCUnode', key, block_name, block_value, command_name=command.replace('_REQ',''))
                                save_results.append(res)
                            except Exception:
                                logger.exception(f'DE_MCUSerialViewSet: save_block_top_level/save_setup failed for {block_name}')
                        handled = True
                except Exception:
                    logger.exception('DE_MCUSerialViewSet: depth-based save 예외')

                # If not handled by depth policy, try existing nested Roll case then fallback
                if not handled:
                    try:
                        # nested Position->Roll special case
                        if isinstance(status_block, dict) and 'Position' in status_block and isinstance(status_block['Position'], dict) and 'Roll' in status_block['Position']:
                            roll_kv = status_block['Position']['Roll']
                            try:
                                res = save_status_nested('MCUnode', key, 'Position', 'Roll', roll_kv, overwrite_sub_if_exists=True, command_name=command.replace('_REQ',''))
                                save_results.append(res)
                            except Exception:
                                logger.exception('DE_MCUSerialViewSet: save_status_nested failed for Position/Roll')
                            handled = True
                    except Exception:
                        logger.exception('DE_MCUSerialViewSet: nested save 검사 중 예외')

                # If not handled by previous logic, and a setup_block exists, save it explicitly
                if not handled and setup_block is not None:
                    try:
                        res = save_setup('MCUnode', key, setup_block, command_name=command.replace('_REQ',''))
                        save_results.append(res)
                        handled = True
                    except Exception:
                        logger.exception('DE_MCUSerialViewSet: save_setup failed')

                if not handled:
                    # fallback: 전체 STATUS+Meta 저장
                    try:
                        res = save_status_with_meta('MCUnode', key, command.replace('_REQ', ''), state_value)
                        save_results.append(res)
                    except Exception:
                        logger.exception('DE_MCUSerialViewSet: save_status_with_meta failed')
            except Exception:
                logger.exception('DE_MCUSerialViewSet: 상태 저장 중 오류')

            # Decide whether to persist registry to disk: only when at least one save reported a changed=True and no error
            try:
                should_persist = False
                if save_results:
                    for r in save_results:
                        try:
                            if r and isinstance(r, dict) and r.get('error') is None and r.get('changed'):
                                should_persist = True
                                break
                        except Exception:
                            continue
                if should_persist:
                    try:
                        persist_registry_state('MCUnode')
                    except Exception:
                        logger.exception('DE_MCUSerialViewSet: 즉시 상태 영구화 실패')
                else:
                    logger.debug('DE_MCUSerialViewSet: persist_registry_state skipped (no successful change)')
            except Exception:
                logger.exception('DE_MCUSerialViewSet: persist decision failed')

            # 간단한 로그
            try:
                logger.debug(f"DE_MCUSerialViewSet: serial={key} command={command} saved")
            except Exception:
                pass

            return Response(state_value, status=status.HTTP_200_OK)

        except Exception as e:
            # client.last_error 우선 사용
            err_msg = None
            try:
                if client is not None and getattr(client, 'last_error', None):
                    err_msg = client.last_error
            except Exception:
                err_msg = None

            exc_name = e.__class__.__name__ if e is not None else ''
            if err_msg or 'SerialException' in exc_name:
                return Response({'detail': err_msg or str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StateViewSet(viewsets.ViewSet):
    """Expose context_store/state.json entries for this app.

    Supports query params:
    - serial: exact serial match
    - serial_contains: substring match (case-insensitive)
    - firmware: firmware version exact match (matches STATUS->Firmware->Version)
    - last_updated_before, last_updated_after: ISO datetime strings to filter Meta.last_updated
    - ordering: 'serial' or '-serial' or 'last_updated' or '-last_updated'
    - serial_number: exact serial match (case-insensitive)
    """

    serializer_class = StateEntrySerializer

    def _load_state(self):
        try:
            # Registry 전용: 레지스트리에서 MCUnode 엔트리를 가져와 상태를 반환합니다.
            # 엔트리가 없으면 create_slave=True로 새 RegistersSlaveContext를 생성합니다.
            entry = get_or_create_registry_entry('MCUnode', create_slave=True)
            if entry is None:
                return {}

            # 1) 먼저 명시적 상태 저장소(_state)를 확인
            try:
                if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                    state = entry.get_all_state()
                    if isinstance(state, dict) and state:
                        return dict(state)
            except Exception:
                # continue to fallback checks
                pass

            # 1.5) 레지스트리가 비어있으면 디스크에서 복원 시도
            try:
                empty_state = False
                try:
                    empty_state = isinstance(state, dict) and not bool(state)
                except Exception:
                    empty_state = True
                if empty_state:
                    # Try to locate the app's context_store/state.json and load it directly into the registry
                    try:
                        app_stores = ensure_context_store_for_apps()
                        cs_path = app_stores.get('MCUnode')
                        if cs_path:
                            app_path = Path(cs_path).parent
                        else:
                            app_path = Path(__file__).resolve().parents[1]

                        state_path = Path(app_path) / 'state.json'
                        if state_path.exists():
                            try:
                                with state_path.open('r', encoding='utf-8') as sf:
                                    disk_state = json.load(sf)
                                if isinstance(disk_state, dict) and disk_state:
                                    # Populate registry entry in a best-effort, non-destructive way
                                    try:
                                        if hasattr(entry, 'set_state') and callable(getattr(entry, 'set_state')):
                                            for serial_k, v in disk_state.items():
                                                try:
                                                    entry.set_state(serial_k, v)
                                                except Exception:
                                                    pass
                                        elif isinstance(entry, dict):
                                            store = entry.setdefault('store', {})
                                            store['state'] = disk_state
                                        else:
                                            store_attr = getattr(entry, 'store', None)
                                            if isinstance(store_attr, dict):
                                                store_attr['state'] = disk_state
                                            else:
                                                try:
                                                    setattr(entry, 'store', {'state': disk_state})
                                                except Exception:
                                                    pass
                                    except Exception:
                                        logger.exception('StateViewSet: failed to apply disk state into registry entry')

                                    # After applying disk_state, attempt to read from registry API again
                                    try:
                                        if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                                            state = entry.get_all_state()
                                            if isinstance(state, dict) and state:
                                                return dict(state)
                                    except Exception:
                                        pass
                            except Exception:
                                logger.exception('StateViewSet: failed to load state.json for MCUnode')
                    except Exception:
                        logger.exception('StateViewSet: restore attempt failed')
            except Exception:
                pass

            # 2) _state가 비어있다면 종종 restore 로직에서 store['state']에 복원해 둡니다.
            try:
                store_attr = getattr(entry, 'store', None)
                if isinstance(store_attr, dict) and 'state' in store_attr and isinstance(store_attr.get('state'), dict):
                    return dict(store_attr.get('state'))
            except Exception:
                pass

            # 3) 딕셔너리형 레지스트리(fallback)
            if isinstance(entry, dict):
                try:
                    state = entry.get('store', {}).get('state', {})
                    if isinstance(state, dict):
                        return dict(state)
                except Exception:
                    pass

            return {}
        except Exception:
            logger.exception('StateViewSet: failed to load state from registry')
            return {}

    def list(self, request):
        qs = self._load_state()
        entries = []
        for serial, val in qs.items():
            obj = {'serial_number': serial}
            if isinstance(val, dict):
                obj.update(val)
            entries.append(obj)

        # Filtering
        serial = request.query_params.get('serial')
        serial_contains = request.query_params.get('serial_contains')
        serial_number = request.query_params.get('serial_number')
        firmware = request.query_params.get('firmware')
        lu_before = request.query_params.get('last_updated_before')
        lu_after = request.query_params.get('last_updated_after')

        def match_entry(e):
            # New: support serial_number param (case-insensitive exact match)
            if serial_number:
                try:
                    if str(e.get('serial_number', '')).upper() != str(serial_number).upper():
                        return False
                except Exception:
                    return False
            if serial and e.get('serial_number') != serial:
                return False
            if serial_contains and serial_contains.lower() not in e.get('serial_number', '').lower():
                return False
            if firmware:
                try:
                    fw = e.get('STATUS', {}).get('Firmware', {}).get('Version') if isinstance(e.get('STATUS'), dict) else None
                    if fw != firmware:
                        return False
                except Exception:
                    return False
            if lu_before or lu_after:
                try:
                    lu = e.get('Meta', {}).get('last_updated')
                    if not lu:
                        return False
                    dt = _iso_parse(lu)
                    if lu_before:
                        dt_before = _iso_parse(lu_before)
                        if not (dt < dt_before):
                            return False
                    if lu_after:
                        dt_after = _iso_parse(lu_after)
                        if not (dt > dt_after):
                            return False
                except Exception:
                    return False
            return True

        filtered = [e for e in entries if match_entry(e)]

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering:
            reverse = ordering.startswith('-')
            key = ordering.lstrip('-')
            if key == 'serial':
                filtered.sort(key=lambda x: x.get('serial_number', ''), reverse=reverse)
            elif key == 'last_updated':
                def _lu_key(x):
                    try:
                        return _iso_parse(x.get('Meta', {}).get('last_updated'))
                    except Exception:
                        return None
                filtered.sort(key=lambda x: (_lu_key(x) is None, _lu_key(x)), reverse=reverse)

        serializer = self.serializer_class(filtered, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        # pk is serial identifier
        qs = self._load_state()
        serial = pk
        if serial is None:
            return Response({'detail': 'serial pk required'}, status=status.HTTP_400_BAD_REQUEST)
        entry = qs.get(serial.upper()) or qs.get(serial)  # try uppercase key then raw
        if entry is None:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        obj = {'serial_number': serial}
        if isinstance(entry, dict):
            obj.update(entry)
        serializer = self.serializer_class(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
