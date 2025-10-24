try:
        
    from .connection import db_instance, db1_instance

    __all__ = ["db_instance", "db1_instance"]
except ImportError:
    pass