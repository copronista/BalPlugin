from .. import bal_resources
from PyQt5.QtGui import QIcon,QPixmap
def read_QIcon(icon_basename: str) -> QIcon:
    return QIcon(bal_resources.icon_path(icon_basename))
def read_QPixmap(icon_basename: str) -> QPixmap:
    return QPixmap(bal_resources.icon_path(icon_basename))
