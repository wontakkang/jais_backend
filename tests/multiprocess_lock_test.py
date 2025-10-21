# 간단한 멀티프로세스 락 검증 스크립트
import time
import random
import json
from multiprocessing import Process, current_process
from pathlib import Path

from utils.protocol.context.manager import create_or_update_slave_context

APP_NAME = 'LSISsocket'
HOST = '127.0.0.1'
PORT = 2004
ITERATIONS = 8
PROCESSES = 6

def worker(proc_index: int):
    name = current_process().name
    for i in range(ITERATIONS):
        try:
            # vary count so payloads differ
            count = 10 + proc_index * 5 + i
            ok = create_or_update_slave_context(APP_NAME, HOST, PORT, memory_creator='LS_XGT_TCP', memory_kwargs={'count': count, 'use_json': True}, persist=True)
            print(f"{name} iter={i} wrote ok={ok} count={count}")
        except Exception as e:
            print(f"{name} iter={i} exception: {e}")
        # small random sleep to increase race chance
        time.sleep(random.uniform(0.01, 0.1))

def main():
    procs = []
    for p in range(PROCESSES):
        proc = Process(target=worker, args=(p,), name=f'P{p}')
        proc.start()
        procs.append(proc)
    for proc in procs:
        proc.join()

    cs_path = Path(r'D:/project/projects/jais/py_backend/LSISsocket/context_store')
    state_file = cs_path / 'state.json'
    tmp_files = list(cs_path.glob('*.tmp'))
    lock_files = list(cs_path.glob('*.lock'))
    result = {'state_exists': state_file.exists(), 'tmp_files': [str(p.name) for p in tmp_files], 'lock_files': [str(p.name) for p in lock_files]}
    print('Post-run check:', result)
    if state_file.exists():
        try:
            with state_file.open('r', encoding='utf-8') as f:
                obj = json.load(f)
            print('state.json valid JSON. top keys:', list(obj.keys())[:10])
            # inspect MEMORY for our host:port
            key = f"{HOST}:{PORT}"
            if key in obj and isinstance(obj[key], dict):
                mem = obj[key].get('MEMORY')
                if isinstance(mem, dict):
                    for mem_name, mem_obj in mem.items():
                        if isinstance(mem_obj, dict) and 'values' in mem_obj:
                            vals = mem_obj['values']
                            if isinstance(vals, list):
                                print(f"{mem_name} values list length: {len(vals)}")
                            elif isinstance(vals, dict):
                                print(f"{mem_name} values dict size: {len(vals)}")
                        elif isinstance(mem_obj, list):
                            print(f"{mem_name} is top-level list length: {len(mem_obj)}")
        except Exception as e:
            print('Failed to parse state.json:', e)

if __name__ == '__main__':
    main()
