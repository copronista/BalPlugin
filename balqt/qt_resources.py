from .. import bal_resources
import sys
try:
    QT_VERSION=sys._GUI_QT_VERSION
except:
    QT_VERSION=6
if QT_VERSION == 5:
    from PyQt5.QtGui import QIcon,QPixmap
else:
    from PyQt6.QtGui import QIcon,QPixmap
    
def read_QIcon(icon_basename: str=bal_resources.DEFAULT_ICON) -> QIcon:
    return QIcon(bal_resources.icon_path(icon_basename))
def read_QPixmap(icon_basename: str=bal_resources.DEFAULT_ICON) -> QPixmap:
    return QPixmap(bal_resources.icon_path(icon_basename))

