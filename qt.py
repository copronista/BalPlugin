'''

Bal
Do you have something to hide?
Secret backup plug-in for the electrum wallet.

Copyright:
    2017 Tiago Romagnani Silveira
    2023 Soren Stoutner <soren@debian.org>

Distributed under the MIT software license, see the accompanying
file LICENCE or http://www.opensource.org/licenses/mit-license.php

'''

import os
import random
import traceback
from decimal import Decimal
from functools import partial
import sys

from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtCore import Qt, QRectF, QRect, QSizeF, QUrl, QPoint, QSize
from PyQt5.QtGui import (QPixmap, QImage, QBitmap, QPainter, QFontDatabase, QPen, QFont,
                         QColor, QDesktopServices, qRgba, QPainterPath)
from PyQt5.QtWidgets import (QGridLayout, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit,QCheckBox,QSpinBox,QMenuBar,QMenu,QLineEdit)

from electrum.plugin import hook
from electrum.i18n import _
from electrum.util import make_dir, InvalidPassword, UserCancelled
from electrum.gui.qt.util import (read_QIcon, EnterButton, WWLabel, icon_path,
                                  WindowModalDialog, Buttons, CloseButton, OkButton,import_meta_gui,export_meta_gui,char_width_in_lineedit,CancelButton)
from electrum.gui.qt.qrtextedit import ScanQRTextEdit
from electrum.gui.qt.main_window import StatusBarButton
from .amountedit import PercAmountEdit
from .bal import BalPlugin
from .heirs import Heirs
from .locktimeedit import HeirsLockTimeEdit

class Plugin(BalPlugin):

    def __init__(self, parent, config, name):
        BalPlugin.__init__(self, parent, config, name)
        self.bal_windows={}

    @hook
    def init_qt(self,gui_object):
        self.gui_object=gui_object
        for window in gui_object.windows:
            self.bal_windows[window.winId]= BalWindow(self,window)
            for child in window.children():
                if isinstance(child,QMenuBar):
                    for menu_child in child.children():
                        if isinstance(menu_child,QMenu):
                            print(dir(menu_child))
                            try:
                                print(menu_child.title())
                                if menu_child.title()==_("&Tools"):
                                    for menu_item in menu_child.children():
                                        pass
                                        
                            except:
                                print("except:",menu_child.text())
                                

            tools_menu = window.getMenuBar()
            print(dir(tools_menu))
            self.init_menubar_tools(self,window,window.tools_menu)

    @hook
    def create_status_bar(self, sb):
        return
        b = StatusBarButton(read_QIcon('bal.png'), "Bal "+_("Bitcoin After Life"),
                            partial(self.setup_dialog, sb), sb.height())
        sb.addPermanentWidget(b)

    @hook
    def init_menubar_tools(self,window,tools_menu):
        w = self.get_window(window)
        w.init_menubar_tools(tools_menu)

    def get_window(self,window):
        w = self.bal_windows.get(window.winId,None)
        if w is None:
            w=BalWindow(self,window)
            self.bal_windows[window.winId]=w
        return w
  
    def requires_settings(self):
        return True
    
    def settings_widget(self, window):
        print("questo mi darebbe la finestra quando attivo il plugin")
        w=self.get_window(window)
        return EnterButton(_('Settings'), partial(w.settings_dialog))

    def password_dialog(self, msg=None, parent=None):
        from electrum.gui.qt.password_dialog import PasswordDialog
        parent = parent or self
        d = PasswordDialog(parent, msg)
        return d.run()

    def get_seed(self):
        password = None
        if self.wallet.has_keystore_encryption():
            password = self.password_dialog(parent=self.d.parent())
            if not password:
                raise UserCancelled()

        keystore = self.wallet.get_keystore()
        if not keystore or not keystore.has_seed():
            return
        self.extension = bool(keystore.get_passphrase(password))
        return keystore.get_seed(password)

    def on_close(self):
        print("close plugin")
        try:
            for window in self.windows:
                window.heirs_tab.close()
                window.tabs.removeTab(self.heirs_tab)
                window.tools_menu.removeAction(_("&Will Executors"))
        except Exception as e:
            print("error closing plugin",e)
            
