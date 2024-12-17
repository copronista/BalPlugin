from functools import partial

from . import qt_resources
if qt_resources.QT_VERSION == 5:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QWidget,QScrollArea)
    from PyQt5.QtGui import (QPixmap, QImage, QBitmap, QPainter, QFontDatabase, QPen, QFont,
                     QColor, QDesktopServices, qRgba, QPainterPath,QPalette)
else:
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QWidget,QScrollArea)
    from PyQt6.QtGui import (QPixmap, QImage, QBitmap, QPainter, QFontDatabase, QPen, QFont,
                     QColor, QDesktopServices, qRgba, QPainterPath,QPalette)


from electrum.util import decimal_point_to_base_unit_name
from electrum.i18n import _

from ..bal import BalPlugin
from .. import will as Will
from .. import util as Util
from .baldialog import BalDialog



    


class WillDetailDialog(BalDialog):


    def __init__(self, bal_window):

        self.will = bal_window.willitems
        self.threshold = Util.parse_locktime_string(bal_window.will_settings['threshold'])
        self.bal_window = bal_window 
        Will.add_willtree(self.will)
        super().__init__(bal_window.window)
        self.config = bal_window.window.config
        self.wallet = bal_window.wallet
        self.format_amount = bal_window.window.format_amount
        self.base_unit = bal_window.window.base_unit
        self.format_fiat_and_units = bal_window.window.format_fiat_and_units
        self.fx = bal_window.window.fx
        self.format_fee_rate = bal_window.window.format_fee_rate
        self.decimal_point = bal_window.bal_plugin.config.get_decimal_point()
        self.base_unit_name = decimal_point_to_base_unit_name(self.decimal_point)
        self.setWindowTitle(_('Will Details'))
        self.setMinimumSize(670,700)
        self.vlayout= QVBoxLayout()
        w=QWidget()
        hlayout = QHBoxLayout(w)

        b = QPushButton(_('Sign'))
        b.clicked.connect(self.ask_password_and_sign_transactions)
        hlayout.addWidget(b)
 
        b = QPushButton(_('Broadcast')) 
        b.clicked.connect(self.broadcast_transactions) 
        hlayout.addWidget(b) 

        b = QPushButton(_('Export'))
        b.clicked.connect(self.export_will)
        hlayout.addWidget(b)
        """
        toggle = "Hide"
        if self.bal_window.bal_plugin._hide_replaced:
            toggle = "Unhide"
        self.toggle_replace_button = QPushButton(_(f"{toggle} replaced"))
        self.toggle_replace_button.clicked.connect(self.toggle_replaced)
        hlayout.addWidget(self.toggle_replace_button)

        toggle = "Hide"
        if self.bal_window.bal_plugin._hide_invalidated:
            toggle = "Unhide"

        self.toggle_invalidate_button = QPushButton(_(f"{toggle} invalidated"))
        self.toggle_invalidate_button.clicked.connect(self.toggle_invalidated)
        hlayout.addWidget(self.toggle_invalidate_button)
        """
        b = QPushButton(_('Invalidate'))
        b.clicked.connect(bal_window.invalidate_will)
        hlayout.addWidget(b)
        self.vlayout.addWidget(w)

        self.paint_scroll_area()
        #vlayout.addWidget(QLabel(_("DON'T PANIC !!! everything is fine, all possible futures are covered")))
        self.vlayout.addWidget(QLabel(_("Expiration date: ")+Util.locktime_to_str(self.threshold)))
        self.vlayout.addWidget(self.scrollbox)
        w=QWidget()
        hlayout = QHBoxLayout(w)
        hlayout.addWidget(QLabel(_("Valid Txs:")+ str(len(Will.only_valid_list(self.will)))))
        hlayout.addWidget(QLabel(_("Total Txs:")+ str(len(self.will))))
        self.vlayout.addWidget(w)
        self.setLayout(self.vlayout)

    def paint_scroll_area(self):
        #self.scrollbox.deleteLater()
        #self.willlayout.deleteLater()
        #self.detailsWidget.deleteLater()
        self.scrollbox = QScrollArea()
        viewport = QWidget(self.scrollbox)
        self.willlayout = QVBoxLayout(viewport)
        self.detailsWidget = WillWidget(parent=self)
        self.willlayout.addWidget(self.detailsWidget)

        self.scrollbox.setWidget(viewport)
        viewport.setLayout(self.willlayout)
    def ask_password_and_sign_transactions(self):
        self.bal_window.ask_password_and_sign_transactions(callback=self.update)
        self.update()
    def broadcast_transactions(self):
        self.bal_window.broadcast_transactions()
        self.update()
    def export_will(self):
        self.bal_window.export_will()
    def toggle_replaced(self):
        self.bal_window.bal_plugin.hide_replaced()
        toggle = _("Hide")
        if self.bal_window.bal_plugin._hide_replaced:
            toggle = _("Unhide")
        self.toggle_replace_button.setText(f"{toggle} {_('replaced')}")
        self.update()

    def toggle_invalidated(self):
        self.bal_window.bal_plugin.hide_invalidated()
        toggle = _("Hide")
        if self.bal_window.bal_plugin._hide_invalidated:
            toggle = _("Unhide")
        self.toggle_invalidate_button.setText(_(f"{toggle} {_('invalidated')}"))
        self.update()

    def update(self):
        self.will = self.bal_window.willitems
        pos = self.vlayout.indexOf(self.scrollbox)
        self.vlayout.removeWidget(self.scrollbox)
        self.paint_scroll_area()
        self.vlayout.insertWidget(pos,self.scrollbox)
        super().update()

