# -*- coding: utf-8 -*-
from datetime import datetime
import time
from LSISsocket.serializers import MemoryGroupSerializer, SocketClientConfigSerializer
from main import django
from utils.calculation import all_dict as calculation_methods
from utils.logger import log_exceptions, log_execution_time
import logging
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from utils.protocol.LSIS.utilities import LSIS_MappingTool

from LSISsocket.models import MemoryGroup, SocketClientConfig, SocketClientStatus
from django.utils import timezone
from pathlib import Path
from . import logger, redis_instance
from corecode import redis_instance as corecode_redis_instance
import re
import json

sockets = []

@log_exceptions(logger)
def tcp_client_to_redis(client):
    global sockets
    connect_sock = None
    try:
        try:
            from main import STOP_EVENT as _STOP_EVENT
        except Exception:
            _STOP_EVENT = None
        try:
            if (_STOP_EVENT is not None and _STOP_EVENT.is_set()):
                logger.info(f'tcp_client_servive: shutdown detected after connect; closing socket {client.host}:{client.port}')
                try:
                    if (connect_sock is not None):
                        connect_sock.close()
                except Exception:
                    pass
                return
        except Exception:
            pass
        if (len(sockets) == 0):
            logger.info(f'try to connect LSIS client => {client.host}:{client.port}')
            default_setting = {'reconnect_delay': 1000, 'reconnect_delay_max': 60000, 'retry_on_empty': True}
            connect_sock = LSIS_TcpClient(client.host, client.port, **default_setting)
            is_connected = connect_sock.connect(retry_forever=False)
            if is_connected:
                sockets.append(connect_sock)
                created_here = True
                if (not redis_instance.exists(f'{client.host}:{client.port}')):
                    redis_instance.hmset(f'{client.host}:{client.port}', mapping={'host': client.host, 'port': client.port, 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(), '%MB': ([0] * 20000), '%RW': ([0] * 20000), '%WW': ([0] * 20000)})
        from types import SimpleNamespace
        for sock in sockets:
            if ((sock.params.host == client.host) and (sock.params.port == client.port)):
                try:
                    for block in client.blocks:
                        try:
                            total_count = int(block.get('count', 0))
                        except Exception:
                            total_count = 0
                        try:
                            start_addr = int(block.get('address', 0))
                        except Exception:
                            start_addr = 0
                        memory = block.get('memory', '')
                        func_name = block.get('func_name')
                        func = getattr(sock, func_name, None)
                        if (func is None):
                            logger.warning(f"LSISsocket: socket has no read function '{func_name}', skipping block")
                            continue
                        read_count = 0
                        response_vals = []
                        while (read_count < total_count):
                            current_count = min(700, (total_count - read_count))
                            addr = (start_addr + read_count)
                            args = [f'{memory}{addr}', current_count]
                            try:
                                partial_response = func(*args)
                            except Exception as e:
                                had_error = True
                                error_msg = str(e)
                                logger.exception(f'Error reading block {args} at offset {addr}, count {current_count}')
                                break
                            try:
                                vals = getattr(partial_response, 'values', None)
                                if (vals is None):
                                    logger.warning(f'partial_response({args} at offset, count {current_count}) has no attribute values or it is None; skipping this chunk ')
                                else:
                                    if (not isinstance(vals, (list, tuple))):
                                        try:
                                            vals = list(vals)
                                        except Exception:
                                            vals = [vals]
                                    response_vals.extend(vals)
                            except Exception as e:
                                logger.exception(f'Error processing partial response values: {e}')
                                had_error = True
                                error_msg = str(e)
                                break
                            read_count += current_count
                            time.sleep(0.025)
                        response = SimpleNamespace(values=response_vals)
                        get_memory = redis_instance.hget(f'{client.host}:{client.port}', memory)
                        if (get_memory is not None):
                            get_memory[start_addr:(start_addr + len(response.values))] = response.values
                            redis_instance.hset(f'{client.host}:{client.port}', memory, get_memory)
                except Exception as e:
                    logger.error(f'Error during initial read for context store persistence: {e}')
            else:
                logger.info(f'try to connect LSIS client => {client.host}:{client.port}')
                default_setting = {'reconnect_delay': 1000, 'reconnect_delay_max': 60000, 'retry_on_empty': True, 'timeout': 60}
                connect_sock = LSIS_TcpClient(client.host, client.port, **default_setting)
                try:
                    connect_sock.connect(retry_forever=False)
                except Exception as e:
                    logger.exception('Error connecting to socket')
                logger.debug(getattr(connect_sock, '_connected', None))
                sockets.append(connect_sock)
                if (not redis_instance.exists(f'{client.host}:{client.port}')):
                    redis_instance.hmset(f'{client.host}:{client.port}', mapping={'host': client.host, 'port': client.port, 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(), '%MB': ([0] * 100000)})
    finally:
        redis_instance.hset(f'{client.host}:{client.port}', 'updated_at', datetime.now().isoformat())  
        try:
            if hasattr(partial_response, 'detailedStatus'):
                detailed_status = partial_response.detailedStatus
            else:
                detailed_status = {'SYSTEM STATUS': 'Timeout', 'ERROR CODE': 999, 'message': partial_response.message}
            status_instance = SocketClientStatus.objects.get(config_id=client.id)
            status_instance.detailedStatus = detailed_status
            status_instance.error_code = detailed_status.get("ERROR CODE", 0)
            status_instance.message = detailed_status.get("message", "")
            status_instance.updated_at = timezone.now()
            status_instance.save()
            reids_to_memory_mapping(client)
        except SocketClientStatus.DoesNotExist:
            logger.error(f'{__name__} : config_id {client.id}를 가진 SocketClientStatus가 존재하지 않습니다')
            detailed_status = {
                'SYSTEM STATUS': 'Timeout',
                'ERROR CODE': 999,
                'message': f'config_id {client.id}를 가진 SocketClientStatus가 존재하지 않습니다'
            }
            status_instance = SocketClientStatus.objects.get(config_id=client.id)
            status_instance.detailedStatus = detailed_status
            status_instance.error_code = detailed_status.get("ERROR CODE", 0)
            status_instance.message = detailed_status.get("message", "")
            status_instance.updated_at = timezone.now()
            status_instance.save()
        except UnboundLocalError as e:
            logger.error(f'{__name__} : 응답없음 발생 : {e}')
            detailed_status = {
                'SYSTEM STATUS': 'Timeout',
                'ERROR CODE': 999,
                'message': f'응답없음 발생'
            }
            status_instance = SocketClientStatus.objects.get(config_id=client.id)
            status_instance.detailedStatus = detailed_status
            status_instance.error_code = detailed_status.get("ERROR CODE", 0)
            status_instance.message = detailed_status.get("message", "")
            status_instance.updated_at = timezone.now()
            status_instance.save()
        except Exception as e:
            logger.error(f'{__name__} : Error updating SocketClientStatus: {e}')
            detailed_status = {
                'SYSTEM STATUS': 'Timeout',
                'ERROR CODE': 999,
                'message': f'알수없는 문제 발생'
            }
            status_instance = SocketClientStatus.objects.get(config_id=client.id)
            status_instance.detailedStatus = detailed_status
            status_instance.error_code = detailed_status.get("ERROR CODE", 0)
            status_instance.message = detailed_status.get("message", "")
            status_instance.updated_at = timezone.now()
            status_instance.save()