class BalWindow:
    def __init__(self,bal_plugin: 'BalPlugin',window: 'ElectrumWindow'):
        self.bal_plugin = bal_plugin
        self.window = window

    def init_menubar_tools(self,tools_menu):
        self.tools_menu=tools_menu
        self.heirs=Heirs(self.window.wallet.db)

        tools_menu.addSeparator()
        tools_menu.addAction(_("&Will Executors"), self.willexecutor_dialog)
        self.heirs_tab = self.create_heirs_tab()

        def add_optional_tab(tabs, tab, icon, description):
            tab.tab_icon = icon
            tab.tab_description = description
            tab.tab_pos = len(tabs)
            if tab.is_shown_cv:
                tabs.addTab(tab, icon, description.replace("&", ""))

        add_optional_tab(self.window.tabs, self.heirs_tab, read_QIcon("will.png"), _("&Heirs"))

    def get_window_title(self,title):
        return _('BAL - ') + _(title) 

    def willexecutor_dialog(self):
        from .willexecutor_dialog import WillExecutorDialog
        h = WillExecutorDialog(self)
        h.exec_()

    def create_heirs_tab(self):
        from .heir_list import HeirList
        self.heir_list = l = HeirList(self)
        tab = self.window.create_list_tab(l)
        tab.is_shown_cv = True
        return tab

    def new_heir_dialog(self):
        d = WindowModalDialog(self.window, self.get_window_title("New heir"))
        vbox = QVBoxLayout(d)
        grid = QGridLayout()

        heir_name = QLineEdit()
        heir_name.setFixedWidth(32 * char_width_in_lineedit())
        heir_address = QLineEdit()
        heir_address.setFixedWidth(32 * char_width_in_lineedit())

        heir_amount = PercAmountEdit(self.window.get_decimal_point)
        heir_locktime = HeirsLockTimeEdit(self.window,0)
        #line4.setFixedWidth(32 * char_width_in_lineedit())

        heir_is_xpub = QCheckBox()

        grid.addWidget(QLabel(_("Name")), 1, 0)
        grid.addWidget(heir_name, 1, 1)

        grid.addWidget(QLabel(_("Address")), 2, 0)
        grid.addWidget(heir_address, 2, 1)

        #grid.addWidget(QLabel(_("xPub")), 2, 2)
        grid.addWidget(QLabel(_("Amount")),3,0)
        grid.addWidget(heir_amount,3,1)
        grid.addWidget(QLabel(_("LockTime")), 4, 0)
        grid.addWidget(heir_locktime, 4, 1)

        vbox.addLayout(grid)
        vbox.addLayout(Buttons(CancelButton(d), OkButton(d)))
        if d.exec_():
            #TODO SAVE HEIR
            heir = [
                    heir_name.text(),
                    heir_address.text(),
                    heir_amount.text(),
                    str(heir_locktime.get_locktime()),
                    ]
            self.set_heir(heir)

    def export_inheritance_handler(self,path):
        txs = self.build_inheritance_transaction()
        with open(path,"w") as f:
            for tx in txs:
                f.write(str(tx))
                f.write('\n')
 
    def set_heir(self,heir):
        self.heirs[heir[0]]=heir[1:]
        self.heir_list.update()
        return True
    
    def import_heirs(self,):
        import_meta_gui(self.window, _('heirs'), self.heirs.import_file, self.heir_list.update)

    def export_heirs(self):
        export_meta_gui(self.window, _('heirs'), self.heirs.export_file)

                   
    def build_inheritance_transaction(self):
        password=None
        if self.window.wallet.has_keystore_encryption():            
            password = self.bal_plugin.password_dialog(parent=self.window)
            #password = self.window.wallet.password
        
        txs = self.heirs.buildTransactions(self.bal_plugin,self.window.wallet)
        if len(txs)>0:
            if self.bal_plugin.config_get(BalPlugin.PREVIEW):
                self.preview_dialog(txs)
            elif self.bal_plugin.config_get(BalPlugin.BROADCAST):
                if self.bal_plugin.config_get(BalPlugin.ASK_BROADCAST):
                    self.preview_dialog(txs)


        self.window.history_list.update()
        self.window.utxo_list.update()
        self.window.labels_changed_signal.emit()
        return txs


    def export_inheritance_transactions(self):
        try:
            export_meta_gui(self.window, _('heirs_transactions'), self.export_inheritance_handler)
        except Exception as e:
            self.window.show_error(str(e))
            raise e
            return

    def settings_dialog(self):
        d = WindowModalDialog(self.window, self.get_window_title("Settings"))

        d.setMinimumSize(100, 200)

        heir_locktime_time = QSpinBox()
        heir_locktime_time.setMinimum(0)
        heir_locktime_time.setMaximum(3650)
        heir_locktime_time.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIME_TIME)))

        heir_locktimedelta_time = QSpinBox()
        heir_locktimedelta_time.setMinimum(0)
        heir_locktimedelta_time.setMaximum(3650)
        heir_locktimedelta_time.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIMEDELTA_TIME)))

        heir_locktime_blocks = QSpinBox()
        heir_locktime_blocks.setMinimum(0)
        heir_locktime_blocks.setMaximum(144*3650)
        heir_locktime_blocks.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIME_BLOCKS)))

        heir_locktimedelta_blocks = QSpinBox()
        heir_locktimedelta_blocks.setMinimum(0)
        heir_locktimedelta_blocks.setMaximum(144*3650)
        heir_locktimedelta_blocks.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIMEDELTA_BLOCKS)))

        heir_tx_fees = QSpinBox()
        heir_tx_fees.setMinimum(1)
        heir_tx_fees.setMaximum(10000)
        heir_tx_fees.setValue(int(self.bal_plugin.config_get(BalPlugin.TX_FEES)))

        heir_broadcast = bal_checkbox(self.bal_plugin, BalPlugin.BROADCAST)
        heir_ask_broadcast = bal_checkbox(self.bal_plugin, BalPlugin.ASK_BROADCAST)
        heir_invalidate = bal_checkbox(self.bal_plugin, BalPlugin.INVALIDATE)
        heir_ask_invalidate = bal_checkbox(self.bal_plugin, BalPlugin.ASK_INVALIDATE)
        heir_preview = bal_checkbox(self.bal_plugin, BalPlugin.PREVIEW)
        

        grid=QGridLayout(d)
        add_widget(grid,"Refresh Time Days",heir_locktime_time,0)
        add_widget(grid,"Refresh Blocks",heir_locktime_blocks,1)
        add_widget(grid,"Transaction fees",heir_tx_fees,2)
        add_widget(grid,"Broadcast transactions",heir_broadcast,3)
        add_widget(grid," - Ask before",heir_ask_broadcast,4)
        add_widget(grid,"Invalidate transactions",heir_invalidate,5)
        add_widget(grid," - Ask before",heir_ask_invalidate,6)
        add_widget(grid,"Show preview before sign",heir_preview,7)
        add_widget(grid,"Max Allowed TimeDelta Days",heir_locktimedelta_time,8)
        add_widget(grid,"Max Allowed BlocksDelta",heir_locktimedelta_blocks,9)


        if not d.exec_():
            return
    #TODO IMPLEMENT PREVIEW DIALOG
    #tx list display txid, willexecutor, qrcode, button to sign
    def preview_dialog(self, txs):
        d = WindowModalDialog(self.window, self.get_window_title("Transactions Preview"))
        d.setMinimumSize(100, 200)
        i=0
        grid=QGridLayout(d)
        for tx in txs:
            grid.addWidget(QLabel(_(tx.txid())),i,0)
            b = QPushButton(_('Details'))
            b.clicked.connect(partial(self.window.show_transaction,tx))
            grid.addWidget(b,i,1)
            i+=1

        if not d.exec_():
            return

class bal_checkbox(QCheckBox):
    def __init__(self, plugin,variable):
        QCheckBox.__init__(self)
        self.setChecked(plugin.config_get(variable))
        def on_check(v):
            plugin.config.set_key(variable, v == QT.Checked, save=True)
        self.stateChanged.connect(on_check)
    
        
def add_widget(grid,label,widget,row):
    grid.addWidget(QLabel(_(label)),row,0)
    grid.addWidget(widget,row,1)
