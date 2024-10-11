import os

PLUGIN_DIR = os.path.split(os.path.realpath(__file__))[0]
DEFAULT_ICON = 'bal32x32.png'
DEFAULT_ICON_PATH = 'icons'


def icon_path(icon_basename: str = DEFAULT_ICON):
    path = resource_path(DEFAULT_ICON_PATH,icon_basename)
    return path

def resource_path(*parts):
    return os.path.join(PLUGIN_DIR, *parts)


