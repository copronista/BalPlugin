
import enum
import copy
import json
import urllib.request
import urllib.parse
from functools import partial

from . import qt_resources
if qt_resources.QT_VERSION == 5:
    from PyQt5.QtGui import QStandardItemModel, QStandardItem
    from PyQt5.QtCore import Qt,QPersistentModelIndex, QModelIndex
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QMenu,QAbstractItemView,QWidget)
else:
    from PyQt6.QtGui import QStandardItemModel, QStandardItem
    from PyQt6.QtCore import Qt,QPersistentModelIndex, QModelIndex
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QMenu,QAbstractItemView,QWidget)

from electrum.i18n import _
from electrum.gui.qt.util import (Buttons,read_QIcon, import_meta_gui, export_meta_gui,MessageBoxMixin)
from electrum.util import write_json_file,read_json_file,FileImportFailed
from electrum.gui.qt.my_treeview import MyTreeView
from electrum.transaction import tx_from_any
from electrum.network import Network


from ..bal import BalPlugin
from .. import willexecutors as Willexecutors
from .. import util as Util 
from .. import will as  Will
from .baldialog import BalDialog

class PreviewList(MyTreeView):
    class Columns(MyTreeView.BaseColumnsEnum):
        LOCKTIME = enum.auto()
        TXID = enum.auto()
        WILLEXECUTOR = enum.auto()
        STATUS = enum.auto()

    headers = {
        Columns.LOCKTIME: _('Locktime'),
        Columns.TXID: _('Txid'),
        Columns.WILLEXECUTOR: _('Will-Executor'),
        Columns.STATUS: _('Status'),
    }

    ROLE_HEIR_KEY = Qt.ItemDataRole.UserRole + 2000
    key_role = ROLE_HEIR_KEY

    def __init__(self, parent: 'BalWindow',will):
        super().__init__(
            parent=parent.window,
            stretch_column=self.Columns.TXID,
        )
        self.decimal_point=parent.bal_plugin.config.get_decimal_point
        self.setModel(QStandardItemModel(self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    

        if not will is None:
            self.will = will
        else:
            self.will = parent.willitems

        self.bal_window = parent
        self.wallet=parent.window.wallet
        self.setModel(QStandardItemModel(self))
        self.setSortingEnabled(True)
        self.std_model = self.model()
        self.config = parent.bal_plugin.config
        self.bal_plugin=self.bal_window.bal_plugin

        self.update()

    def create_menu(self, position):
        menu = QMenu()
        idx = self.indexAt(position)
        column = idx.column() or self.Columns.TXID
        selected_keys = []
        for s_idx in self.selected_in_column(self.Columns.TXID):
            sel_key = self.model().itemFromIndex(s_idx).data(0)
            selected_keys.append(sel_key)
        if selected_keys and idx.isValid():
            column_title = self.model().horizontalHeaderItem(column).text()
            column_data = '\n'.join(self.model().itemFromIndex(s_idx).text()
                                    for s_idx in self.selected_in_column(column))

            menu.addAction(_("details").format(column_title), lambda: self.show_transaction(selected_keys)).setEnabled(len(selected_keys)<2)
            if len(selected_keys)==1 and self.will[selected_keys[0]].we:
                menu.addAction(_("check ").format(column_title), lambda: self.check_transactions(selected_keys))

            menu.addSeparator()
            menu.addAction(_("delete").format(column_title), lambda: self.delete(selected_keys))

        menu.exec(self.viewport().mapToGlobal(position))

    def delete(self,selected_keys):
        for key in selected_keys:
            del self.will[key]
            try:
                del self.bal_window.willitems[key]
            except:
                pass
            try:
                del self.bal_window.will[key]
            except:
                pass
        self.update()

    def check_transactions(self,selected_keys):
        wout = {}
        for k in selected_keys:
            wout[k] = self.will[k]
        if wout:
            self.bal_window.check_transactions(wout)
        self.update()

    def show_transaction(self,selected_keys):
        for key in selected_keys:
            self.bal_window.show_transaction(self.will[key].tx)

        self.update()

    def select(self,selected_keys):
        self.selected += selected_keys
        self.update()

    def deselect(self,selected_keys):
        for key in selected_keys:
            self.selected.remove(key)
        self.update()

    def update_will(self,will):
        self.will.update(will)
        self.update()

    def update(self):
        if self.will is None:
            return

        current_key = self.get_role_data_for_current_item(col=self.Columns.TXID, role=self.ROLE_HEIR_KEY)
        self.model().clear()
        self.update_headers(self.__class__.headers)




        set_current = None
        for txid,bal_tx in self.will.items():
            if self.bal_window.bal_plugin._hide_replaced and bal_tx[BalPlugin.STATUS_REPLACED]:
                continue
            if self.bal_window.bal_plugin._hide_invalidated and bal_tx[BalPlugin.STATUS_INVALIDATED]:
                continue


            tx=bal_tx.tx
            labels = [""] * len(self.Columns)
            labels[self.Columns.LOCKTIME] = Util.locktime_to_str(tx.locktime)
            labels[self.Columns.TXID] = txid
            we = 'None'
            if bal_tx.we:
                we = bal_tx.we['url']
            labels[self.Columns.WILLEXECUTOR]=we
            status = bal_tx.status
            if len(bal_tx.status) > 53:
                status = "...{}".format(status[-50:])
            labels[self.Columns.STATUS] = status
            
            
            
            items=[]
            for e in labels:
                if type(e)== list:
                    try:
                        items.append(QStandardItem(*e))
                    except Exception as e:
                        pass
                else:
                    items.append(QStandardItem(str(e)))

            self.model().insertRow(self.model().rowCount(), items)
            if txid == current_key:
                idx = self.model().index(row_count, self.Columns.TXID)
                set_current = QPersistentModelIndex(idx)
            self.set_current_idx(set_current)

    def create_toolbar(self, config): 
        toolbar, menu = self.create_toolbar_with_menu('') 
        menu.addAction(_("Prepare"), self.build_transactions) 
        menu.addAction(_("Display"), self.bal_window.preview_modal_dialog) 
        menu.addAction(_("Sign"), self.ask_password_and_sign_transactions)
        menu.addAction(_("Export"), self.export_will)
        menu.addAction(_("Import"), self.import_will)
        menu.addAction(_("Broadcast"), self.broadcast)
        menu.addAction(_("Invalidate"), self.invalidate_will)
        prepareButton = QPushButton(_("Prepare"))
        prepareButton.clicked.connect(self.build_transactions)
        signButton = QPushButton(_("Sign"))
        signButton.clicked.connect(self.ask_password_and_sign_transactions)
        pushButton = QPushButton(_("Broadcast"))
        pushButton.clicked.connect(self.broadcast)
        displayButton = QPushButton(_("Display"))
        displayButton.clicked.connect(self.bal_window.preview_modal_dialog)
        hlayout = QHBoxLayout()
        widget = QWidget()
        hlayout.addWidget(prepareButton)
        hlayout.addWidget(signButton)
        hlayout.addWidget(pushButton)
        hlayout.addWidget(displayButton)
        widget.setLayout(hlayout)
        toolbar.insertWidget(2,widget)

        return toolbar

    def hide_replaced(self):
        self.bal_window.bal_plugin.hide_replaced()
        self.update()

    def hide_invalidated(self):
        self.bal_window.bal_plugin.hide_invalidated()
        self.update()

    def build_transactions(self):
        will = self.bal_window.prepare_will()
        if will:
            self.update_will(will)

    def export_json_file(self,path):
        write_json_file(path, self.will)

    def export_will(self):
        self.bal_window.export_will()
        self.update()

    def import_will(self):
        self.bal_window.import_will()

    def ask_password_and_sign_transactions(self):
        self.bal_window.ask_password_and_sign_transactions(callback=self.update) 
                    
    def broadcast(self):
        self.bal_window.broadcast_transactions()
        self.update

    def invalidate_will(self):
        self.bal_window.invalidate_will()
        self.update()

class PreviewDialog(BalDialog,MessageBoxMixin):
    def __init__(self, bal_window, will):
        self.parent = bal_window.window
        BalDialog.__init__(self,bal_window = bal_window)
        self.bal_plugin = bal_window.bal_plugin
        self.gui_object = self.bal_plugin.gui_object
        self.config = self.bal_plugin.config
        self.bal_window = bal_window
        self.wallet = bal_window.window.wallet
        self.format_amount = bal_window.window.format_amount
        self.base_unit = bal_window.window.base_unit
        self.format_fiat_and_units = bal_window.window.format_fiat_and_units 
        self.fx = bal_window.window.fx 
        self.format_fee_rate = bal_window.window.format_fee_rate
        self.show_address = bal_window.window.show_address
        if not will:
            self.will = bal_window.willitems
        else:
            self.will = will
        self.setWindowTitle(_('Transactions Preview'))
        self.setMinimumSize(1000, 200)
        self.size_label = QLabel()
        self.transactions_list = PreviewList(self.bal_window,self.will)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.size_label)
        vbox.addWidget(self.transactions_list)
        buttonbox = QHBoxLayout()

        b = QPushButton(_('Sign'))
        b.clicked.connect(self.transactions_list.ask_password_and_sign_transactions)
        buttonbox.addWidget(b)

        b = QPushButton(_('Export Will'))
        b.clicked.connect(self.transactions_list.export_will)
        buttonbox.addWidget(b)

        b = QPushButton(_('Broadcast'))
        b.clicked.connect(self.transactions_list.broadcast)
        buttonbox.addWidget(b)

        b = QPushButton(_('Invalidate will'))
        b.clicked.connect(self.transactions_list.invalidate_will)
        buttonbox.addWidget(b)

        vbox.addLayout(buttonbox)

        self.update()
    

    def update_will(self,will):
        self.will.update(will)
        self.transactions_list.update_will(will)
        self.update()
    
    def update(self):
        self.transactions_list.update()

    def is_hidden(self):
        return self.isMinimized() or self.isHidden()

    def show_or_hide(self):
        if self.is_hidden():
            self.bring_to_top()
        else:
            self.hide()

    def bring_to_top(self):
        self.show()
        self.raise_()

    def closeEvent(self, event):
        event.accept()