@log_exceptions(logger)
def reids_to_memory_mapping(client):
    # /LSISsocket/client-configs/id=client_id로 직렬화기의 값을 가져오기
    try:
        bulk_data = {}
        configs = []
        MB = redis_instance.hget(name=f'{client.host}:{client.port}', key='%MB')
        # client가 단일 모델 인스턴스인 경우
        if isinstance(client, SocketClientConfig):
            serializer = SocketClientConfigSerializer(client)
            configs = serializer.data
        memory_groups = configs.get('memory_groups_detail', [])
        memory_bulk_data = {}
        for group in memory_groups:
            for key in group:
                if key == 'variables':
                    for mem in group.get('variables'):
                        try:
                            LMT = LSIS_MappingTool(**mem)
                            _value = LMT.repack(MB)
                            if type(_value).__name__ == 'float':
                                _value= float("{:.3f}".format(round(_value, 3)))
                            # Redis에 변수별 속성(JSON 배열) 저장
                            try:
                                key = f"{configs.get('id', None)}:{mem.get('id', None)}"
                                memory_bulk_data[key] = _value
                            except Exception as _e:
                                logger.debug(f'Attribute save failed for var {mem.get("id")}: {_e}')
                        except Exception as e:
                            logger.error(f'Error creating LSIS_MappingTool for memory variable {mem}: {e}')
        calc_groups = configs.get('calc_groups_detail', [])
        calc_bulk_data = {}
        for group in calc_groups:
            for key in group:
                if key == 'variables':
                    for mem in group.get('variables'):
                        args_values = []
                        try:
                            for arg in mem.get('args', []):
                                args_values.append(memory_bulk_data[f"{configs.get('id', None)}:{arg}"])
                            key = f"{configs.get('id', None)}:{mem.get('id', None)}"
                            calc_bulk_data[key] = calculation_methods.get(mem.get('name').get('use_method'))(*args_values)
                        except Exception as _e:
                            logger.debug(f'Attribute save failed for var {mem.get("id")}: {_e}')
        bulk_data.update(memory_bulk_data)
        bulk_data.update(calc_bulk_data)
        corecode_redis_instance.bulk_update(bulk_data)
    except Exception as err:
        logger.error(f'Error fetching memory-groups serializer data: {err}')
        configs = []
    
    
@log_exceptions(logger)
def setup_variables_to_redis(group=None):
    memory_bulk_data = {}
    setup_varialbes = group.get('variables', [])
    for id in setup_varialbes:
        try:
            key = f"{group.id}:{id}"
            memory_bulk_data[key] = None
        except Exception as _e:
            logger.debug(f'Attribute save failed for var {id}: {_e}')