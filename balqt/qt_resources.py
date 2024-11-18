from .. import bal_resources
from PyQt6.QtGui import QIcon,QPixmap
def read_QIcon(icon_basename: str=bal_resources.DEFAULT_ICON) -> QIcon:
    return QIcon(bal_resources.icon_path(icon_basename))
def read_QPixmap(icon_basename: str=bal_resources.DEFAULT_ICON) -> QPixmap:
    return QPixmap(bal_resources.icon_path(icon_basename))

