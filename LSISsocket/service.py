# -*- coding: utf-8 -*-
from datetime import datetime
from main import django
from utils.logger import log_exceptions
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from asgiref.sync import sync_to_async
from utils import setup_logger
from utils.protocol.LSIS.utilities import LSIS_MappingTool
from django.utils import timezone

logger = setup_logger('LSISsocket', './log/LSISsocket.log')

sockets = []

@log_exceptions(logger)
def tcp_client_servive(client):
    global sockets
    is_existed = False
    connect_sock = None
    from LSISsocket.models import SocketClientStatus  # django.setup() 이후 import
    try:
        socketValue = []
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
        for block in client.blocks:
            block_value = {}
            response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
            now = timezone.now()
            if len(block.get('groups')) == 0:
                pass
            for group in block.get('groups'):
                for var in group.get('variables'):
                    lsmt = LSIS_MappingTool(**var)
                    start_address = group.get('start_address')*2
                    end_address = group.get('start_address')*2+group.get('size_byte')
                    data = lsmt.repack(response.values[start_address:end_address])
                    block_value.update({
                        f"{group['name']}:{group['project_id']}:{block['parentId']}:{block['blockId']}:{group['group_id']}:{var['name']}": 
                        {
                            "value": data,
                            "label": {
                                "type": group["name"],
                                "project_id": group["project_id"],
                                "parent_id": block["parentId"],
                                "block_id": block["blockId"],
                                "group_id": group["group_id"],
                                "variable": var["name"],
                                "attributes": sorted(var['attributes']),
                            },
                        }
                    })
            socketValue.append(block_value)
            if hasattr(response, 'detailedStatus'):
                detailed_status = response.detailedStatus
            else:
                detailed_status = {
                    "SYSTEM STATUS": "Timeout",
                    "ERROR CODE": 999,
                    "message": response.message,
                }
            object = SocketClientStatus.objects.get_or_create(config_id=client.id)
            if object:
                SocketClientStatus.objects.filter(
                    config_id=client.id
                ).update(
                    detailedStatus=detailed_status,
                    error_code=detailed_status.get("ERROR CODE", 0),
                    message=detailed_status.get("message", ""),
                    values=socketValue,
                    updated_at=now
                )
    except Exception as e:
        now = timezone.now()
        for sock in sockets:
            if sock.params.host == client.host and sock.params.port == client.port:
                if not is_existed:
                    sock.close()
                    sockets.remove(sock)
                    logger.error(f'cancel to connect LSIS client => {client.host}:{client.port}')
                break
        logger.error(f'tcp_client_servive : {e}')
        detailed_status = {
            "SYSTEM STATUS": "Timeout",
            "ERROR CODE": 999,
            "message": str(e),
        }
        object = SocketClientStatus.objects.get_or_create(config_id=client.id)