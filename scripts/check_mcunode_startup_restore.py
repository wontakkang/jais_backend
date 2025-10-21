from pathlib import Path
import os
import sys
import json

this = Path(__file__).resolve()
proj_root = str(this.parent.parent)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'py_backend.settings')
import django
django.setup()

from utils.protocol.context.scheduler import restore_contexts
from utils.protocol.context.manager import get_or_create_registry_entry, restore_json_blocks_to_slave_context, ensure_context_store_for_apps
from MCUnode.views import StateViewSet

# Step 1: run global restore_contexts()
try:
    rr = restore_contexts()
    print('restore_contexts returned:', rr)
except Exception as e:
    print('restore_contexts failed:', e)

# Step 2: perform MCUnode startup restore as in main.py
entry = get_or_create_registry_entry('MCUnode', create_slave=True)
state_ok = False
if entry is not None:
    try:
        if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
            cur = entry.get_all_state()
            if isinstance(cur, dict) and cur:
                state_ok = True
    except Exception:
        state_ok = False

if not state_ok:
    app_stores = ensure_context_store_for_apps()
    cs = app_stores.get('MCUnode')
    app_path = Path(cs).parent if cs else Path(__file__).resolve().parents[1]
    # try block-based restore
    try:
        restore_json_blocks_to_slave_context(app_path, entry, load_most_recent=True, use_key_as_memory_name=True)
        print('restore_json_blocks_to_slave_context attempted')
    except Exception as e:
        print('restore_json_blocks_to_slave_context failed:', e)
    # aggregated state.json
    still_empty = True
    try:
        if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
            cur2 = entry.get_all_state()
            if isinstance(cur2, dict) and cur2:
                still_empty = False
    except Exception:
        still_empty = True

    if still_empty:
        state_path = Path(app_path) / 'state.json'
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as sf:
                    disk_state = json.load(sf)
            except Exception as e:
                disk_state = None
                print('failed to load aggregated state.json:', e)
            if isinstance(disk_state, dict) and disk_state:
                try:
                    if hasattr(entry, 'set_state') and callable(getattr(entry, 'set_state')):
                        for serial_k, v in disk_state.items():
                            try:
                                entry.set_state(serial_k, v)
                            except Exception:
                                pass
                    elif isinstance(entry, dict):
                        store = entry.setdefault('store', {})
                        store['state'] = disk_state
                    else:
                        store_attr = getattr(entry, 'store', None)
                        if isinstance(store_attr, dict):
                            store_attr['state'] = disk_state
                        else:
                            try:
                                setattr(entry, 'store', {'state': disk_state})
                            except Exception:
                                pass
                    print('aggregated state.json applied to registry')
                except Exception as e:
                    print('failed to apply aggregated state to registry:', e)

# Final: print StateViewSet._load_state()
sv = StateViewSet()
state = sv._load_state()
print('Final registry state loaded (keys):', list(state.keys()))
print(json.dumps(state, ensure_ascii=False, indent=2))
