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

def lsis_init_and_reset(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        client.send_stop()
        response = client.send_reset()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='init_reset',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='초기 통신 및 리셋 명령 전송',
        )
        return {"detail": "초기 통신 및 리셋 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='init_reset',
            value='failure",',
            response=str(e),
            payload={'host': host, 'port': port},
            message='init_reset 명령 전송 실패',
        )
        return {"detail": "init_reset 명령 전송 실패", "error": str(e)}

def lsis_stop(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        response = client.send_stop()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='stop',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='STOP 명령 전송',
        )
        return {"detail": "STOP 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='stop',
            value='failure",',
            response=str(e),
            payload={'host': host, 'port': port},
            message='STOP 명령 전송 실패',
        )
        return {"detail": "STOP 명령 전송 실패", "error": str(e)}


def lsis_run(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        response = client.send_start()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='run',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='RUN 명령 전송 완료',
        )
        return {"detail": "RUN 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='run',
            value='failure",',
            response=str(e),
            payload={'host': host, 'port': port},
            message='RUN 명령 전송 실패',
        )
        return {"detail": "RUN 명령 전송 실패", "error": str(e)}

