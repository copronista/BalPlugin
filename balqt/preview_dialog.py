#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2012 thomasv@gitorious
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import enum
import copy

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt,QPersistentModelIndex, QModelIndex
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QMenu,QAbstractItemView)

from electrum.i18n import _
from electrum.gui.qt.util import (Buttons,read_QIcon, import_meta_gui, export_meta_gui,MessageBoxMixin,BlockingWaitingDialog,WaitingDialog,WindowModalDialog)
from electrum.util import write_json_file,read_json_file,FileImportFailed
from electrum.gui.qt.my_treeview import MyTreeView
from electrum.gui.qt.transaction_dialog import show_transaction
import json
import urllib.request
import urllib.parse
from ..bal import BalPlugin
from ..willexecutors import Willexecutors
from ..util import Util 
from electrum.transaction import tx_from_any
from electrum.network import Network
from functools import partial
import json

class PreviewList(MyTreeView):
    class Columns(MyTreeView.BaseColumnsEnum):
        LOCKTIME = enum.auto()
        TXID = enum.auto()
        #DESCRIPTION = enum.auto()
        #VALUE = enum.auto() 
        STATUS = enum.auto()

    headers = {
        Columns.LOCKTIME: _('Locktime'),
        Columns.TXID: _('Txid'),
        #Columns.DESCRIPTION: _('Description'),
        #Columns.VALUE: _('Value'),
        Columns.STATUS: _('Status'),
    }

    ROLE_HEIR_KEY = Qt.UserRole + 2000
    key_role = ROLE_HEIR_KEY

    def __init__(self, parent: 'BalWindow',will):
        super().__init__(
            parent=parent.window,
            stretch_column=self.Columns.TXID,
            #editable_columns=[self.Columns.URL,self.Columns.BASE_FEE,self.Columns.ADDRESS],

        )
        self.decimal_point=parent.bal_plugin.config.get_decimal_point
        self.setModel(QStandardItemModel(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
    

        #print("will",will)
        if not will is None:
            self.will = will
        else:
            self.will = parent.will
        self.bal_window = parent
        self.wallet=parent.window.wallet
        self.setModel(QStandardItemModel(self))
        self.setSortingEnabled(True)
        self.std_model = self.model()
        self.config = parent.bal_plugin.config
        self.bal_plugin=self.bal_window.bal_plugin

        #self.selected = self.parent.bal_plugin.config_get(BalPlugin.SELECTED_WILLEXECUTORS)
           

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

            """if sel_key in self.selected:
                menu.addAction(_("deselect").format(column_title), lambda: self.deselect(selected_keys))
            else:
            """    
            #menu.addAction(_("select").format(column_title), lambda: self.select(selected_keys))
            menu.addAction(_("details").format(column_title), lambda: self.show_transaction(selected_keys)).setEnabled(len(selected_keys)<2)

            menu.addSeparator()
            menu.addAction(_("delete").format(column_title), lambda: self.delete(selected_keys))

        menu.exec_(self.viewport().mapToGlobal(position))
    """
    def get_edit_key_from_coordinate(self, row, col):
        print("get edit key",row,col,self.ROLE_HEIR_KEY+col)
        a= self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col)
        print(a) 
        #return self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col+1)
        return a
    """
    def delete(self,selected_keys):
        for key in selected_keys:
            del self.will[key]
        self.update()
        
    def show_transaction(self,selected_keys):
        for key in selected_keys:
            self.bal_window.window.show_transaction(self.will[key]['tx'])
            #self.show_transaction(self.will[key]['tx'], parent=self.bal_window.window.top_level_window())

        self.update()

    def select(self,selected_keys):
        self.selected += selected_keys
        #self.parent.bal_plugin.config.set_key(BalPlugin.SELECTED_WILLEXECUTORS,self.selected,save=True)
        self.update()

    def deselect(self,selected_keys):
        for key in selected_keys:
            self.selected.remove(key)
        #self.parent.bal_plugin.config.set_key(BalPlugin.SELECTED_WILLEXECUTORS,self.selected,save=True)
        self.update()
    """
    def on_edited(self, idx, edit_key, *, text):
        prior_name = self.parent.willexecutors_list[edit_key]
        print("prior_name",prior_name)
        aarint("edit_key",edit_key)

        col = idx.column()
        print("col",col)
        if col == self.Columns.URL:
            self.parent.willexecutors_list[text]=self.parent.willexecutors_list[edit_key]
            del self.parent.willexecutors_list[edit_key]
        if col == self.Columns.BASE_FEE:
            self.parent.willexecutors_list[edit_key]["base_fee"] = text
        if col == self.Columns.ADDRESS:
            self.parent.willexecutors_list[edit_key]["info"] = text
        self.update()
    """
    def update_will(self,will):
        self.will.update(will)
        self.update()

    def update(self):
        #print("update will")
        if self.will is None:
            return

        current_key = self.get_role_data_for_current_item(col=self.Columns.TXID, role=self.ROLE_HEIR_KEY)
        self.model().clear()
        self.update_headers(self.__class__.headers)




        set_current = None

        for txid,bal_tx in self.will.items():
            #self.ping_server(url)
            tx=bal_tx['tx']
            labels = [""] * len(self.Columns)
            #print("willlocktime",tx.locktime)
            labels[self.Columns.LOCKTIME] = Util.locktime_to_str(tx.locktime)
            labels[self.Columns.TXID] = txid
            #labels[self.Columns.DESCRIPTION] = bal_tx.get('description','')
            #labels[self.Columns.VALUE] = Util.decode_amount(bal_tx.get('heirsvalue',0),self.config.get_decimal_point())
            labels[self.Columns.STATUS] = bal_tx.get('status','None')
            
            
            
            items=[]
            for e in labels:
                if type(e)== list:
                    try:
                        items.append(QStandardItem(*e))
                    except Exception as e:
                        print("e cazzo",e)
                else:
                    #print(labels)
                    items.append(QStandardItem(str(e)))
            """
            items[self.Columns.SELECTED].setEditable(False)
            items[self.Columns.URL].setEditable(True)
            items[self.Columns.ADDRESS].setEditable(True)
            items[self.Columns.BASE_FEE].setEditable(True)
            items[self.Columns.STATUS].setEditable(False)

            items[self.Columns.URL].setData(url, self.ROLE_HEIR_KEY+1)
            items[self.Columns.BASE_FEE].setData(url, self.ROLE_HEIR_KEY+2)
            items[self.Columns.ADDRESS].setData(url, self.ROLE_HEIR_KEY+3)
            """

            self.model().insertRow(self.model().rowCount(), items)
            if txid == current_key:
                idx = self.model().index(row_count, self.Columns.TXID)
                set_current = QPersistentModelIndex(idx)
            self.set_current_idx(set_current)

    def create_toolbar(self, config): 
        toolbar, menu = self.create_toolbar_with_menu('') 
        menu.addAction(_("Prepare Will"), self.build_transactions) 
        menu.addAction(_("Display Will"), self.bal_window.preview_modal_dialog) 
        menu.addAction(_("Sign Will"), self.ask_password_and_sign_transactions)
        menu.addAction(_("Export Will"), self.export_will)
        menu.addAction(_("Import Will"), self.import_will)
        menu.addAction(_("Export Transactions"), self.export_file)
        menu.addAction(_("Broadcast"), self.broadcast)
        menu.addAction(_("Invalidate Will"), self.invalidate_will)
        return toolbar

    def build_transactions(self):
        will = self.bal_window.prepare_will()
        if will:
            self.update_will(will)
    def export_json_file(self,path):
        write_json_file(path, self.will)

    def export_will(self):
        export_meta_gui(self.bal_window.window, _('will'), self.export_json_file)

    def import_json_file(self,path):
        try:
            data = read_json_file(path)
            for k,v in data.items():
                data[k]['tx']=tx_from_any(v['tx'])
            self.will.update(data)
        except:
            raise FileImportFailed(_("Invalid will file"))

    def import_will(self):
        import_meta_gui(self.bal_window.window, _('will'), self.import_json_file,self.update)

    def sign_transactions(self,password):
        txs={}
        signed = None
        tosign = None
        def get_message():
            msg = ""
            if signed:
                msg=_(f"signed: {signed}\n")
            return msg + _(f"signing: {tosign}")
        for txid,willitem in self.will.items():
            tx = copy.deepcopy(willitem['tx'])
            if BalPlugin.STATUS_COMPLETE in willitem['status']:
                print("altready signed",txid)
                txs[txid]=tx
                continue 
            #if not tx.is_complete() and tx.is_missing_info_from_network():
             #   await tx.add_info_from_network(self.wallet.network, timeout=10)

            #task = partial(self.wallet.sign_transaction, tx, password,ignore_warnings=True)
            #msg = _(f"Signing transactions...{txid}")
            #WaitingDialog(self, msg, task, on_success, on_failure)
            tosign=txid
            self.waiting_dialog.update(get_message())
            for txin in tx.inputs():
                #print_utxo(txin,"UTXO")
                prevout = txin.prevout.to_json()
                if prevout[0] in self.will:
                    #print("TROVATO",self.will[prevout[0]])
                    change = self.will[prevout[0]]['tx'].outputs()[prevout[1]]
                    txin._trusted_value_sats = change.value
                    try:
                        txin.script_descriptor = change.script_descriptor
                    except:
                        pass
                    txin.is_mine=True
                    txin._TxInput__address=change.address
                    txin._TxInput__scriptpubkey = change.scriptpubkey
                    txin._TxInput__value_sats = change.value
                    #print_utxo(txin)
                print(">>>>>>>>",txin.spent_txid)
         

            self.wallet.sign_transaction(tx, password,ignore_warnings=True)
            signed=tosign
            is_complete=False
            if tx.is_complete():
                is_complete=True
                willitem['status'] += BalPlugin.STATUS_COMPLETE
            #self.bal_window.window.sign_tx(tx,callback=sign_done,external_keypairs=None)
            print("tx: {} is complete:{}".format(txid, tx.is_complete()))
            txs[txid]=tx
        return txs

    def ask_password_and_sign_transactions(self):
        def on_success(txs):
            for txid,tx in txs.items():
                self.bal_window.will[txid]['tx'] = self.will[txid]['tx']=copy.deepcopy(tx)
            #self.bal_window.will[txid]['tx']=tx_from_any(str(tx))
            self.update()
            try:
                self.bal_window.will_list.update()
            except:
                print("failed to update willlist")
                pass
        def on_failure(exc_info):
            print("sign fail",exc_info)


        password = None
        if self.wallet.has_keystore_encryption():
            password = self.bal_plugin.password_dialog(parent=self.bal_window.window)
        #self.sign_transactions(password)
        
        task = partial(self.sign_transactions, password)
        msg = _('Signing transactions...')
        self.waiting_dialog = WaitingDialog(self, msg, task, on_success, on_failure)
        
                    




    def export_inheritance_handler(self,path):
        print(path)
        with open(path,"w") as f:
            for txid,willitem in self.will.items():
                self.will[txid]['status']+=BalPlugin.STATUS_EXPORTED
                f.write(str(willitem['tx'])+"\n")
        self.update()

    def export_file(self):
        try:
            Util.export_meta_gui(self.bal_window.window, _('heirs_transactions'), self.export_inheritance_handler)
        except Exception as e:
            self.bal_window.window.show_error(str(e))
            raise e
        return
    def import_file(self):
        pass


    def broadcast(self):
        Willexecutors.push_transactions_to_willexecutors(self.will, self.bal_window.bal_plugin.config_get(BalPlugin.SELECTED_WILLEXECUTORS))


    def invalidate_will(self):
        self.bal_window.invalidate_will()

class PreviewDialog(WindowModalDialog,MessageBoxMixin):
    def __init__(self, bal_window, will):
        self.parent = bal_window.window
        WindowModalDialog.__init__(self,parent=self.parent)
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
            self.will = bal_window.will
        else:
            self.will = will
        self.setWindowTitle(_('Transactions Preview'))
        self.setMinimumSize(1000, 200)
        self.size_label = QLabel()
        self.transactions_list = PreviewList(self.bal_window,will)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.size_label)
        vbox.addWidget(self.transactions_list)
        buttonbox = QHBoxLayout()

        b = QPushButton(_('Write Will'))
        b.clicked.connect(self.transactions_list.export_file)
        buttonbox.addWidget(b)

        b = QPushButton(_('Sign'))
        b.clicked.connect(self.transactions_list.ask_password_and_sign_transactions)
        buttonbox.addWidget(b)


        b = QPushButton(_('Export Will'))
        b.clicked.connect(self.transactions_list.export_file)
        buttonbox.addWidget(b)

        b = QPushButton(_('Importt Will'))
        b.clicked.connect(self.transactions_list.export_file)
        buttonbox.addWidget(b)


        b = QPushButton(_('Export Transactions'))
        b.clicked.connect(self.transactions_list.export_file)
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
    

