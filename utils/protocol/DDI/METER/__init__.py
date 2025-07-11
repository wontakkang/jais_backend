from . import TEROS

all_list = []
all_dict = {}

# dew_point.calculation_methods 활용
if hasattr(TEROS, "calculation_methods"):
    all_list.extend(TEROS.calculation_methods.keys())
    all_dict.update(TEROS.calculation_methods)


__all__ = all_list