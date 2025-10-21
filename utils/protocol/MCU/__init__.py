import os
import importlib
from pathlib import Path

# Get all Python files in the current MCU directory
current_dir = Path(__file__).parent
python_files = [f.stem for f in current_dir.glob("*.py") if f.stem != "__init__"]

all_list = []
all_dict = {}

# Import each module and extract public functions/classes
for module_name in python_files:
    try:
        module = importlib.import_module(f".{module_name}", package=__package__)
        
        # If module has __all__, use it
        if hasattr(module, "__all__") and isinstance(module.__all__, (list, tuple)):
            for name in module.__all__:
                obj = getattr(module, name, None)
                if obj is not None:
                    all_list.append(name)
                    all_dict[name] = obj
        else:
            # Fallback: expose public callables from module
            for name in dir(module):
                if name.startswith("_"):
                    continue
                obj = getattr(module, name)
                if callable(obj) or (hasattr(obj, '__module__') and obj.__module__ == module.__name__):
                    all_list.append(name)
                    all_dict[name] = obj
    except ImportError as e:
        # Skip modules that can't be imported
        continue

# Also include the client module for backward compatibility
from .client import DE_MCU_SerialClient
if "DE_MCU_SerialClient" not in all_list:
    all_list.append("DE_MCU_SerialClient")
    all_dict["DE_MCU_SerialClient"] = DE_MCU_SerialClient

__all__ = all_list