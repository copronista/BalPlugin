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

from PyQt5.QtCore import Qt, QRectF, QRect, QSizeF, QUrl, QPoint, QSize
from PyQt5.QtGui import (QPixmap, QImage, QBitmap, QPainter, QFontDatabase, QPen, QFont,QIcon,
                         QColor, QDesktopServices, qRgba, QPainterPath,QPalette)

from PyQt5.QtWidgets import (QGridLayout, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit,QCheckBox,QSpinBox,QMenuBar,QMenu,QLineEdit,QScrollArea,QWidget,QSpacerItem,QSizePolicy)

from electrum.plugin import hook
from electrum.i18n import _
from electrum.util import make_dir, InvalidPassword, UserCancelled,resource_path
from electrum.util import bfh, read_json_file,write_json_file,decimal_point_to_base_unit_name,FileImportFailed,FileExportFailed

from electrum.gui.qt.util import (EnterButton, WWLabel, 
                                    Buttons, CloseButton, OkButton,import_meta_gui,export_meta_gui,char_width_in_lineedit,CancelButton,HelpButton)

from electrum.gui.qt.qrtextedit import ScanQRTextEdit
from electrum.gui.qt.main_window import StatusBarButton
from electrum.gui.qt.password_dialog import PasswordDialog
from electrum.gui.qt.transaction_dialog import TxDialog
from electrum import constants
from electrum.transaction import Transaction
from .bal import BalPlugin
from .heirs import Heirs
from . import util as Util
from . import will as Will

from .balqt.locktimeedit import HeirsLockTimeEdit
from .balqt.willexecutor_dialog import WillExecutorDialog
from .balqt.preview_dialog import PreviewDialog,PreviewList
from .balqt.heir_list import HeirList
from .balqt.amountedit import PercAmountEdit
from .balqt.willdetail import WillDetailDialog
from .balqt import qt_resources
from . import willexecutors as Willexecutors
from electrum.transaction import tx_from_any
from time import time
from electrum import json_db
from electrum.json_db import StoredDict
import datetime
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Callable, Optional, List, Union, Tuple, Mapping
from .balqt.baldialog import BalDialog,BalWaitingDialog,BalBlockingWaitingDialog


class Plugin(BalPlugin):

    def __init__(self, parent, config, name):
        print("INIT BALPLUGIN")
        BalPlugin.__init__(self, parent, config, name)
        self.bal_windows={}


    @hook
    def init_qt(self,gui_object):
        print("HOOK init qt")   
        try:
            self.gui_object=gui_object
            #json_db.register_dict('heirs', tuple, None)
            #json_db.register_dict('will', lambda x: get_will(x), None)

            for window in gui_object.windows:
                wallet = window.wallet
                if wallet:
                    window.show_warning(_('Please restart Electrum to activate the BAL plugin'), title=_('Success'))
                    return
                w = BalWindow(self,window)
                self.bal_windows[window.winId]= w
                for child in window.children():
                    if isinstance(child,QMenuBar):
                        for menu_child in child.children():
                            if isinstance(menu_child,QMenu):
                                try:
                                    print(menu_child.title())
                                    if menu_child.title()==_("&Tools"):
                                        #pass
                                        w.init_menubar_tools(menu_child)
                                            
                                except Exception as e:
                                    raise e
                                    print("except:",menu_child.text())
                                    
        except Exception as e:
            raise e
            print("Error loading plugin",e)
            Util.print_var(window)
            Util.print_var(window.window())



    @hook
    def create_status_bar(self, sb):
        print("HOOK create status bar")
        return
        b = StatusBarButton(qt_resources.read_QIcon('bal32x32.png'), "Bal "+_("Bitcoin After Life"),
                            partial(self.setup_dialog, sb), sb.height())
        sb.addPermanentWidget(b)

    @hook
    def init_menubar_tools(self,window,tools_menu):
        print("HOOK init_menubar")
        w = self.get_window(window)
        w.init_menubar_tools(tools_menu)

    @hook
    def load_wallet(self,wallet, main_window):
        print("HOOK load wallet")
        w = self.get_window(main_window)
        w.wallet = wallet
        w.init_will()
        w.disable_plugin = False
        w.ok=True

    @hook
    def on_close_window(self,window):
        print("HOOK on close_window")
        #Util.print_var(window)
        w = self.get_window(window)
        if w.disable_plugin:
            return
        w.build_inheritance_transaction(ignore_duplicate=True,keep_original=True)
        #show_preview=self.config_get(BalPlugin.PREVIEW)
        if Will.is_new(w.will):
            if self.config_get(BalPlugin.PREVIEW):
                w.preview_modal_dialog()
                w.dw.exec_()
            elif self.config_get(BalPlugin.BROADCAST):
                if self.config_get(BalPlugin.ASK_BROADCAST):
                    w.preview_modal_dialog()
                    w.dw.exec_()
            

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
                try:
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

                    
                    window.tabs.update()
                    bal_window.will_tab.hide()
                    #window.tabs.removeTab(bal_window.will_tab.tab_pos-1)
                    print(7)
                    #Util.print_var(bal_window.tools_menu.willexecutors_action)
                    bal_window.tools_menu.removeAction(bal_window.tools_menu.willexecutors_action)
                except:
                    pass
        except Exception as e:
            raise e
            print("error closing plugin",e)
