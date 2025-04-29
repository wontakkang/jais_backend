import time
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from fastapi import HTTPException
from asgiref.sync import sync_to_async
from .models import SocketClientCommand, SocketClientConfig

async def tcp_client_servive(client):
        sock = LSIS_TcpClient(host=client.host, port=client.port)
        try:
            sock.connect(retry_forever=False)
            for block in client.blocks:
                response = getattr(sock, block['func_name'])(f"{block['memory']}{block['address']}", block['count'])
                client.detailedStatus = response.detailedStatus
                await sync_to_async(client.save)()
        except Exception as e:
            client.detailedStatus = {
                "SYSTEM STATUS": "Timeout",
                "ERROR CODE": 999,
                "message": str(e),
            }
            await sync_to_async(client.save)()
            
def lsis_init_and_reset(host, port, user=None):
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

