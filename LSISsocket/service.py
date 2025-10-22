# -*- coding: utf-8 -*-
from datetime import datetime
import time
from main import django
from utils.calculation import all_dict as calculation_methods
from utils.logger import log_exceptions
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from asgiref.sync import sync_to_async
from utils import setup_logger
from utils.protocol.LSIS.utilities import LSIS_MappingTool
from django.utils import timezone
from pathlib import Path

from utils.protocol.context import BaseSlaveContext, CONTEXT_REGISTRY, RegistersSlaveContext
from LSISsocket.apps import LSISsocketConfig
from utils.protocol.context.manager import _sync_registry_state, restore_json_blocks_to_slave_context
from utils.protocol.context.manager import create_or_update_slave_context
try:
    app_name = getattr(LSISsocketConfig, 'name', 'LSISsocket')
except Exception:
    app_name = 'LSISsocket'

logger = setup_logger('LSISsocket', './log/LSISsocket.log')

sockets = []

@log_exceptions(logger)
async def tcp_client_servive(client):
    global sockets
    # Try to import STOP_EVENT lazily to avoid circular import at module import time
    try:
        from main import STOP_EVENT as _STOP_EVENT
    except Exception:
        _STOP_EVENT = None

    # If shutdown already requested, skip work
    try:
        if _STOP_EVENT is not None and _STOP_EVENT.is_set():
            logger.info(f'tcp_client_servive: shutdown requested, skipping client {client.host}:{client.port}')
            return
    except Exception:
        pass

    connect_sock = None
    is_existed = False
    if len(sockets) > 0:
        for sock in sockets:
            is_existed = False
            if sock.params.host == client.host and sock.params.port == client.port:
                is_existed = True
                connect_sock = sock
                break
    if not is_existed:
        logger.info(f'try to connect LSIS client => {client.host}:{client.port}')
        connect_sock = LSIS_TcpClient(client.host, client.port, timeout=60)
        connect_sock.connect(retry_forever=False)
        sockets.append(connect_sock)

        # If shutdown requested immediately after connect, close and exit quickly
        try:
            if _STOP_EVENT is not None and _STOP_EVENT.is_set():
                logger.info(f'tcp_client_servive: shutdown detected after connect; closing socket {client.host}:{client.port}')
                try:
                    connect_sock.close()
                except Exception:
                    pass
                return
        except Exception:
            pass

        # Persist a SlaveContext entry for this client into context_store/state.json
        try:
            create_or_update_slave_context(
                "LSISsocket",
                client.host,
                client.port,
                memory_creator="LS_XGT_TCP",
                memory_kwargs={"count": 20000, "use_json": True},
                persist=False,
            )
            # CONTEXT_REGISTRY[app_name]에 SlaveContext에 key=f"{client.host}:{client.port}"인 상태에서 blocks이라는 하위 키 생성하고 client.blocks 할당
                     
            memory = CONTEXT_REGISTRY[app_name].get_state(f"{client.host}:{client.port}")
            memory['blocks'] = client.blocks
            response = []
            # _sync_registry_state(app_name=app_name, serial=f"{client.host}:{client.port}", entry_obj=memory)  
            for block in client.blocks:
                logger.debug(f"LSISsocket service read block => {block}")
                try:
                    total_count = int(block.get('count', 0))
                except Exception:
                    total_count = 0
                try:
                    read_count = int(block.get('address', 0))
                except Exception:
                    read_count = 0
                response = []
                while read_count < total_count:
                    current_count = min(700, total_count - read_count)
                    args = [
                        f"{block.get('memory','')}{read_count}",
                        current_count
                    ]
                    try:
                        func_name = block.get('func_name')
                        func = getattr(connect_sock, func_name, None)
                        if func is None:
                            logger.error(f"LSISsocket: connect_sock has no attribute '{func_name}'")
                            break
                        partial_response = func(*args)
                    except Exception:
                        logger.exception('Error calling read function on connect_sock, aborting this block')
                        break

                    # 방어적 주소 표시 및 로깅
                    try:
                        try:
                            addr_display = int(block.get('address', 0)) + read_count
                        except Exception:
                            addr_display = read_count
                        logger.debug(f"LSISsocket service read block partial done => {addr_display}, read_count: {read_count}, current_count: {current_count}")
                    except Exception:
                        # 로깅 실패는 치명적이지 않으므로 무시
                        pass

                    # partial_response.values 안전하게 확장
                    try:
                        vals = getattr(partial_response, 'values', None)
                        if vals is None:
                            logger.warning('partial_response has no attribute values or it is None')
                        elif not isinstance(vals, (list, tuple)):
                            logger.warning('partial_response.values is not a list/tuple, skipping extend')
                        else:
                            try:
                                logger.debug(f"LSISsocket partial response values => {vals[:5]}... (total {len(vals)})")
                            except Exception:
                                # 길이 파악이나 슬라이싱이 실패할 경우에도 값을 확장
                                logger.debug('LSISsocket partial response values => (unable to display sample)')
                            response.extend(vals)
                    except Exception as e:
                        logger.error(f'Error extending response values: {e}')

                    read_count += current_count
        
            logger.info(f'Persisted slave context for {client.host}:{client.port} {CONTEXT_REGISTRY[app_name].get_state(f"{client.host}:{client.port}").keys()} to state.json')
        except Exception:
            logger.exception(f'Failed to persist slave context for {client.host}:{client.port}')
            
    for sock in sockets:
        logger.debug(f'LSISsocket CONTEXT_REGISTRY => {sock}') 
        
    # for block in client.blocks:
    #     logger.debug(f"LSISsocket service read block => {block}")
    #     try:
    #         total_count = int(block.get('count', 0))
    #     except Exception:
    #         total_count = 0
    #     try:
    #         read_count = int(block.get('address', 0))
    #     except Exception:
    #         read_count = 0
    #     response = []
    #     while read_count < total_count:
    #         current_count = min(700, total_count - read_count)
    #         args = [
    #             f"{block.get('memory','')}{read_count}",
    #             current_count
    #         ]
    #         try:
    #             func_name = block.get('func_name')
    #             func = getattr(connect_sock, func_name, None)
    #             if func is None:
    #                 logger.error(f"LSISsocket: connect_sock has no attribute '{func_name}'")
    #                 break
    #             partial_response = func(*args)
    #         except Exception:
    #             logger.exception('Error calling read function on connect_sock, aborting this block')
    #             break

    #         # 방어적 주소 표시 및 로깅
    #         try:
    #             try:
    #                 addr_display = int(block.get('address', 0)) + read_count
    #             except Exception:
    #                 addr_display = read_count
    #             logger.debug(f"LSISsocket service read block partial done => {addr_display}, read_count: {read_count}, current_count: {current_count}")
    #         except Exception:
    #             # 로깅 실패는 치명적이지 않으므로 무시
    #             pass

    #         # partial_response.values 안전하게 확장
    #         try:
    #             vals = getattr(partial_response, 'values', None)
    #             if vals is None:
    #                 logger.warning('partial_response has no attribute values or it is None')
    #             elif not isinstance(vals, (list, tuple)):
    #                 logger.warning('partial_response.values is not a list/tuple, skipping extend')
    #             else:
    #                 try:
    #                     logger.debug(f"LSISsocket partial response values => {vals[:5]}... (total {len(vals)})")
    #                 except Exception:
    #                     # 길이 파악이나 슬라이싱이 실패할 경우에도 값을 확장
    #                     logger.debug('LSISsocket partial response values => (unable to display sample)')
    #                 response.extend(vals)
    #         except Exception as e:
    #             logger.error(f'Error extending response values: {e}')

    #         read_count += current_count
    
        
    from LSISsocket.models import SocketClientStatus  # django.setup() 이후 import
    socketValue = {}
    #     block_value = {}
    #     socket_key = f"{block['parentId']}:{block['blockId']}"
    #     response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
    #     now = timezone.now()
    #     if len(block.get('groups')) == 0:
    #         pass
    #     for group in block.get('groups'):
    #         for var in group.get('variables'):
    #             lsmt = LSIS_MappingTool(**var)
    #             start_address = group.get('start_address')*2
    #             end_address = group.get('start_address')*2+group.get('size_byte')
    #             data = lsmt.repack(response.values[start_address:end_address])
    #             var_key = f"{group['name']}:{group['project_id']}:{socket_key}:{group['group_id']}:{var['name']}"
    #             block_value[var_key] = {
    #                 "key": var_key,
    #                 "value": data,
    #                 "label": {
    #                     "type": group["name"],
    #                     "project_id": group["project_id"],
    #                     "parent_id": block["parentId"],
    #                     "block_id": block["blockId"],
    #                     "group_id": group["group_id"],
    #                     "variable": var["name"],
    #                     "attributes": sorted(var['attributes']),
    #                 },
    #             }
    #     socketValue[socket_key] = block_value
    #     if len(block.get('calc_groups')) == 0:
    #         pass
    #     for calc_group in block.get('calc_groups'):
    #         args = {}
    #         for var in calc_group.get('variables'):
    #             for key, var_key in var.get('args').items():
    #                 args[key] = socketValue[socket_key][f"{var_key}"].get('value')
    #             if var.get('use_method') in calculation_methods:
    #                 var_key = f"{calc_group['name']}:{calc_group['project_id']}:{socket_key}:{calc_group['group_id']}:{var['name']}"
    #                 socketValue[socket_key][var_key] = {
    #                 "key": var_key,
    #                 "value": calculation_methods.get(var.get('use_method'))(**args),
    #                 "label": {
    #                     "type": calc_group["name"],
    #                     "project_id": calc_group["project_id"],
    #                     "parent_id": block["parentId"],
    #                     "block_id": block["blockId"],
    #                     "group_id": calc_group["group_id"],
    #                     "variable": var["name"],
    #                     "attributes": sorted(var['attributes']),
    #                 },
    #             }
    #     if hasattr(response, 'detailedStatus'):
    #         detailed_status = response.detailedStatus
    #     else:
    #         detailed_status = {
    #             "SYSTEM STATUS": "Timeout",
    #             "ERROR CODE": 999,
    #             "message": response.message,
    #         }
    #     object = SocketClientStatus.objects.get_or_create(config_id=client.id)
    #     if object:
    #         SocketClientStatus.objects.filter(
    #             config_id=client.id
    #         ).update(
    #             detailedStatus=detailed_status,
    #             error_code=detailed_status.get("ERROR CODE", 0),
    #             message=detailed_status.get("message", ""),
    #             values=socketValue,
    #             updated_at=now
    #         )
    # except Exception as e:
    #     now = timezone.now()
    #     for sock in sockets:
    #         if sock.params.host == client.host and sock.params.port == client.port:
    #             if not is_existed:
    #                 sock.close()
    #                 sockets.remove(sock)
    #                 logger.error(f'cancel to connect LSIS client => {client.host}:{client.port}')
    #             break
    #     detailed_status = {
    #         "SYSTEM STATUS": "Timeout",
    #         "ERROR CODE": 999,
    #         "message": str(e),
    #     }
    #     object = SocketClientStatus.objects.get_or_create(config_id=client.id)