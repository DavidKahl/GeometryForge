import importlib

def build_parts(parameters, parts, api):
    for part in parts:
        api.begin(part)
        importlib.import_module(part).build(parameters, api)
