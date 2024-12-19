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
from datetime import datetime

from . import qt_resources
if qt_resources.QT_VERSION == 5:
    from PyQt5.QtGui import QStandardItemModel, QStandardItem
    from PyQt5.QtCore import Qt, QPersistentModelIndex, QModelIndex
    from PyQt5.QtWidgets import (QAbstractItemView, QMenu,QWidget,QHBoxLayout,QLabel,QSpinBox,QPushButton)
else:
    from PyQt6.QtGui import QStandardItemModel, QStandardItem
    from PyQt6.QtCore import Qt, QPersistentModelIndex, QModelIndex
    from PyQt6.QtWidgets import (QAbstractItemView, QMenu,QWidget,QHBoxLayout,QLabel,QSpinBox,QPushButton)

from electrum.i18n import _
from electrum.bitcoin import is_address
from electrum.util import block_explorer_URL 
from electrum.plugin import run_hook
from electrum.gui.qt.util import webopen, MessageBoxMixin,HelpButton
from electrum.gui.qt.my_treeview import MyTreeView, MySortModel

from .. import util as Util
from .locktimeedit import HeirsLockTimeEdit
if TYPE_CHECKING:
    from electrum.gui.qt.main_window import ElectrumWindow


class HeirList(MyTreeView,MessageBoxMixin):

    class Columns(MyTreeView.BaseColumnsEnum):
        NAME = enum.auto()
        ADDRESS = enum.auto()
        AMOUNT = enum.auto()

    headers = {
        Columns.NAME: _('Name'),
        Columns.ADDRESS: _('Address'),
        Columns.AMOUNT: _('Amount'),
        #Columns.LOCKTIME:_('LockTime'),
    }
    filter_columns = [Columns.NAME, Columns.ADDRESS]

    ROLE_SORT_ORDER = Qt.ItemDataRole.UserRole + 1000

    ROLE_HEIR_KEY = Qt.ItemDataRole.UserRole + 1001
    key_role = ROLE_HEIR_KEY

    def __init__(self, bal_window: 'BalWindow'):
        super().__init__(
            parent=bal_window.window,
            main_window=bal_window.window,
            stretch_column=self.Columns.NAME,
            editable_columns=[self.Columns.NAME,self.Columns.ADDRESS,self.Columns.AMOUNT],
        )
        self.decimal_point = bal_window.bal_plugin.config.get_decimal_point()
        self.bal_window = bal_window

        try:
            self.setModel(QStandardItemModel(self))
            self.sortByColumn(self.Columns.NAME, Qt.SortOrder.AscendingOrder)
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        except:
            pass
            #self.sortByColumn(self.Columns.NAME, Qt.SortOrder.AscendingOrder)
            #self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self.setSortingEnabled(True)
        self.std_model = self.model()

        self.update()
    

    def on_edited(self, idx, edit_key, *, text):
        original = prior_name = self.bal_window.heirs.get(edit_key)
        if not prior_name:
            return
        col = idx.column()
        try:
            #if col == 3:
            #    try:
            #        text = Util.str_to_locktime(text)
            #    except:
            #        print("not a valid locktime")
            #        pass
            if col == 2:
                text = Util.encode_amount(text,self.decimal_point)
            elif col == 0:
                self.bal_window.delete_heirs([edit_key])
                edit_key = text
            prior_name[col-1] = text
            prior_name.insert(0,edit_key)
            prior_name = tuple(prior_name)
        except Exception as e:
            #print("eccezione tupla",e)
            prior_name = (edit_key,)+prior_name[:col-1]+(text,)+prior_name[col:]
        #print("prior_name",prior_name,original)
       
        try:
            self.bal_window.set_heir(prior_name)
            #print("setheir")
        except Exception as e:
            pass

            #print("heir non valido ripristino l'originale",e)
            try:
                #print("setup_original",(edit_key,)+original)
                self.bal_window.set_heir((edit_key,)+original)
            except Exception as e:
                #print("errore nellimpostare original",e,original)
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
            menu.addAction(_("Delete"), lambda: self.bal_window.delete_heirs(selected_keys))
        menu.exec(self.viewport().mapToGlobal(position))

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
            labels[self.Columns.AMOUNT] = Util.decode_amount(heir[1],self.decimal_point)
            #labels[self.Columns.LOCKTIME] =  str(Util.locktime_to_str(heir[2]))

            items = [QStandardItem(x) for x in labels]
            items[self.Columns.NAME].setEditable(True)
            items[self.Columns.ADDRESS].setEditable(True)
            items[self.Columns.AMOUNT].setEditable(True)
            #items[self.Columns.LOCKTIME].setEditable(True)
            items[self.Columns.NAME].setData(key, self.ROLE_HEIR_KEY+1)
            items[self.Columns.ADDRESS].setData(key, self.ROLE_HEIR_KEY+2)
            items[self.Columns.AMOUNT].setData(key, self.ROLE_HEIR_KEY+3)
            #items[self.Columns.LOCKTIME].setData(key, self.ROLE_HEIR_KEY+4)

            self.model().insertRow(self.model().rowCount(), items)

            if key == current_key:
                idx = self.model().index(row_count, self.Columns.NAME)
                set_current = QPersistentModelIndex(idx)
        self.set_current_idx(set_current)
        # FIXME refresh loses sort order; so set "default" here:
        self.filter()
        run_hook('update_heirs_tab', self)

    def refresh_row(self, key, row):
        # nothing to update here
        pass

    def get_edit_key_from_coordinate(self, row, col):
        #print("role_data",self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY))
        #print(col)
        return self.get_role_data_from_coordinate(row, col, role=self.ROLE_HEIR_KEY+col+1) 
        return col

    def create_toolbar(self, config):
        toolbar, menu = self.create_toolbar_with_menu('')
        menu.addAction(_("&New Heir"), self.bal_window.new_heir_dialog)
        menu.addAction(_("Import"), self.bal_window.import_heirs)
        menu.addAction(_("Export"), lambda: self.bal_window.export_heirs())
        #menu.addAction(_("Build Traonsactions"), self.build_transactions)

        self.heir_locktime = HeirsLockTimeEdit(self.window(),0)
        def on_heir_locktime():
            if not self.heir_locktime.get_locktime():
                self.heir_locktime.set_locktime('1y')
            self.bal_window.will_settings['locktime'] = self.heir_locktime.get_locktime() if self.heir_locktime.get_locktime() else "1y"
            self.bal_window.bal_plugin.config.set_key('will_settings',self.bal_window.will_settings,save = True)
        self.heir_locktime.valueEdited.connect(on_heir_locktime)

        self.heir_threshold = HeirsLockTimeEdit(self,0)
        def on_heir_threshold():
            if not self.heir_threshold.get_locktime():
                self.heir_threshold.set_locktime('180d')

            self.bal_window.will_settings['threshold'] = self.heir_threshold.get_locktime() 
            self.bal_window.bal_plugin.config.set_key('will_settings',self.bal_window.will_settings,save = True)
        self.heir_threshold.valueEdited.connect(on_heir_threshold)

        self.heir_tx_fees = QSpinBox()
        self.heir_tx_fees.setMinimum(1)
        self.heir_tx_fees.setMaximum(10000)
        def on_heir_tx_fees():
            if not self.heir_tx_fees.value():
                self.heir_tx_fees.set_value(1)
            self.bal_window.will_settings['tx_fees'] = self.heir_tx_fees.value()
            self.bal_window.bal_plugin.config.set_key('will_settings',self.bal_window.will_settings,save = True)
        self.heir_tx_fees.valueChanged.connect(on_heir_tx_fees)


        self.heirs_widget = QWidget()
        layout = QHBoxLayout()
        self.heirs_widget.setLayout(layout)
        
        layout.addWidget(QLabel(_("Delivery Time:")))
        layout.addWidget(self.heir_locktime)
        layout.addWidget(HelpButton(_("Locktime* to be used in the transaction\n"
                                    +"if you choose Raw, you can insert various options based on suffix:\n"
                                    #+" - b: number of blocks after current block(ex: 144b means tomorrow)\n"
                                    +" - d: number of days after current day(ex: 1d means tomorrow)\n"
                                    +" - y: number of years after currrent day(ex: 1y means one year from today)\n"
                                    +"* locktime can be anticipated to update will\n")))

        layout.addWidget(QLabel(" "))
        layout.addWidget(QLabel(_("Check Alive:")))
        layout.addWidget(self.heir_threshold)
        layout.addWidget(HelpButton(_("Check  to ask for invalidation.\n"
                                    +"When less then this time is missing, ask to invalidate.\n"
                                    +"If you fail to invalidate during this time, your transactions will be delivered to your heirs.\n"
                                    +"if you choose Raw, you can insert various options based on suffix:\n"
                                    #+" - b: number of blocks after current block(ex: 144b means tomorrow)\n"
                                    +" - d: number of days after current day(ex: 1d means tomorrow).\n"
                                    +" - y: number of years after currrent day(ex: 1y means one year from today).\n\n")))
        layout.addWidget(QLabel(" "))
        layout.addWidget(QLabel(_("Fees:")))
        layout.addWidget(self.heir_tx_fees)
        layout.addWidget(HelpButton(_("Fee to be used in the transaction")))
        layout.addWidget(QLabel("sats/vbyte"))
        layout.addWidget(QLabel(" "))
        newHeirButton = QPushButton(_("New Heir"))
        newHeirButton.clicked.connect(self.bal_window.new_heir_dialog)
        layout.addWidget(newHeirButton)

        toolbar.insertWidget(2, self.heirs_widget)

        return toolbar
    def update_will_settings(self):
        self.heir_threshold.set_locktime(self.bal_window.will_settings['threshold'])
        self.heir_locktime.set_locktime(self.bal_window.will_settings['locktime'])
        self.heir_tx_fees.setValue(int(self.bal_window.will_settings['tx_fees']))

    def build_transactions(self):
        will = self.bal_window.prepare_will()

