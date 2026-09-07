import importlib


def load_adapter(module_name: str):
    module = importlib.import_module(module_name)
    return module.Adapter()

