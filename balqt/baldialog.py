from typing import Callable,Any

from . import qt_resources
if qt_resources.QT_VERSION == 5:
    from PyQt5.QtCore import Qt,pyqtSignal
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QCheckBox
else:
    from PyQt6.QtCore import Qt,pyqtSignal
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QCheckBox

from electrum.gui.qt.util import WindowModalDialog, TaskThread
from electrum.i18n import _
from electrum.logging import get_logger

_logger = get_logger(__name__)

class BalDialog(WindowModalDialog):

    def __init__(self,parent,title=None, icon = 'bal32x32.png'):
        self.parent=parent
        WindowModalDialog.__init__(self,self.parent,title)
        self.setWindowIcon(qt_resources.read_QIcon(icon))

class BalWaitingDialog(BalDialog):
    updatemessage=pyqtSignal([str], arguments=['message'])
    def __init__(self, bal_window: 'BalWindow', message: str, task, on_success=None, on_error=None, on_cancel=None,exe=True):
        assert bal_window
        BalDialog.__init__(self, bal_window.window, _("Please wait"))
        self.message_label = QLabel(message)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.message_label)
        self.updatemessage.connect(self.update_message)
        if on_cancel:
            self.cancel_button = CancelButton(self)
            self.cancel_button.clicked.connect(on_cancel)
            vbox.addLayout(Buttons(self.cancel_button))
        self.accepted.connect(self.on_accepted)
        self.task=task
        self.on_success = on_success
        self.on_error = on_error
        self.on_cancel = on_cancel
        if exe:
            self.exe()

    def exe(self):
        self.thread = TaskThread(self)
        self.thread.finished.connect(self.deleteLater)  # see #3956
        self.thread.finished.connect(self.finished)
        self.thread.add(self.task, self.on_success, self.accept, self.on_error)
        self.exec()

    def hello(self):
        pass
    def finished(self):
        _logger.info("finished")
    def wait(self):
        self.thread.wait()

    def on_accepted(self):
        self.thread.stop()
    def update_message(self,msg):
        self.message_label.setText(msg)

    def update(self, msg):
        self.updatemessage.emit(msg)

    def getText(self):
         return self.message_label.text()

    def closeEvent(self,event):
        self.thread.stop()



class BalBlockingWaitingDialog(BalDialog):
    def __init__(self, bal_window: 'BalWindow', message: str, task: Callable[[], Any]):
        BalDialog.__init__(self, bal_window, _("Please wait"))
        self.message_label = QLabel(message)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.message_label)
        self.finished.connect(self.deleteLater)  # see #3956
        # show popup
        self.show()
        # refresh GUI; needed for popup to appear and for message_label to get drawn
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        try:
            # block and run given task
            task()
        finally:
            # close popup
            self.accept()

class bal_checkbox(QCheckBox):
    def __init__(self, plugin,variable,window=None):
        QCheckBox.__init__(self)
        self.setChecked(plugin.config_get(variable))
        window=window
        def on_check(v):
            plugin.config.set_key(variable, v == Qt.CheckState.Checked, save=True)
            if window:
                plugin._hide_invalidated= plugin.config_get(plugin.HIDE_INVALIDATED)
                plugin._hide_replaced= plugin.config_get(plugin.HIDE_REPLACED)

                window.update_all()
        self.stateChanged.connect(on_check)

    #TODO IMPLEMENT PREVIEW DIALOG
    #tx list display txid, willexecutor, qrcode, button to sign
    #   :def preview_dialog(self, txs):
    def preview_dialog(self, txs):
        w=PreviewDialog(self,txs)
        w.exec()
        return w
    def add_info_from_will(self,tx):
        for input in tx.inputs():
            pass


