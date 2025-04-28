import os
import sys
from asgiref.sync import sync_to_async
from ..utils.protocol.LSIS import LSIS_TcpClient

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