class WillWidget(QWidget):
    def __init__(self,father=None,parent = None):
        super().__init__()
        vlayout = QVBoxLayout()
        self.setLayout(vlayout)
        self.will = parent.bal_window.willitems
        self.parent = parent
        for w in self.will:
            if self.will[w].get_status('REPLACED') and self.parent.bal_window.bal_plugin._hide_replaced:
                continue
            if self.will[w].get_status('INVALIDATED') and self.parent.bal_window.bal_plugin._hide_invalidated:
                continue
            f = self.will[w].father
            if father == f:
                qwidget = QWidget()
                childWidget = QWidget()
                hlayout=QHBoxLayout(qwidget)
                qwidget.setLayout(hlayout)
                vlayout.addWidget(qwidget)
                detailw=QWidget()
                detaillayout=QVBoxLayout()
                detailw.setLayout(detaillayout)

                willpushbutton = QPushButton(w)

                willpushbutton.clicked.connect(partial(self.parent.bal_window.show_transaction,txid=w))
                detaillayout.addWidget(willpushbutton)
                locktime = Util.locktime_to_str(self.will[w].tx.locktime)
                creation = Util.locktime_to_str(self.will[w].time)
                def qlabel(title,value):
                    label = "<b>"+_(str(title)) + f":</b>\t{str(value)}"
                    return QLabel(label)
                detaillayout.addWidget(qlabel("Locktime",locktime))
                detaillayout.addWidget(qlabel("Creation Time",creation))
                total_fees = self.will[w].tx.input_value() - self.will[w].tx.output_value()
                decoded_fees = total_fees #Util.decode_amount(total_fees,self.parent.decimal_point)
                fee_per_byte = round(total_fees/self.will[w].tx.estimated_size(),3)
                fees_str = str(decoded_fees) + " ("+  str(fee_per_byte) + " sats/vbyte)"
                detaillayout.addWidget(qlabel("Transaction fees:",fees_str))
                detaillayout.addWidget(qlabel("Status:",self.will[w].status))
                detaillayout.addWidget(QLabel(""))
                detaillayout.addWidget(QLabel("<b>Heirs:</b>"))
                for heir in self.will[w].heirs:
                    if "w!ll3x3c\"" not in heir:
                        decoded_amount = Util.decode_amount(self.will[w].heirs[heir][3],self.parent.decimal_point)
                        detaillayout.addWidget(qlabel(heir,f"{decoded_amount} {self.parent.base_unit_name}"))
                if self.will[w].we:
                    detaillayout.addWidget(QLabel(""))
                    detaillayout.addWidget(QLabel(_("<b>Willexecutor:</b:")))
                    decoded_amount = Util.decode_amount(self.will[w].we['base_fee'],self.parent.decimal_point)

                    detaillayout.addWidget(qlabel(self.will[w].we['url'],f"{decoded_amount} {self.parent.base_unit_name}"))
                detaillayout.addStretch()
                pal = QPalette()
                pal.setColor(QPalette.ColorRole.Window, QColor(self.will[w].get_color()))
                detailw.setAutoFillBackground(True)
                detailw.setPalette(pal)

                hlayout.addWidget(detailw)
                hlayout.addWidget(WillWidget(w,parent = parent))

