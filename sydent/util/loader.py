import importlib
from typing import Type

from sydent.config.exceptions import ConfigError


def load_class(full_path: str) -> Type:
    try:
        _module, class_name = full_path.rsplit(".", 1)
        module = importlib.import_module(_module)
        return getattr(module, class_name)
    except (AttributeError, ModuleNotFoundError):
        raise ConfigError("Cannot load: %s" % full_path)
