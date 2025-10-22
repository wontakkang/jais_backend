from django.core.management.base import BaseCommand
from pathlib import Path
import json
import logging

from utils.protocol.context import CONTEXT_REGISTRY

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Dump entire CONTEXT_REGISTRY to stdout as JSON.'

    def handle(self, *args, **options):
        try:
            def serialize(v):
                try:
                    if hasattr(v, 'get_all_state') and callable(getattr(v, 'get_all_state')):
                        return v.get_all_state()
                    if isinstance(v, dict):
                        return v.get('store', {}).get('state', {})
                    store = getattr(v, 'store', None)
                    if isinstance(store, dict):
                        return store.get('state', {})
                    # Last resort: try repr
                    return {'__repr__': repr(v)}
                except Exception as e:
                    return {'__error__': str(e)}

            out = {}
            for k, v in CONTEXT_REGISTRY.items():
                out[k] = serialize(v)

            self.stdout.write(json.dumps(out, ensure_ascii=False, indent=2, default=str))
            return 0
        except Exception as e:
            logger.exception('Failed to dump CONTEXT_REGISTRY')
            self.stderr.write(str(e))
            return 1
