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

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt,QPersistentModelIndex, QModelIndex
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,QMenu)

from electrum.i18n import _
from electrum.gui.qt.util import (Buttons,read_QIcon, import_meta_gui, export_meta_gui,MessageBoxMixin)
from electrum.util import write_json_file,read_json_file
from electrum.gui.qt.my_treeview import MyTreeView
import json
import urllib.request
import urllib.parse
from ..bal import BalPlugin
from ..util import encode_amount,decode_amount
class WillExecutorList(MyTreeView):
    class Columns(MyTreeView.BaseColumnsEnum):
        SELECTED = enum.auto()
        URL = enum.auto()
        BASE_FEE = enum.auto()
        ADDRESS = enum.auto()
        STATUS = enum.auto()

    headers = {
        Columns.SELECTED:_(''),
        Columns.URL: _('Url'),
        Columns.BASE_FEE: _('Base fee'),
        Columns.ADDRESS:_('Info'),
        Columns.STATUS: _('S'),
    }

    ROLE_HEIR_KEY = Qt.UserRole + 2000
    key_role = ROLE_HEIR_KEY

    def __init__(self, parent: 'WillExecutorDialog'):
        super().__init__(
            parent=parent,
            stretch_column=self.Columns.URL,
            editable_columns=[self.Columns.URL,self.Columns.BASE_FEE,self.Columns.ADDRESS],

        )
        self.parent = parent
        self.setModel(QStandardItemModel(self))
        self.setSortingEnabled(True)
        self.std_model = self.model()
        self.config =parent.bal_plugin.config
        self.selected = self.parent.bal_plugin.config_get(BalPlugin.SELECTED_WILLEXECUTORS)
           

        self.update()



    def create_menu(self, position):
        menu = QMenu()
        idx = self.indexAt(position)
        column = idx.column() or self.Columns.URL
        selected_keys = []
        for s_idx in self.selected_in_column(self.Columns.URL):
            sel_key = self.model().itemFromIndex(s_idx).data(0)
            selected_keys.append(sel_key)
        if selected_keys and idx.isValid():
            column_title = self.model().horizontalHeaderItem(column).text()
            column_data = '\n'.join(self.model().itemFromIndex(s_idx).text()
                                    for s_idx in self.selected_in_column(column))
            if sel_key in self.selected:
                menu.addAction(_("deselect").format(column_title), lambda: self.deselect(selected_keys))
            else:
                menu.addAction(_("select").format(column_title), lambda: self.select(selected_keys))
            menu.addAction(_("delete").format(column_title), lambda: self.delete(selected_keys))
            if column in self.editable_columns:
                item = self.model().itemFromIndex(idx)
                if item.isEditable():
                    persistent = QPersistentModelIndex(idx)
                    menu.addAction(_("Edit {}").format(column_title), lambda p=persistent: self.edit(QModelIndex(p)))

        menu.exec_(self.viewport().mapToGlobal(position))

    def get_edit_key_from_coordinate(self, row, col):
        print("get edit key",row,col,self.ROLE_HEIR_KEY+col)
        a= self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col)
        print(a) 
        #return self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col+1)
        return a

    def delete(self,selected_keys):
        for key in selected_keys:
            del self.parent.willexecutors_list[key]
        self.update()
    def select(self,selected_keys):
        self.selected += selected_keys
        self.parent.bal_plugin.config.set_key(BalPlugin.SELECTED_WILLEXECUTORS,self.selected,save=True)
        self.update()

    def deselect(self,selected_keys):
        for key in selected_keys:
            self.selected.remove(key)
        self.parent.bal_plugin.config.set_key(BalPlugin.SELECTED_WILLEXECUTORS,self.selected,save=True)
        self.update()

    def on_edited(self, idx, edit_key, *, text):
        prior_name = self.parent.willexecutors_list[edit_key]
        print("prior_name",prior_name)
        print("idx",idx)
        print("edit_key",edit_key)

        col = idx.column()
        print("col",col)
        if col == self.Columns.URL:
            self.parent.willexecutors_list[text]=self.parent.willexecutors_list[edit_key]
            del self.parent.willexecutors_list[edit_key]
        if col == self.Columns.BASE_FEE:
            self.parent.willexecutors_list[edit_key]["base_fee"] = encode_amount(text,self.config.get_decimal_point())
        if col == self.Columns.ADDRESS:
            self.parent.willexecutors_list[edit_key]["info"] = text
        self.update()

    def update(self):
        if self.parent.willexecutors_list is None:
            return

        current_key = self.get_role_data_for_current_item(col=self.Columns.URL, role=self.ROLE_HEIR_KEY)
        self.model().clear()
        self.update_headers(self.__class__.headers)




        set_current = None

        for url, value in self.parent.willexecutors_list.items():
            #self.ping_server(url)
            print("new value",url,value)
            labels = [""] * len(self.Columns)
            labels[self.Columns.URL] = url 
            if url in self.selected:
                labels[self.Columns.SELECTED] = [read_QIcon('confirmed.png'),'']
            else:
                labels[self.Columns.SELECTED] = ''
            labels[self.Columns.BASE_FEE] = decode_amount(value.get('base_fee',0),self.config.get_decimal_point())
            if str(value.get('status',0)) == "200":
                labels[self.Columns.STATUS] = [read_QIcon('status_connected.png'),'']
            else:
                labels[self.Columns.STATUS] = [read_QIcon('unconfirmed.png'),'']
            labels[self.Columns.ADDRESS] = str(value.get('info',''))
            
            items=[]
            for e in labels:
                if type(e)== list:
                    try:
                        items.append(QStandardItem(*e))
                    except Exception as e:
                        print("e cazzo",e)
                else:
                    items.append(QStandardItem(e))
            items[self.Columns.SELECTED].setEditable(False)
            items[self.Columns.URL].setEditable(True)
            items[self.Columns.ADDRESS].setEditable(True)
            items[self.Columns.BASE_FEE].setEditable(True)
            items[self.Columns.STATUS].setEditable(False)

            items[self.Columns.URL].setData(url, self.ROLE_HEIR_KEY+1)
            items[self.Columns.BASE_FEE].setData(url, self.ROLE_HEIR_KEY+2)
            items[self.Columns.ADDRESS].setData(url, self.ROLE_HEIR_KEY+3)


            self.model().insertRow(self.model().rowCount(), items)
            if url == current_key:
                idx = self.model().index(row_count, self.Columns.NAME)
                set_current = QPersistentModelIndex(idx)
            self.set_current_idx(set_current)



    def ping_servers(self):
        for url in self.parent.willexecutors_list:
            self.ping_server(url)

    def ping_server(self,url):
            try:
                print("ping ",url)
                res=urllib.request.urlopen(url)
                self.parent.willexecutors_list[url]['status']=res.status 
            except Exception as e: print(f"error {e} \n url:{url}")

           


