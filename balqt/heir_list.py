#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2015 Thomas Voegtlin
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
from typing import TYPE_CHECKING

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QPersistentModelIndex, QModelIndex
from PyQt5.QtWidgets import (QAbstractItemView, QMenu)

from electrum.i18n import _
from electrum.bitcoin import is_address
from electrum.util import block_explorer_URL
from electrum.plugin import run_hook

from electrum.gui.qt.util import webopen, MessageBoxMixin
from electrum.gui.qt.my_treeview import MyTreeView
from datetime import datetime
from ..util import str_to_locktime,locktime_to_str,encode_amount,decode_amount
if TYPE_CHECKING:
    from electrum.gui.qt.main_window import ElectrumWindow


class HeirList(MyTreeView,MessageBoxMixin):

    class Columns(MyTreeView.BaseColumnsEnum):
        NAME = enum.auto()
        ADDRESS = enum.auto()
        AMOUNT = enum.auto()
        LOCKTIME = enum.auto()

    headers = {
        Columns.NAME: _('Name'),
        Columns.ADDRESS: _('Address'),
        Columns.AMOUNT: _('Amount'),
        Columns.LOCKTIME:_('LockTime'),
    }
    filter_columns = [Columns.NAME, Columns.ADDRESS]

    ROLE_HEIR_KEY = Qt.UserRole + 2000
    key_role = ROLE_HEIR_KEY

    def __init__(self, bal_window: 'BalWindow'):
        super().__init__(
            parent=bal_window.window,
            main_window=bal_window.window,
            stretch_column=self.Columns.NAME,
            editable_columns=[self.Columns.ADDRESS,self.Columns.AMOUNT,self.Columns.LOCKTIME],
        )
        self.decimal_point = bal_window.bal_plugin.config.get_decimal_point()
        self.bal_window = bal_window
        self.setModel(QStandardItemModel(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.std_model = self.model()
        self.update()

    def on_edited(self, idx, edit_key, *, text):
        print("self",self)
        print("idx",idx)
        print("edit key",edit_key)
        print("text",text)
       
        original = prior_name = self.bal_window.heirs.get(edit_key)
        print("prior_name",prior_name,text)
        if not prior_name:
            return
        col = idx.column()
        print("column",col,self.Columns.LOCKTIME)
        try:
            if col == 3:
                try:
                    text = str_to_locktime(text)
                except:
                    print("not a valid locktime")
                    pass
            if col == 2:
                text = encode_amount(text,self.decimal_point)
            else:
                print("porco dio di colonna",col)
            prior_name[col-1] = text
            prior_name.insert(0,edit_key)
            prior_name = tuple(prior_name)
        except Exception as e:
            print("eccezione tupla",e)
            prior_name = (edit_key,)+prior_name[:col-1]+(text,)+prior_name[col:]
        print("prior_name",prior_name,original)
       
        try:
            self.bal_window.set_heir(prior_name)
            print("setheir")
        except Exception as e:

            print("heir non valido ripristino l'originale",e)
            try:
                print("setup_original",(edit_key,)+original)
                self.bal_window.set_heir((edit_key,)+original)
            except:
                print("errore nellimpostare original",original)
                self.update()

    def create_menu(self, position):
        menu = QMenu()
        idx = self.indexAt(position)
        column = idx.column() or self.Columns.NAME
        selected_keys = []
        for s_idx in self.selected_in_column(self.Columns.NAME):
            #print(s_idx)
            sel_key = self.model().itemFromIndex(s_idx).data(0)
            selected_keys.append(sel_key)
        if selected_keys and idx.isValid():
            column_title = self.model().horizontalHeaderItem(column).text()
            column_data = '\n'.join(self.model().itemFromIndex(s_idx).text()
                                    for s_idx in self.selected_in_column(column))
            menu.addAction(_("Copy {}").format(column_title), lambda: self.place_text_on_clipboard(column_data, title=column_title))
            if column in self.editable_columns:
                item = self.model().itemFromIndex(idx)
                if item.isEditable():
                    # would not be editable if openalias
                    persistent = QPersistentModelIndex(idx)
                    menu.addAction(_("Edit {}").format(column_title), lambda p=persistent: self.edit(QModelIndex(p)))
            menu.addAction(_("Pay to"), lambda: self.bal_window.payto_heirs(selected_keys))
            menu.addAction(_("Delete"), lambda: self.bal_window.delete_heirs(selected_keys))
            URLs = [block_explorer_URL(self.config, 'addr', key) for key in filter(is_address, selected_keys)]
            if URLs:
                menu.addAction(_("View on block explorer"), lambda: [webopen(u) for u in URLs])

        run_hook('create_heir_menu', menu, selected_keys, self.bal_window)
        menu.exec_(self.viewport().mapToGlobal(position))

    def update(self):
        if self.maybe_defer_update():
            return
        current_key = self.get_role_data_for_current_item(col=self.Columns.NAME, role=self.ROLE_HEIR_KEY)
        self.model().clear()
        self.update_headers(self.__class__.headers)
        set_current = None
        for key in sorted(self.bal_window.heirs.keys()):
            heir = self.bal_window.heirs[key]
            labels = [""] * len(self.Columns)
            labels[self.Columns.NAME] = key
            labels[self.Columns.ADDRESS] = heir[0]
            labels[self.Columns.AMOUNT] = decode_amount(heir[1],self.decimal_point)
            labels[self.Columns.LOCKTIME] =  str(locktime_to_str(heir[2]))

            items = [QStandardItem(x) for x in labels]
            items[self.Columns.NAME].setEditable(False)
            items[self.Columns.ADDRESS].setEditable(True)
            items[self.Columns.AMOUNT].setEditable(True)
            items[self.Columns.LOCKTIME].setEditable(True)
            items[self.Columns.NAME].setData(key, self.ROLE_HEIR_KEY+1)
            items[self.Columns.ADDRESS].setData(key, self.ROLE_HEIR_KEY+2)
            items[self.Columns.AMOUNT].setData(key, self.ROLE_HEIR_KEY+3)
            items[self.Columns.LOCKTIME].setData(key, self.ROLE_HEIR_KEY+4)
            row_count = self.model().rowCount()
            self.model().insertRow(row_count, items)
            if key == current_key:
                idx = self.model().index(row_count, self.Columns.NAME)
                set_current = QPersistentModelIndex(idx)
        self.set_current_idx(set_current)
        # FIXME refresh loses sort order; so set "default" here:
        self.sortByColumn(self.Columns.NAME, Qt.AscendingOrder)
        self.filter()
        run_hook('update_heirs_tab', self)

    def refresh_row(self, key, row):
        # nothing to update here
        pass

    def get_edit_key_from_coordinate(self, row, col):
        if col == self.Columns.NAME:
            return None
        #print("role_data",self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY))
        #print(col)
        return self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col+1) 
        return col

    def create_toolbar(self, config):
        toolbar, menu = self.create_toolbar_with_menu('')
        menu.addAction(_("&New Heir"), self.bal_window.new_heir_dialog)
        menu.addAction(_("Import"), self.bal_window.import_heirs)
        menu.addAction(_("Export"), lambda: self.bal_window.export_heirs())
        menu.addAction(_("Build Transactions"), self.build_transactions)
        return toolbar
    def build_transactions(self):
        will = self.bal_window.build_inheritance_transaction(ignore_duplicate=False,keep_original = False)
        if len(will) ==0:
            self.window.show_message(_("no tx to be created"))

