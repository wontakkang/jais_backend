from pathlib import Path
import os
import sys
import json

# Ensure project root on sys.path
this = Path(__file__).resolve()
proj_root = str(this.parent.parent)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'py_backend.settings')

import django
django.setup()

from MCUnode.views import StateViewSet

sv = StateViewSet()
state = sv._load_state()
print(json.dumps(state, ensure_ascii=False, indent=2))
