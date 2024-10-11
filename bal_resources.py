import os

plugin_dir = os.path.split(os.path.realpath(__file__))[0]

def icon_path(icon_basename: str):
    path = resource_path('icons',icon_basename)
    return path

def resource_path(*parts):
    return os.path.join(plugin_dir, *parts)


