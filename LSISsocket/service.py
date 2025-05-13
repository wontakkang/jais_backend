# -*- coding: utf-8 -*-
from main import django
from utils.logger import log_exceptions
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from asgiref.sync import sync_to_async
from utils import setup_logger
from utils.protocol.LSIS.utilities import LSIS_MappingTool

logger = setup_logger('LSISsocket', './log/LSISsocket.log')

sockets = []

@log_exceptions(logger)
def tcp_client_servive(client):
    global sockets
    is_existed = False
    connect_sock = None
    from LSISsocket.models import SocketClientStatus  # django.setup() 이후 import
    try:
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
            response = getattr(connect_sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
            # response.values
            for block in client.blocks:
                print(f"address :{block.get('memory')} {block.get('address')} {block.get('count')}")
                for group in block.get('groups'):
                    print(group.get('start_address'), group.get('size_byte'))
                    for var in group.get('variables'):
                        print(f"var :{var}")
                        memoryIndex = group.get('start_address') + var.get('address')
                        print(f"value : {response.values[memoryIndex]}")
                        
                        #data_type이 int8, int16, int32, uint8, uint16, uint32으로 수정
                        
                        # LSIS_MappingTool
            # identifier, address, scale, _min, _max, status_able, log_able, write_able, alert_able, cat_name, name = value
            # # 채널의 식별자와 매핑된 식별자 비교
            # if ch_params['identifier'] == 'memory':
            #     lmt = LSIS_MappingTool(*value)
            # response = connect_sock.read_bytes(block['memory'], block['address'], block['count'])
                        
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
                    values=response.values
                )
    except Exception as e:
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
        if object:
            SocketClientStatus.objects.filter(
                config_id=client.id
            ).update(
                detailedStatus=detailed_status,
                error_code=detailed_status.get("ERROR CODE", 0),
                message=detailed_status.get("message", ""),
                values=response.values
            )
