'''

Bal

Bitcoin after life


'''

import os
import random
import traceback
from functools import partial
import sys
import copy

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
                                  WindowModalDialog, Buttons, CloseButton, OkButton,import_meta_gui,export_meta_gui,char_width_in_lineedit,CancelButton,HelpButton)
from electrum.gui.qt.qrtextedit import ScanQRTextEdit
from electrum.gui.qt.main_window import StatusBarButton
from electrum.gui.qt.password_dialog import PasswordDialog

from .bal import BalPlugin
from .heirs import Heirs
from .util import Util
from .will import Will, WillExpiredException,NotCompleteWillException
from .balqt.locktimeedit import HeirsLockTimeEdit
from .balqt.willexecutor_dialog import WillExecutorDialog
from .balqt.preview_dialog import PreviewDialog,PreviewList
from .balqt.heir_list import HeirList
from .balqt.amountedit import PercAmountEdit
from electrum.transaction import tx_from_any
from time import time
import datetime
class Plugin(BalPlugin):

    def __init__(self, parent, config, name):
        BalPlugin.__init__(self, parent, config, name)
        self.bal_windows={}


    @hook
    def init_qt(self,gui_object):
        
        try:
            self.gui_object=gui_object
            for window in gui_object.windows:
                wallet = window.wallet
                w = BalWindow(self,window)
                self.bal_windows[window.winId]= w
                for child in window.children():
                    if isinstance(child,QMenuBar):
                        for menu_child in child.children():
                            if isinstance(menu_child,QMenu):
                                try:
                                    print(menu_child.title())
                                    if menu_child.title()==_("&Tools"):
                                        w.init_menubar_tools(menu_child)
                                            
                                except:
                                    print("except:",menu_child.text())
                                    
        except Exception as e:
            print("Error loading plugin",e)
            Util.print_var(window)
            Util.print_var(window.window())



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

    @hook
    def on_close_window(self,window):
            #Util.print_var(window)
            w = self.get_window(window)
            w.build_inheritance_transaction(ignore_duplicate=True,keep_original=True)
            


    def get_window(self,window):
        w = self.bal_windows.get(window.winId,None)
        if w is None:
            w=BalWindow(self,window)
            self.bal_windows[window.winId]=w
        return w
  
    def requires_settings(self):
        return True
    
    def settings_widget(self, window):
        w=self.get_window(window.window)
        #w.window.show_message(_("please reastart electrum to activate BalPlugin"))
        return EnterButton(_('Settings'), partial(w.settings_dialog))

    def password_dialog(self, msg=None, parent=None):
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
            for winid,bal_window in self.bal_windows.items():
                print(1)
                window=bal_window.window
                print(2)
                bal_window.heirs_tab.close()
                print(3)
                bal_window.will_tab.close()
                print(4)
                window.toggle_tab(bal_window.heirs_tab)
                print(5)
                window.toggle_tab(bal_window.will_tab)
                print(6)

                #Util.print_var(window.tabs)
                window.tabs.update()
                bal_window.will_tab.hide()
                #window.tabs.removeTab(bal_window.will_tab.tab_pos-1)
                print(7)
                #Util.print_var(bal_window.tools_menu.willexecutors_action)
                bal_window.tools_menu.removeAction(bal_window.tools_menu.willexecutors_action)
        except Exception as e:
            print("error closing plugin",e)
            