class shown_cv():
    _type= bool
    def __init__(self,value):
        self.value=value
    def get(self):
        return self.value
    def set(self,value):
        self.value=value
class BalWindow():
    def __init__(self,bal_plugin: 'BalPlugin',window: 'ElectrumWindow'):
        self.bal_plugin = bal_plugin
        self.window = window
        self.heirs = {}
        self.will = {}
        self.will_settings = None
        self.heirs_tab = self.create_heirs_tab()
        self.will_tab = self.create_will_tab()
        self.ok= False
        self.disable_plugin = True
        if self.window.wallet:
            self.wallet = self.window.wallet
            self.heirs_tab.wallet = self.wallet
            self.will_tab.wallet = self.wallet
            #self.init_will()
        #print(self.window.windowTitle())


    def init_menubar_tools(self,tools_menu):
        self.tools_menu=tools_menu


        def add_optional_tab(tabs, tab, icon, description):
            tab.tab_icon = icon
            tab.tab_description = description
            tab.tab_pos = len(tabs)
            if tab.is_shown_cv:
                tabs.addTab(tab, icon, description.replace("&", ""))
        
        add_optional_tab(self.window.tabs, self.heirs_tab, qt_resources.read_QIcon("heir.png"), _("&Heirs"))
        add_optional_tab(self.window.tabs, self.will_tab, qt_resources.read_QIcon("will.png"), _("&Will"))
        tools_menu.addSeparator()
        self.tools_menu.willexecutors_action = tools_menu.addAction(_("&Will-Executors"), self.willexecutor_dialog)
    def erease_will(self):
        to_delete = []
        for w in self.will:
            to_delete.append(w)
        for w in to_delete:
            del self.will[w]

    def init_will(self):
        print("********************init_____will____________**********")
        if not self.heirs:
            self.heirs = Heirs._validate(Heirs(self.wallet.db))
        if not self.will:
            self.will=self.wallet.db.get_dict("will")
        if not self.will_settings:
            self.will_settings=self.wallet.db.get_dict("will_settings")
            print("will_settings:",self.will_settings)
            if not self.will_settings:
                self.will_settings['tx_fees']=100
                self.will_settings['threshold']='180d'
                self.will_settings['locktime']='1y'
            self.heir_list.update_will_settings()
        #self.will=json_db._convert_dict(json_db.path,"will",self.will[w])
        self.willitems={}
        for w in self.will:
            if isinstance(self.will[w]['tx'],str):
                #dict.__setitem__(self.will,w,dict(self.will[w]))   
                try:
                    self.will[w]['tx']=Will.get_tx_from_any(self.will[w])
                    self.will[w]['tx'].get_info_from_wallet(self.wallet)
                except:
                    self.disable_plugin=True
                    self.show_warning(_('Please restart Electrum to activate the BAL plugin'), title=_('Success'))
                    self.bal_plugin.on_close()
                    return
                
        if self.will:
            Will.normalize_will(self.will,self.wallet)
        
        self.will_list.will=self.will
        self.will_list.update_will(self.will)
        self.will_tab.update()

    def get_window_title(self,title):
        return _('BAL - ') + _(title) 

    def willexecutor_dialog(self):
        h = WillExecutorDialog(self)
        h.show()

    def create_heirs_tab(self):
        self.heir_list = l = HeirList(self)
        tab = self.window.create_list_tab(l)
        tab.is_shown_cv = shown_cv(True)
        return tab

    def create_will_tab(self):
        self.will_list = l = PreviewList(self,None)
        tab = self.window.create_list_tab(l)
        tab.is_shown_cv = shown_cv(True)
        #self.will_tab.update_will(self.will)
        return tab

    def new_heir_dialog(self):
        d = BalDialog(self.window, self.get_window_title("New heir"))
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

        #grid.addWidget(QLabel(_("LockTime")), 4, 0)
        #grid.addWidget(heir_locktime, 4, 1)
        #grid.addWidget(HelpButton("if you choose Raw, you can insert various options based on suffix:\n " 
        #                          +" - b: number of blocks after current block(ex: 144b means tomorrow)\n" 
        #                          +" - d: number of days after current day(ex: 1d means tomorrow)\n"  
        #                           +" - y: number of years after currrent day(ex: 1y means one year from today)\n\n" 
        #                          +"when using d or y time will be set to 00:00 for privacy reasons\n" 
        #                          +"when used without suffix it can be used to indicate:\n" 
        #                          +" - exact block(if value is less than 500,000,000)\n"
        #                          +" - exact block timestamp(if value greater than 500,000,000"),4,2)

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
                self.show_error(str(e))

    def export_inheritance_handler(self,path):
        txs = self.build_inheritance_transaction(ignore_duplicate=True, keep_original=False)
        with open(path,"w") as f:
            for tx in txs:
                #Util.print_var(tx)
                tx['status']+=BalPlugin.STATUS_EXPORTED
                f.write(str(tx['tx']))
                f.write('\n')
 
    def set_heir(self,heir):
        heir=list(heir)
        heir[3]=self.will_settings['locktime']

        h=Heirs.validate_heir(heir[0],heir[1:])
        self.heirs[heir[0]]=h
        self.heir_list.update()
        return True

    def delete_heirs(self,heirs):
        for heir in heirs:
            del self.heirs[heir]
        self.heirs.save()
        self.heir_list.update()
        return True
    
    def import_heirs(self,):
        import_meta_gui(self.window, _('heirs'), self.heirs.import_file, self.heir_list.update)

    def export_heirs(self):
        Util.export_meta_gui(self.window, _('heirs'), self.heirs.export_file)

    def prepare_will(self, ignore_duplicate = False, keep_original = False):
        will = self.build_inheritance_transaction(ignore_duplicate = ignore_duplicate, keep_original=keep_original)
        if not (will and len(will) > 0 and Will.is_new(will)):
            self.show_message(_('no tx to be created'))
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
            self.will[txid][BalPlugin.STATUS_VALID]=False
            self.will[txid][BalPlugin.STATUS_INVALIDATED]=True
        except Exception as e:
            print(f"cannot invalidate {txid}")
            raise e
    #def invalidate_will(self):
    #    tx = Will.invalidate_will(self.will,self.wallet,self.will_settings['tx_fees']))
    #    self.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
    #    if tx:
    #        self.show_transaction(tx)
    #    else:
    #        self.show_message(_("no inputs to be invalidate"))
    def update_will(self,will):
        print("SELF.UPDATE WILL")
        Will.update_will(self.will,will)
        #print("WILL2",will)    
        #print("WILL3",will)    
        for wid in will:
            print("saving wid",wid,will[wid])
            wi = Will.WillItem(will[wid])
            wi.print()
            #print("tx",str(will[wid]['tx']))
            self.will[wid]=wi.to_dict()
        #Will.normalize_will(will)

        Will.normalize_will(self.will,self.wallet)

    def build_will(self, ignore_duplicate = True, keep_original = True ):
        will = {}
        willtodelete=[]
        willtoappend={}
        try:
            self.willexecutors = Willexecutors.get_willexecutors(self.bal_plugin, update=True, bal_window=self) 

            #print(willexecutors)
            txs = self.heirs.get_transactions(self.bal_plugin,self.window.wallet,self.will_settings['tx_fees'],None,self.date_to_check)
            print(txs)
            creation_time = time()
            if txs:
                for txid in txs:
                    txtodelete=[]
                    _break = False
                    #print(txid,txs[txid].description)
                    tx = {}
                    tx['tx'] = txs[txid]
                    tx['my_locktime'] = txs[txid].my_locktime
                    tx['heirsvalue'] = txs[txid].heirsvalue
                    tx['description'] = txs[txid].description
                    tx['willexecutor'] = txs[txid].willexecutor
                    tx['status'] = BalPlugin.STATUS_NEW
                    tx['tx_fees'] = txs[txid].tx_fees
                    tx[BalPlugin.STATUS_NEW] = True
                    tx[BalPlugin.STATUS_VALID] = True
                    tx[BalPlugin.STATUS_REPLACED] = False
                    tx[BalPlugin.STATUS_INVALIDATED] = False
                    tx[BalPlugin.STATUS_EXPORTED] = False
                    tx[BalPlugin.STATUS_BROADCASTED] = False
                    tx[BalPlugin.STATUS_RESTORED] = False
                    tx[BalPlugin.STATUS_COMPLETE] = False
                    tx[BalPlugin.STATUS_PUSHED] = False
                    tx[BalPlugin.STATUS_ANTICIPATED] = False

                    tx['time'] = creation_time
                    tx['heirs'] = txs[txid].heirs
                    tx['txchildren'] = []
                    will[txid]=tx
                    

                self.update_will(will)
                #try:
                #    Will.is_will_valid(self.will, block_to_check, date_to_check, self.window.wallet.get_utxos(),self.delete_not_valid)
                #except WillExpiredException as e:
                #    tx = Will.invalidate_will(self.will)
                #    #self.window.show_transaction(self.will[key]['tx'])

                #    self.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
                #    self.bal_window.window.show_transaction(tx)
                #except NotCompleteWillException as e:
                #    self.show_message(_("Will is not complete some utxo was not included for unknown reasons"))


                



        except Exception as e:
            raise e
            pass
            #print(e)
            #self.show_message(e)
            #raise e
        return self.will 

    def check_will(self):
        return Will.is_will_valid(self.will, self.block_to_check, self.date_to_check, self.will_settings['tx_fees'],self.window.wallet.get_utxos(),heirs=self.heirs,willexecutors=self.willexecutors ,self_willexecutor=self.no_willexecutor,callback_not_valid_tx=self.delete_not_valid)
    def show_message(self,text):
        self.window.show_message(text)
    def show_warning(self,text):
        self.window.show_warning(text)
    def show_error(self,text):
        self.window.show_error(text)
    def show_critical(self,text):
        self.window.show_critical(text)

    def build_inheritance_transaction(self,ignore_duplicate = True, keep_original = True):
        try:
            if self.disable_plugin:
                print("plugin is disabled")
                return
            if not self.heirs:
                print("not heirs",self.heirs)
                return
            try: 
                print("start building transactions")
                self.date_to_check = Util.parse_locktime_string(self.will_settings['threshold'])
                print("date_to_check:",self.date_to_check)
                self.locktime_blocks=self.bal_plugin.config_get(BalPlugin.LOCKTIME_BLOCKS)
                self.current_block = Util.get_current_height(self.wallet.network)
                self.block_to_check = self.current_block + self.locktime_blocks
                #locktime_time=self.bal_plugin.config_get(BalPlugin.LOCKTIME_TIME)
                #date_to_check = (datetime.datetime.now()+datetime.timedelta(days=locktime_time)).timestamp()
                self.no_willexecutor = self.bal_plugin.config_get(BalPlugin.NO_WILLEXECUTOR)
                #for txid in self.will_not_replaced_nor_invalidated():
                #    if not self.will[txid]['status']==BalPlugin.STATUS_NEW:
                #        self.will[txid]['status']+=BalPlugin.STATUS_REPLACED
                #    else:
                #        willtodelete.append((None,txid))
                self.willexecutors = Willexecutors.get_willexecutors(self.bal_plugin,update=False,bal_window=self) 
            except Exception as e:
                raise e
                return
            #current_will_is_valid = Util.is_will_valid(self.will, block_to_check, date_to_check, utxos)
            #print("current_will is valid",current_will_is_valid,self.will)
            try:
                print(self.heirs)
                for heir in self.heirs:
                    h=self.heirs[heir]
                    self.heirs[heir]=[h[0],h[1],self.will_settings['locktime']]
                    print("will_Settings locktime",self.will_settings['locktime'])
                    print(self.heirs[heir])
                self.check_will()
            except Will.WillExpiredException as e:
                self.invalidate_will()
                return
            except Will.NoHeirsException:
                return

            except Will.NotCompleteWillException as e:
                print(type(e),":",e)
                message = "not complete"
                if isinstance(e,Will.HeirChangeException):
                    message ="heirs changed:"
                elif isinstance(e,Will.WillExecutorNotPresent):
                    message = "Will-Executor not present:"
                elif isinstance(e,Will.WillexecutorChangeException):
                    message = "Will-Executor changed"
                elif isinstance(e,Will.TxFeesChangedException):
                    message = "txfees are changed"
                elif isinstance(e,Will.HeirNotFoundException):
                    message = "heir not found"
                self.show_message(f"{_(message)}: {e} {_('will have to be rebuilt')}")
                print("build will")
                self.build_will(ignore_duplicate,keep_original)

                try:
                    self.check_will()
                    for wid,w in self.will.items():
                        self.wallet.set_label(wid,"BAL Transaction")
                except Will.WillExpiredException as e:
                    self.invalidate_will()
                except Will.NotCompleteWillException as e:
                    self.show_error("Error:{}\n {}".format(str(e),_("Please, check your heirs, locktime and threshold!")))

                self.window.history_list.update()
                self.window.utxo_list.update()
                try:
                    self.will_list.update_will(self.will)
                except Exception as e:
                    raise e
                    pass
                    #raise e
                return self.will
        except Exception as e:
            #print("ERROR: exception building transactions",e)
            raise e
            pass
    def show_transaction_real(
        self,
        tx: Transaction,
        *,
        parent: 'ElectrumWindow',
        prompt_if_unsaved: bool = False,
        external_keypairs: Mapping[bytes, bytes] = None,
        payment_identifier: 'PaymentIdentifier' = None,
    ):
        try:
            d = TxDialog(
                tx,
                parent=parent,
                prompt_if_unsaved=prompt_if_unsaved,
                external_keypairs=external_keypairs,
                payment_identifier=payment_identifier,
            )
            d.setWindowIcon(qt_resources.read_QIcon("bal32x32.png"))
        except SerializationError as e:
            _logger.exception('unable to deserialize the transaction')
            parent.show_critical(_("Electrum was unable to deserialize the transaction:") + "\n" + str(e))
        else:
            d.show()
            return d

    def show_transaction(self,tx=None,txid=None,parent = None):
        print("parent:",parent)
        if not parent:
            parent = self.window
        if txid !=None and txid in self.will:
            tx=self.will[txid]['tx']
        if not tx:
            raise Exception(_("no tx"))
        return self.show_transaction_real(tx,parent=parent)
            #self.show_transaction(self.will[key]['tx'], parent=.self.bal_window.window.top_level_window())


    def invalidate_will(self):
        def on_success(result):
            if result:
                self.show_message(_("Please sign and broadcast this transaction to invalidate current will"))
                self.wallet.set_label(result.txid(),"BAL Invalidate")
                a=self.show_transaction(result)
            else:
                self.show_message(_("No transactions to invalidate"))
        def on_failure(exec_info):
            self.show_error(f"ERROR:{exec_info}")
            Util.print_var(exec_info)
        #txs = Will.invalidate_will(self.will)
        fee_per_byte=self.will_settings.get('tx_fees',1)
        task = partial(Will.invalidate_will,self.will,self.wallet,fee_per_byte)
        msg = _("Calculating Transactions")
        self.waiting_dialog = BalWaitingDialog(self.window, msg, task, on_success, on_failure)

    def ask_password_and_sign_transactions(self,callback=None):
        def on_success(txs):
            for txid,tx in txs.items():
                self.will[txid]['tx']=copy.deepcopy(tx)
            #self.bal_window.will[txid]['tx']=tx_from_any(str(tx))
            try:
                self.will_list.update()
            except:
                print("failed to update willlist")
                pass
            if callback:
                try:
                    print("CALLLBACK")
                    callback()
                except Exception as e:
                    print("failed to CALLBACK")
                    raise e
                    pass

        def on_failure(exc_info):
            print("sign fail",exc_info)
        
        
        password = None
        if self.wallet.has_keystore_encryption():
            password = self.bal_plugin.password_dialog(parent=self.window)
        #self.sign_transactions(password)
        
        task = partial(self.sign_transactions, password)
        msg = _('Signing transactions...')
        self.waiting_dialog = BalWaitingDialog(self.window, msg, task, on_success, on_failure)

    def broadcast_transactions(self,force=False):
        def on_success(sulcess):
            print("OK, sulcess transaction was sent")
            self.show_message(_("All transactions are broadcasted to respective Will-Executors"))
            self.will_list.update()
            pass
        def on_failure(err):
            print(err)

        task = partial(self.push_transactions_to_willexecutors,force)
        msg = _('Selecting Will-Executors')
        self.broadcasting_dialog = BalWaitingDialog(self.window,msg,task,on_success,on_failure)
        #self.will_list.update()

    def push_transactions_to_willexecutors(self,force=False):
        willexecutors ={}
        for wid in self.will:
            willitem = self.will[wid]
            if willitem[BalPlugin.STATUS_VALID]:
                if willitem[BalPlugin.STATUS_COMPLETE]:
                    if not willitem[BalPlugin.STATUS_PUSHED] or force:
                        if 'willexecutor' in willitem:
                            willexecutor=willitem['willexecutor']
                            if  willexecutor and Willexecutors.is_selected(willexecutor):
                                url=willexecutor['url']
                                if not url in willexecutors:
                                    willexecutor['txs']=""
                                    willexecutor['txsids']=[]
                                    willexecutor['broadcast_status']= _("Waiting...")
                                    willexecutors[url]=willexecutor
                                willexecutors[url]['txs']+=str(willitem['tx'])+"\n"
                                willexecutors[url]['txsids'].append(wid)
        #print(willexecutors)
        if not willexecutors:
            return
        def getMsg(willexecutors):
            msg = "Pushing Transactions to Will-Executors:\n"
            for url in willexecutors:
                msg += f"{url}:\t{willexecutors[url]['broadcast_status']}\n"
            return msg
        for url in willexecutors:
            willexecutor = willexecutors[url]
            if Willexecutors.is_selected(willexecutor):
                print("msg:",getMsg(willexecutors))
                self.broadcasting_dialog.update(getMsg(willexecutors))
                if 'txs' in willexecutor:
                    if self.push_transactions_to_willexecutor(willexecutors[url]['txs'],url):
                        for wid in willexecutors[url]['txsids']:
                            self.will[wid][BalPlugin.STATUS_PUSHED]=True
                            self.will[wid]['status']+="."+ BalPlugin.STATUS_PUSHED
                        willexecutors[url]['broadcast_stauts'] = _("Success")
                    else:
                        willexecutors[url]['broadcast_stauts'] = _("Failed")
                    del willexecutor['txs']

    def push_transactions_to_willexecutor(self,strtxs,url):
        print(url,strtxs)
        try:
            req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/pushtxs", data=strtxs.encode('ascii'), method='POST')
            req.add_header('Content-Type', 'text/plain')
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')
                if response.status != 200:
                    print(f"error{response.status} pushing txs to: {url}")
                else:
                    return True
                
        except Exception as e:
            print(f"error contacting {url} for pushing txs",e)


    def export_json_file(self,path):
        write_json_file(path, self.will)

    def export_will(self):
        try:
            Util.export_meta_gui(self.window, _('will.json'), self.export_json_file)
        except Exception as e:
            self.show_error(str(e))
            raise e
        
    def import_will(self):
        def sulcess():
            self.will_list.update_will(self.will)
        import_meta_gui(self.window, _('will'), self.import_json_file,sulcess)

    def import_json_file(self,path):
        try:
            data = read_json_file(path)
            for k,v in data.items():
                data[k]['tx']=tx_from_any(v['tx'])
            self.update_will(data)
        except Exception as e:
            raise e
            raise FileImportFailed(_("Invalid will file"))


    def sign_transactions(self,password):
        txs={}
        signed = None
        tosign = None
        def get_message():
            msg = ""
            if signed:
                msg=_(f"signed: {signed}\n")
            return msg + _(f"signing: {tosign}")
        for txid in Will.only_valid(self.will):
            willitem = self.will[txid]
            tx = copy.deepcopy(willitem['tx'])
            if willitem[BalPlugin.STATUS_COMPLETE]:
                print("altready signed",txid)
                txs[txid]=tx
                continue
            tosign=txid
            self.waiting_dialog.update(get_message())
            for txin in tx.inputs():
                prevout = txin.prevout.to_json()
                if prevout[0] in self.will:
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


            self.wallet.sign_transaction(tx, password,ignore_warnings=True)
            signed=tosign
            is_complete=False
            if tx.is_complete():
                is_complete=True
                willitem['status'] += "." + BalPlugin.STATUS_COMPLETE
                willitem[BalPlugin.STATUS_COMPLETE]=True
            print("tx: {} is complete:{}".format(txid, tx.is_complete()))
            txs[txid]=tx
        return txs




    def ping_willexecutors_task(self,wes):
        print("ping willexecutots task")
        pinged = []
        failed = []
        def get_title():
            msg = _('Ping Will-Executors')
            msg += "\n"
            for url in wes:
                msg += f"{url}: "
                if url in pinged:
                    msg += "Ok"
                elif url in failed:
                    msg +="Ko"
                else:
                    msg += "-"
                msg+="\n"
            return msg 
        for url,we in wes.items():
            print(f"ping {url}")
            self.pingwaiting_dialog.update(get_title())
            wes[url]=Willexecutors.get_info_task(url,we)
            if wes[url]['status']=='KO':
                failed.append(url)
            else:
                pinged.append(url)
            
    def ping_willexecutors(self,wes):
        def on_success(result):
            pass
        def on_failure(e):
            print(e)
            pass
        print("ping willexecutors")
        task = partial(self.ping_willexecutors_task,wes)
        msg = _('Ping Will-Executors')
        self.pingwaiting_dialog = BalWaitingDialog(self.window,msg,task,on_success,on_failure)

    def preview_modal_dialog(self):
        self.dw=WillDetailDialog(self)
        self.dw.show()
            
    def settings_dialog(self):
        d = BalDialog(self.window, self.get_window_title("Settings"))
        d.setMinimumSize(100, 200)
        
        qicon=qt_resources.read_QPixmap("bal32x32.png")
        lbl_logo = QLabel()
        lbl_logo.setPixmap(qicon)
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
        heir_ping_willexecutors = bal_checkbox(self.bal_plugin, BalPlugin.PING_WILLEXECUTORS)
        heir_ask_ping_willexecutors = bal_checkbox(self.bal_plugin, BalPlugin.ASK_PING_WILLEXECUTORS)
        heir_no_willexecutor = bal_checkbox(self.bal_plugin, BalPlugin.NO_WILLEXECUTOR)

        
        heir_hide_replaced = bal_checkbox(self.bal_plugin,BalPlugin.HIDE_REPLACED,self)
        heir_hide_invalidated = bal_checkbox(self.bal_plugin,BalPlugin.HIDE_INVALIDATED,self)
        heir_allow_repush = bal_checkbox(self.bal_plugin,BalPlugin.ALLOW_REPUSH,self)
        heir_repush = QPushButton("Rebroadcast transactions")
        heir_repush.clicked.connect(partial(self.broadcast_transactions,True))
        grid=QGridLayout(d)
        #add_widget(grid,"Refresh Time Days",heir_locktime_time,0,"Delta days for inputs to  be invalidated and transactions resubmitted")
        #add_widget(grid,"Refresh Blocks",heir_locktime_blocks,1,"Delta blocks for inputs to be invalidated and transaction resubmitted")
        #add_widget(grid,"Transaction fees",heir_tx_fees,1,"Default transaction fees")
        #add_widget(grid,"Broadcast transactions",heir_broadcast,3,"")
        #add_widget(grid," - Ask before",heir_ask_broadcast,4,"")
        #add_widget(grid,"Invalidate transactions",heir_invalidate,5,"")
        #add_widget(grid," - Ask before",heir_ask_invalidate,6,"")
        #add_widget(grid,"Show preview before sign",heir_preview,7,"")

        #grid.addWidget(lbl_logo,0,0) 
        add_widget(grid,"Hide Replaced",heir_hide_replaced, 1, "Hide replaced transactions from will detail and list")
        add_widget(grid,"Hide Invalidated",heir_hide_invalidated ,2,"Hide invalidated transactions from will detail and list")
        add_widget(grid,"Ping Willexecutors",heir_ping_willexecutors,3,"Ping willexecutors to get payment info before compiling will")
        add_widget(grid," - Ask before",heir_ask_ping_willexecutors,4,"Ask before to ping willexecutor")
        add_widget(grid,"Backup Transaction",heir_no_willexecutor,5,"Add transactions without willexecutor")
        grid.addWidget(heir_repush,6,0)
        grid.addWidget(HelpButton("Broadcast all transactions to willexecutors including those already pushed"),6,2)
        #add_widget(grid,"Max Allowed TimeDelta Days",heir_locktimedelta_time,8,"")
        #add_widget(grid,"Max Allowed BlocksDelta",heir_locktimedelta_blocks,9,"")


        if not d.exec_():
            try:
                self.update_all()
            except:
                pass
            return
    def update_all(self):
        self.will_list.update_will(self.will)
        self.heirs_tab.update()
        self.will_tab.update()
        self.will_list.update()

    #TODO IMPLEMENT PREVIEW DIALOG
    #tx list display txid, willexecutor, qrcode, button to sign
    #   :def preview_dialog(self, txs):
    def preview_dialog(self, txs):
        w=PreviewDialog(self,txs)
        w.show()
        return w
    def add_info_from_will(self,tx):
        for input in tx.inputs():
            pass


class bal_checkbox(QCheckBox):
    def __init__(self, plugin,variable,window=None):
        QCheckBox.__init__(self)
        self.setChecked(plugin.config_get(variable))
        window=window
        def on_check(v):
            plugin.config.set_key(variable, v == Qt.Checked, save=True)
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
        w.exec_()
        return w
    def add_info_from_will(self,tx):
        for input in tx.inputs():
            pass


class bal_checkbox(QCheckBox):
    def __init__(self, plugin,variable,window=None):
        QCheckBox.__init__(self)
        self.setChecked(plugin.config_get(variable))
        window=window
        def on_check(v):
            #print("checked")
            plugin.config.set_key(variable, v == Qt.Checked, save=True)
            if window:
                plugin._hide_invalidated= plugin.config_get(plugin.HIDE_INVALIDATED)
                plugin._hide_replaced= plugin.config_get(plugin.HIDE_REPLACED)

                window.update_all()
        self.stateChanged.connect(on_check)


def add_widget(grid,label,widget,row,help_):
    grid.addWidget(QLabel(_(label)),row,0)
    grid.addWidget(widget,row,1)
    grid.addWidget(HelpButton(help_),row,2)

