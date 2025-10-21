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
from utils.protocol.context.manager import restore_json_blocks_to_slave_context
from utils.protocol.context.manager import create_or_update_slave_context
try:
    app_name = getattr(LSISsocketConfig, 'name', 'LSISsocket')
except Exception:
    app_name = 'LSISsocket'

logger = setup_logger('LSISsocket', './log/LSISsocket.log')

sockets = []

@log_exceptions(logger)
def tcp_client_servive(client):
    
    app_path = Path(r'D:\project\projects\jais\py_backend\LSISsocket')
    cs_path = app_path / 'context_store'
    cs_path.mkdir(parents=True, exist_ok=True)
    slave_ctx = RegistersSlaveContext(create_memory='create_ls_xgt_tcp_memory', count=20000, use_json=True)
    restored = restore_json_blocks_to_slave_context(app_path, slave_ctx, load_most_recent=True)
    CONTEXT_REGISTRY[app_name] = slave_ctx
    
    global sockets
    is_existed = False
    connect_sock = None
    
    if len(sockets) > 0:
        for sock in sockets:
            if sock.params.host == client.host and sock.params.port == client.port:
                is_existed = True
                connect_sock = sock
                break
    if not is_existed:
        logger.info(f'try to connect LSIS client => {client.host}:{client.port}')
        connect_sock = LSIS_TcpClient(client.host, client.port, timeout=60)
        connect_sock.connect(retry_forever=False)
        sockets.append(connect_sock)
        # Persist a SlaveContext entry for this client into context_store/state.json
        try:
            create_or_update_slave_context(
                "LSISsocket",
                client.host,
                client.port,
                memory_creator="LS_XGT_TCP",
                memory_kwargs={"count": 20000, "use_json": True},
                persist=True,
            )
            logger.info(f'Persisted slave context for {client.host}:{client.port} to state.json')
        except Exception:
            logger.exception(f'Failed to persist slave context for {client.host}:{client.port}')
    for block in client.blocks:
        try:
            logger.debug(f'LSISsocket service read block => {block})')
            response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{0}", 700)
            CONTEXT_REGISTRY[app_name].setValues(memory=block["memory"], address=int(0), values=response.values)
            
            if block['count'] <= 700:
                response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
            elif block['count'] > 700:
                total_count = block['count']
                read_count = 0
                response = []
                while read_count < total_count:
                    current_count = min(700, total_count - read_count)
                    logger.debug(f'LSISsocket service read block partial => {int(block['address']) + read_count}, read_count: {current_count})')
                    partial_response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{int(block['address']) + read_count}", current_count)
                    response.extend(partial_response.values)
                    read_count += current_count
        except Exception as e:
            logger.error(f'Error reading block {block}: {e}')
                
                
    #             if response is None:
    #                 response = partial_response
    #             else:
    #                 response.values.extend(partial_response.values)
    #             read_count += current_count
        
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