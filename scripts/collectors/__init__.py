"""采集器包：导入所有模块以完成注册。"""
from __future__ import annotations

import importlib
import pkgutil

MODULES = ("italent", "tianjian", "shinewing", "rongcheng", "ey")


def load_all() -> None:
    for name in MODULES:
        importlib.import_module(f"collectors.{name}")
    for info in pkgutil.iter_modules(__path__):
        if info.name in MODULES or info.name == "base":
            continue
        try:
            importlib.import_module(f"collectors.{info.name}")
        except Exception:
            pass
