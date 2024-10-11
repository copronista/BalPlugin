from electrum.gui.qt.util import WindowModalDialog
from typing import Callable,Any
from . import qt_resources
class BalDialog(WindowModalDialog):

    def __init__(self,parent,title=None, icon = 'bal32x32.png'):
        self.parent=parent
        WindowModalDialog.__init__(self,self.parent,title)
        self.setWindowIcon(qt_resources.read_QIcon(icon))

class BalWaitingDialog(BalDialog):
    def __init__(self, bal_window: 'BalWindow', message: str, task, on_success=None, on_error=None, on_cancel=None):
        assert bal_window
        BalDialog.__init__(self, bal_window, _("Please wait"))
        self.message_label = QLabel(message)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.message_label)
        if on_cancel:
            self.cancel_button = CancelButton(self)
            self.cancel_button.clicked.connect(on_cancel)
            vbox.addLayout(Buttons(self.cancel_button))
        self.accepted.connect(self.on_accepted)
        self.show()
        self.thread = TaskThread(self)
        self.thread.finished.connect(self.deleteLater)  # see #3956
        self.thread.add(task, on_success, self.accept, on_error)

    def wait(self):
        self.thread.wait()

    def on_accepted(self):
        self.thread.stop()

    def update(self, msg):
        self.message_label.setText(msg)

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





