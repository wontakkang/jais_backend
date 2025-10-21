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

from utils.protocol.context import CONTEXT_REGISTRY
from utils.protocol.context.manager import get_or_create_registry_entry

out = {
    'context_registry_keys': list(CONTEXT_REGISTRY.keys()),
    'mcunode': None,
}

entry = CONTEXT_REGISTRY.get('MCUnode')
entry_info = {}
try:
    entry_info['present'] = entry is not None
    entry_info['type'] = type(entry).__name__ if entry is not None else None
    entry_info['id'] = id(entry) if entry is not None else None
    # if get_all_state available
    try:
        entry_info['has_get_all_state'] = hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state'))
    except Exception:
        entry_info['has_get_all_state'] = False
    try:
        entry_info['has_set_state'] = hasattr(entry, 'set_state') and callable(getattr(entry, 'set_state'))
    except Exception:
        entry_info['has_set_state'] = False
    # _state attribute
    try:
        s = getattr(entry, '_state', None)
        entry_info['_state_type'] = type(s).__name__ if s is not None else None
        if isinstance(s, dict):
            entry_info['_state_keys'] = list(s.keys())[:20]
            entry_info['_state_len'] = len(s)
        else:
            entry_info['_state_preview'] = str(s)[:200]
    except Exception:
        entry_info['_state_error'] = True
    # store attr
    try:
        store = getattr(entry, 'store', None)
        entry_info['has_store'] = store is not None
        entry_info['store_type'] = type(store).__name__ if store is not None else None
        if isinstance(store, dict):
            entry_info['store_keys'] = list(store.keys())[:40]
        else:
            entry_info['store_preview'] = str(store)[:200]
    except Exception:
        entry_info['store_error'] = True
    # if get_all_state callable, call it
    try:
        if entry_info.get('has_get_all_state'):
            g = entry.get_all_state()
            entry_info['get_all_state_type'] = type(g).__name__
            if isinstance(g, dict):
                entry_info['get_all_state_keys'] = list(g.keys())[:40]
                entry_info['get_all_state_len'] = len(g)
            else:
                entry_info['get_all_state_preview'] = str(g)[:200]
    except Exception as e:
        entry_info['get_all_state_error'] = str(e)
except Exception as e:
    entry_info = {'error': str(e)}

out['mcunode'] = entry_info
print(json.dumps(out, ensure_ascii=False, indent=2))