class BalWindow():
    def __init__(self,bal_plugin: 'BalPlugin',window: 'ElectrumWindow'):
        self.bal_plugin = bal_plugin
        self.window = window
        self.wallet = self.window.wallet
        self.heirs = Heirs._validate(Heirs(self.wallet.db))
        self.will=self.wallet.db.get_dict("will")
        Will.normalize_will(self.will,self.wallet)
        for txid,willtx in self.will.items():
            if isinstance(willtx['tx'],str):
                tx=tx_from_any(willtx['tx'])
                willtx['tx']=tx
            self.add_info_from_will(willtx['tx'])
        


        self.heirs_tab = self.create_heirs_tab()
        self.will_tab = self.create_will_tab()
        print(self.window.windowTitle())

    def init_menubar_tools(self,tools_menu):
        self.tools_menu=tools_menu

        def add_optional_tab(tabs, tab, icon, description):
            tab.tab_icon = icon
            tab.tab_description = description
            tab.tab_pos = len(tabs)
            if tab.is_shown_cv:
                tabs.addTab(tab, icon, description.replace("&", ""))

        add_optional_tab(self.window.tabs, self.heirs_tab, read_QIcon("will.png"), _("&Heirs"))
        add_optional_tab(self.window.tabs, self.will_tab, read_QIcon("will.png"), _("&Will"))
        tools_menu.addSeparator()
        self.tools_menu.willexecutors_action = tools_menu.addAction(_("&Will Executors"), self.willexecutor_dialog)

    def get_window_title(self,title):
        return _('BAL - ') + _(title) 

    def willexecutor_dialog(self):
        h = WillExecutorDialog(self)
        h.exec_()

    def create_heirs_tab(self):
        self.heir_list = l = HeirList(self)
        tab = self.window.create_list_tab(l)
        tab.is_shown_cv = True
        return tab

    def create_will_tab(self):
        self.will_list = l = PreviewList(self,None)
        tab = self.window.create_list_tab(l)
        tab.is_shown_cv = True
        #self.will_tab.update_will(self.will)
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
        grid.addWidget(HelpButton("Unique name or description about heir"),1,2)

        grid.addWidget(QLabel(_("Address")), 2, 0)
        grid.addWidget(heir_address, 2, 1)
        grid.addWidget(HelpButton("heir bitcoin address"),2,2)

        #grid.addWidget(QLabel(_("xPub")), 2, 2)
        grid.addWidget(QLabel(_("Amount")),3,0)
        grid.addWidget(heir_amount,3,1)
        grid.addWidget(HelpButton("Fixed or Percentage amount if end with %"),3,2)

        grid.addWidget(QLabel(_("LockTime")), 4, 0)
        grid.addWidget(heir_locktime, 4, 1)
        grid.addWidget(HelpButton("if you choose Raw, you can insert various options based on suffix:\n " 
                                  +" - b: number of blocks after current block(ex: 144b means tomorrow)\n" 
                                  +" - d: number of days after current day(ex: 1d means tomorrow)\n"  
                                  +" - y: number of years after currrent day(ex: 1y means one year from today)\n\n" 
                                  +"when using d or y time will be set to 00:00 for privacy reasons\n" 
                                  +"when used without suffix it can be used to indicate:\n" 
                                  +" - exact block(if value is less than 500,000,000)\n"
                                  +" - exact block timestamp(if value greater than 500,000,000"),4,2)

        vbox.addLayout(grid)
        vbox.addLayout(Buttons(CancelButton(d), OkButton(d)))
        while d.exec_():
            #TODO SAVE HEIR
            heir = [
                    heir_name.text(),
                    heir_address.text(),
                    Util.encode_amount(heir_amount.text(),self.bal_plugin.config.get_decimal_point()),
                    str(heir_locktime.get_locktime()),
                    ]
            try:
                self.set_heir(heir)
                break
            except Exception as e:
                self.window.show_error(str(e))

    def export_inheritance_handler(self,path):
        txs = self.build_inheritance_transaction(ignore_duplicate=True, keep_original=False)
        with open(path,"w") as f:
            for tx in txs:
                Util.print_var(tx)
                tx['status']+=BalPlugin.STATUS_EXPORTED
                f.write(str(tx['tx']))
                f.write('\n')
 
    def set_heir(self,heir):
        h=Heirs.validate_heir(heir[0],heir[1:])
        print("print_h",h)
        self.heirs[heir[0]]=h
        print("cazz")
        self.heir_list.update()
        return True

    def delete_heirs(self,heir):
        del self.heirs[heir[0]]
        self.heirs.save()
        self.heir_list.update()
        return True
    
    def import_heirs(self,):
        import_meta_gui(self.window, _('heirs'), self.heirs.import_file, self.heir_list.update)

    def export_heirs(self):
        export_meta_gui(self.window, _('heirs'), self.heirs.export_file)

    def prepare_will(self, ignore_duplicate = False, keep_original = False):
        will = self.build_inheritance_transaction(ignore_duplicate = ignore_duplicate, keep_original=keep_original)
        if not will or  len(will) == 0:
            self.window.show_message(_('no tx to be created'))
        return will
    def will_not_replaced_nor_invalidated(self):
        for k,v in self.will.items():
            if not BalPlugin.STATUS_REPLACED in v['status']:
                if not BalPlugin.STATUS_INVALIDATED in v['status']:
                        yield k

    def del_old_will(self,oldwilltodelete):
        print("del old will")
        new_old_will_to_delete=[]
        for did in oldwilltodelete:
            print(f"del: {did}")
            try:
                del self.will[did]
            except:
                print(f"trying to delete {did}: but failed")
            for oid in self.will:
                if Util.txid_in_utxo(did,self.will[oid]['tx'].inputs()):
                    print(f"append {oid} to be deleted")
                    new_old_will_to_delete.append(oid)
        if len(new_old_will_to_delete)>0:
            self.del_old_will(new_old_will_to_delete)
    
    def delete_not_valid(self,txid,s_utxo):
        try:
            self.will[txid]['status']+=BalPlugin.STATUS_INVALIDATED
            self.will[txid]['valid']=False
        except Exception as e:
            print(f"cannot invalidate {txid}")
            raise e

    def build_inheritance_transaction(self,ignore_duplicate = True, keep_original = True):
        try:
            locktime_time=self.bal_plugin.config_get(BalPlugin.LOCKTIME_TIME)
            locktime_blocks=self.bal_plugin.config_get(BalPlugin.LOCKTIME_BLOCKS)
            date_to_check = (datetime.datetime.now()+datetime.timedelta(days=locktime_time)).timestamp()
            current_block = Util.get_current_height(self.wallet.network)
            block_to_check = current_block + locktime_blocks
            will = {}
            willtodelete=[]
            willtoappend={}
            show_preview=False
            #for txid in self.will_not_replaced_nor_invalidated():
            #    if not self.will[txid]['status']==BalPlugin.STATUS_NEW:
            #        self.will[txid]['status']+=BalPlugin.STATUS_REPLACED
            #    else:
            #        willtodelete.append((None,txid))
            utxos=self.window.wallet.get_utxos()
            #current_will_is_valid = Util.is_will_valid(self.will, block_to_check, date_to_check, utxos)
            #print("current_will is valid",current_will_is_valid,self.will)
            try:
                Will.is_will_valid(self.will, block_to_check, date_to_check, self.window.wallet.get_utxos(),self.delete_not_valid)
            except WillExpiredException as e:
                tx = Will.invalidate_will(self.will)
                self.window.show_transaction(self.will[key]['tx'])

                self.window.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
                self.bal_window.window.show_transaction(tx)
            except NotCompleteWillException as e:
                self.window.show_message(_("Will is not complete some utxo was not included I will rebuild it"))
            try: 
                txs = self.heirs.get_transactions(self.bal_plugin,self.window.wallet,None,date_to_check)
                creation_time = time()
                if txs:
                    for txid in txs:
                        txtodelete=[]
                        _break = False
                        print(txid,txs[txid].description)
                        tx = {}
                        tx['tx'] = txs[txid]
                        tx['my_locktime'] = txs[txid].my_locktime
                        tx['heirsvalue'] = txs[txid].heirsvalue
                        tx['description'] = txs[txid].description
                        tx['willexecutor'] = txs[txid].willexecutor
                        tx['status'] = BalPlugin.STATUS_NEW
                        tx['exported'] = False
                        tx['broadcasted'] = False
                        tx['valid'] = True
                        tx['time'] = creation_time
                        tx['heirs'] = txs[txid].heirs
                        tx['txchildren'] = []
                        will[txid]=tx
                        

                        
                    Will.update_will(self.will,will)
                    Will.normalize_will(will)
                    Will.normalize_will(will)
                    print(will)
                    for nid in will:
                        txid=will[nid]['tx'].txid()
                        if not txid in self.will:
                            print("new txid:",txid,nid)
                            self.will[txid]=will[nid]
                    todelete=[]
                    for wid in self.will:
                        if wid != self.will[wid]['tx'].txid():
                            print("todelete",wid,self.will[wid]['tx'].txid())
                            todelete.append(wid)
                    for wid in todelete:
                        self.will[wid]=None
                        try:
                            del self.will[wid]
                        except:
                            print("was not present",wid)
                    for wid in self.will:
                        self.will[wid]=self.will[wid]
                    try:
                        Will.is_will_valid(self.will, block_to_check, date_to_check, self.window.wallet.get_utxos(),self.delete_not_valid)
                    except WillExpiredException as e:
                        tx = Will.invalidate_will(self.will)
                        self.window.show_transaction(self.will[key]['tx'])

                        self.window.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
                        self.bal_window.window.show_transaction(tx)
                    except NotCompleteWillException as e:
                        self.window.show_message(_("Will is not complete some utxo was not included for unknown reasons"))


                    



                if show_preview:
                    if self.bal_plugin.config_get(BalPlugin.PREVIEW):
                        self.preview_dialog(self.will)
                    elif self.bal_plugin.config_get(BalPlugin.BROADCAST):
                        if self.bal_plugin.config_get(BalPlugin.ASK_BROADCAST):
                            self.preview_dialog(self.will)

                self.window.history_list.update()
                self.window.utxo_list.update()
                try:
                    self.will_list.update_will(self.will)
                except: 
                    pass
                    #raise e
            except Exception as e:
                pass
                #print(e)
                #self.window.show_message(e)
                #raise e
            return self.will 
        except Exception as e:
            #print("ERROR: exception building transactions",e)
            #raise e
            pass


    def settings_dialog(self):
        d = WindowModalDialog(self.window, self.get_window_title("Settings"))

        d.setMinimumSize(100, 200)

        heir_locktime_time = QSpinBox()
        heir_locktime_time.setMinimum(0)
        heir_locktime_time.setMaximum(3650)
        heir_locktime_time.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIME_TIME)))
        def on_heir_locktime_time():
            value = heir_locktime_time.value()
            self.bal_plugin.config.set_key(BalPlugin.LOCKTIME_TIME,value,save=True)
        heir_locktime_time.valueChanged.connect(on_heir_locktime_time)

        heir_locktimedelta_time = QSpinBox()
        heir_locktimedelta_time.setMinimum(0)
        heir_locktimedelta_time.setMaximum(3650)
        heir_locktimedelta_time.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIMEDELTA_TIME)))
        def on_heir_locktime_time():
            value = heir_locktime_time.value
            self.bal_plugin.config.set_key(BalPlugin.LOCKTIME_TIME,value,save=True)
        heir_locktime_time.valueChanged.connect(on_heir_locktime_time)

        heir_locktime_blocks = QSpinBox()
        heir_locktime_blocks.setMinimum(0)
        heir_locktime_blocks.setMaximum(144*3650)
        heir_locktime_blocks.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIME_BLOCKS)))
        def on_heir_locktime_blocks():
            value = heir_locktime_blocks.value()
            self.bal_plugin.config.set_key(BalPlugin.LOCKTIME_BLOCKS,value,save=True)
        heir_locktime_blocks.valueChanged.connect(on_heir_locktime_blocks)

        heir_locktimedelta_blocks = QSpinBox()
        heir_locktimedelta_blocks.setMinimum(0)
        heir_locktimedelta_blocks.setMaximum(144*3650)
        heir_locktimedelta_blocks.setValue(int(self.bal_plugin.config_get(BalPlugin.LOCKTIMEDELTA_BLOCKS)))
        def on_heir_locktimedelta_blocks():
            value = heir_locktimedelta_blocks.value()
            self.bal_plugin.config.set_key(BalPlugin.LOCKTIMEDELTA_TIME,value,save=True)
        heir_locktimedelta_blocks.valueChanged.connect(on_heir_locktimedelta_blocks)

        heir_tx_fees = QSpinBox()
        heir_tx_fees.setMinimum(1)
        heir_tx_fees.setMaximum(10000)
        heir_tx_fees.setValue(int(self.bal_plugin.config_get(BalPlugin.TX_FEES)))
        def on_heir_tx_fees():
            value = heir_tx_fees.value()
            self.bal_plugin.config.set_key(BalPlugin.TX_FEES,value,save=True)
        heir_tx_fees.valueChanged.connect(on_heir_tx_fees)

        heir_broadcast = bal_checkbox(self.bal_plugin, BalPlugin.BROADCAST)
        heir_ask_broadcast = bal_checkbox(self.bal_plugin, BalPlugin.ASK_BROADCAST)
        heir_invalidate = bal_checkbox(self.bal_plugin, BalPlugin.INVALIDATE)
        heir_ask_invalidate = bal_checkbox(self.bal_plugin, BalPlugin.ASK_INVALIDATE)
        heir_preview = bal_checkbox(self.bal_plugin, BalPlugin.PREVIEW)
        

        grid=QGridLayout(d)
        add_widget(grid,"Refresh Time Days",heir_locktime_time,0,"Delta days for inputs to  be invalidated and transactions resubmitted")
        add_widget(grid,"Refresh Blocks",heir_locktime_blocks,1,"Delta blocks for inputs to be invalidated and transaction resubmitted")
        add_widget(grid,"Transaction fees",heir_tx_fees,2,"default transaction fees")
        add_widget(grid,"Broadcast transactions",heir_broadcast,3,"")
        add_widget(grid," - Ask before",heir_ask_broadcast,4,"")
        add_widget(grid,"Invalidate transactions",heir_invalidate,5,"")
        add_widget(grid," - Ask before",heir_ask_invalidate,6,"")
        add_widget(grid,"Show preview before sign",heir_preview,7,"")
        #add_widget(grid,"Max Allowed TimeDelta Days",heir_locktimedelta_time,8,"")
        #add_widget(grid,"Max Allowed BlocksDelta",heir_locktimedelta_blocks,9,"")


        if not d.exec_():
            return
    #TODO IMPLEMENT PREVIEW DIALOG
    #tx list display txid, willexecutor, qrcode, button to sign
    #   :def preview_dialog(self, txs):
    def preview_dialog(self, txs):
        w=PreviewDialog(self,txs)
        w.exec_()
        return w
    def add_info_from_will(self,tx):
        for input in tx.inputs():
            pass


class bal_checkbox(QCheckBox):
    def __init__(self, plugin,variable):
        QCheckBox.__init__(self)
        self.setChecked(plugin.config_get(variable))
        def on_check(v):
            plugin.config.set_key(variable, v == Qt.Checked, save=True)
        self.stateChanged.connect(on_check)


def add_widget(grid,label,widget,row,help_):
    grid.addWidget(QLabel(_(label)),row,0)
    grid.addWidget(widget,row,1)
    grid.addWidget(HelpButton(help_),row,2)

