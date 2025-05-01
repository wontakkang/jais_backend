# -*- coding: utf-8 -*-
from main import django
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from asgiref.sync import sync_to_async

def tcp_client_servive(sock, client):
    from LSISsocket.models import SocketClientStatus  # django.setup() 이후 import
    try:
        sock.connect(retry_forever=False)
        for block in client.blocks:
            response = getattr(sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
            if hasattr(response, 'detailedStatus'):
                detailed_status = response.detailedStatus
            else:
                detailed_status = {
                    "SYSTEM STATUS": "Timeout",
                    "ERROR CODE": 999,
                    "message": response.message,
                }
            object = SocketClientStatus.objects.get(config_id=client.id)
            if object:
                SocketClientStatus.objects.filter(
                    config_id=client.id
                ).update(
                    detailedStatus=detailed_status,
                    error_code=detailed_status.get("ERROR CODE", 0),
                    message=detailed_status.get("message", "")
                )
    except Exception as e:
        detailed_status = {
            "SYSTEM STATUS": "Timeout",
            "ERROR CODE": 999,
            "message": str(e),
        }
        object = SocketClientStatus.objects.get(config_id=client.id)
        if object:
            SocketClientStatus.objects.filter(
                config_id=client.id
            ).update(
                detailedStatus=detailed_status,
                error_code=detailed_status.get("ERROR CODE", 0),
                message=detailed_status.get("message", "")
            )