def get_willexecutors_list_from_json(config):
    try:
        with open("willexecutors.json") as f:
            h = json.load(f)
            config.set_key(BalPlugin.WILLEXECUTORS,h,save=True)
            return h
    except Exception as e:
        print("errore aprendo willexecutors.json:",e)
        return {}

class WillExecutorDialog(QDialog,MessageBoxMixin):
    def __init__(self, bal_window):
        QDialog.__init__(self)
        self.bal_plugin = bal_window.bal_plugin
        self.gui_object = self.bal_plugin.gui_object
        self.config = self.bal_plugin.config
        self.window = bal_window.window
        self.willexecutors_list = self.bal_plugin.config_get(BalPlugin.WILLEXECUTORS) or {
            'https://bitcoinafter.life/': {
                "base_fee": 100000,
                "status": 0,
                "info":"Bitcoin After Life Will Executor"
            }
        }
        
        self.setWindowTitle(_('WillExecutor Service List'))
        self.setMinimumSize(800, 200)
        self.size_label = QLabel()
        self.willexecutor_list = WillExecutorList(self)

        vbox = QVBoxLayout(self)
        vbox.addWidget(self.size_label)
        vbox.addWidget(self.willexecutor_list)
        buttonbox = QHBoxLayout()

        b = QPushButton(_('Import'))
        b.clicked.connect(self.import_file)
        buttonbox.addWidget(b)

        b = QPushButton(_('Export'))
        b.clicked.connect(self.export_file)
        buttonbox.addWidget(b)

        b = QPushButton(_('Add'))
        b.clicked.connect(self.add)
        buttonbox.addWidget(b)
        
        b = QPushButton(_('Close'))
        b.clicked.connect(self.close)
        buttonbox.addWidget(b)

        vbox.addLayout(buttonbox)

        self.willexecutor_list.update()

    def add(self):
        self.willexecutors_list["http://localhost:8080"]={"info":"New Will Executor","base_fee":0,"status":"-1"}
        self.willexecutor_list.update()     

    def import_file(self):
        import_meta_gui(self, _('willexecutors'), self.import_json_file, self.willexecutors_list.update)

    def export_file(self, path):
        export_meta_gui(self, _('willexecutors'), self.export_json_file)

    def export_json_file(self,path):
        write_json_file(path, self.willexecutors_list)


    def import_json_file(self, path):
        data = read_json_file(path)
        data = self._validate(data)
        self.willexecutors_list.update(data)
        self.willexecutor_list.update()

    #TODO validate willexecutor json import file
    def _validate(self,data):
        return data

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
    
