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
                         QColor, QDesktopServices, qRgba, QPainterPath,QPalette)

from PyQt5.QtWidgets import (QGridLayout, QVBoxLayout, QHBoxLayout, QLabel,QDialog,
                             QPushButton, QLineEdit,QCheckBox,QSpinBox,QMenuBar,QMenu,QLineEdit,QScrollArea,QWidget,QSpacerItem,QSizePolicy)

from electrum.plugin import hook
from electrum.i18n import _
from electrum.util import make_dir, InvalidPassword, UserCancelled
from electrum.util import bfh, decimal_point_to_base_unit_name

from electrum.gui.qt.util import (read_QIcon, EnterButton, WWLabel, icon_path,
                                  
                                  WindowModalDialog, Buttons, CloseButton, OkButton,import_meta_gui,export_meta_gui,char_width_in_lineedit,CancelButton,HelpButton,WaitingDialog)

from electrum.gui.qt.qrtextedit import ScanQRTextEdit
from electrum.gui.qt.main_window import StatusBarButton
from electrum.gui.qt.password_dialog import PasswordDialog
from electrum.gui.qt.transaction_dialog import show_transaction

from .bal import BalPlugin
from .heirs import Heirs
from .util import Util
from .will import Will, WillExpiredException,NotCompleteWillException,WillItem,HeirChangeException,WillexecutorChangeException,WillexecutorNotPresent,TxFeesChangedException,HeirNotFoundException

from .balqt.locktimeedit import HeirsLockTimeEdit
from .balqt.willexecutor_dialog import WillExecutorDialog
from .balqt.preview_dialog import PreviewDialog,PreviewList
from .balqt.heir_list import HeirList
from .balqt.amountedit import PercAmountEdit
from .willexecutors import Willexecutors
from electrum.transaction import tx_from_any
from time import time
from electrum import json_db
from electrum.json_db import StoredDict
import datetime
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
                                            
                                except:
                                    print("except:",menu_child.text())
                                    
        except Exception as e:
            print("Error loading plugin",e)
            Util.print_var(window)
            Util.print_var(window.window())



    @hook
    def create_status_bar(self, sb):
        print("HOOK create status bar")
        return
        b = StatusBarButton(read_QIcon('bal.png'), "Bal "+_("Bitcoin After Life"),
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
        #w.wallet = wallet
        w.ok=True
        w.init_will()

    @hook
    def on_close_window(self,window):
        print("HOOK on close_window")
        pass
        #Util.print_var(window)
        w = self.get_window(window)
        w.build_inheritance_transaction(ignore_duplicate=True,keep_original=True)
        #show_preview=self.config_get(BalPlugin.PREVIEW)
        if Will.is_new(w.will):
            if self.config_get(BalPlugin.PREVIEW):
                w.preview_dialog(w.will)
            elif self.config_get(BalPlugin.BROADCAST):
                if self.config_get(BalPlugin.ASK_BROADCAST):
                    w.preview_dialog(self.will)
            


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
        self.heirs = {}
        self.will = {}
        self.will_settings = None
        self.heirs_tab = self.create_heirs_tab()
        self.will_tab = self.create_will_tab()
        self.ok= False
        if self.window.wallet:
            self.wallet = self.window.wallet
            self.heirs_tab.wallet = self.wallet
            self.will_tab.wallet = self.wallet
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
        print("WALLET",dir(self.wallet.db.data))
        #self.will=json_db._convert_dict(json_db.path,"will",self.will[w])

        for w in self.will:
            if isinstance(self.will[w]['tx'],str):
                #dict.__setitem__(self.will,w,dict(self.will[w]))   
                self.will[w]['tx']=Will.get_tx_from_any(self.will[w])
                self.will[w]['tx'].get_info_from_wallet(self.wallet)

        if self.will:
            Will.normalize_will(self.will,self.wallet)
        
        self.will_list.will=self.will
        self.will_list.update_will(self.will)
        self.will_tab.update()

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
        heir=list(heir)
        heir[3]=self.will_settings['locktime']

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
        if not (will and len(will) > 0 and Will.is_new(will)):
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
            self.will[txid][BalPlugin.STATUS_VALID]=False
            self.will[txid][BalPlugin.STATUS_INVALIDATED]=True
        except Exception as e:
            print(f"cannot invalidate {txid}")
            raise e
    def invalidate_will(self):
        tx = Will.invalidate_will(self.will,self.wallet,self.bal_plugin.config_get(BalPlugin.TX_FEES))
        self.window.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
        if tx:
            self.show_transaction(tx)
        else:
            self.window.show_message(_("no inputs to be invalidate"))
    def build_will(self,from_date, willexecutors, ignore_duplicate = True, keep_original = True ):
        will = {}
        willtodelete=[]
        willtoappend={}
        try:

            #print(willexecutors)
            txs = self.heirs.get_transactions(self.bal_plugin,self.window.wallet,self.will_settings['tx_fees'],None,from_date)
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
                    print("porcodio",txs[txid].tx_fees)
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
                    

                #print("WILL",will)    
                Will.update_will(self.will,will)
                #print("WILL2",will)    
                #print("WILL3",will)    
                for wid in will:
                    print("saving wid",wid,will[wid])
                    wi = WillItem(will[wid])
                    wi.print()
                    #print("tx",str(will[wid]['tx']))
                    self.will[wid]=wi.to_dict()
                #Will.normalize_will(will)

                Will.normalize_will(self.will)
                for wid in will:
                    will[wid]['tx'].set_rbf=True

                #try:
                #    Will.is_will_valid(self.will, block_to_check, date_to_check, self.window.wallet.get_utxos(),self.delete_not_valid)
                #except WillExpiredException as e:
                #    tx = Will.invalidate_will(self.will)
                #    #self.window.show_transaction(self.will[key]['tx'])

                #    self.window.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
                #    self.bal_window.window.show_transaction(tx)
                #except NotCompleteWillException as e:
                #    self.window.show_message(_("Will is not complete some utxo was not included for unknown reasons"))


                



        except Exception as e:
            raise e
            pass
            #print(e)
            #self.window.show_message(e)
            #raise e
        return self.will 

    def build_inheritance_transaction(self,ignore_duplicate = True, keep_original = True):
        try:
            print("start building transactions")
            #locktime_time=self.bal_plugin.config_get(BalPlugin.LOCKTIME_TIME)
            locktime_blocks=self.bal_plugin.config_get(BalPlugin.LOCKTIME_BLOCKS)
            #date_to_check = (datetime.datetime.now()+datetime.timedelta(days=locktime_time)).timestamp()
            date_to_check = Util.parse_locktime_string(self.will_settings['threshold'])
            current_block = Util.get_current_height(self.wallet.network)
            block_to_check = current_block + locktime_blocks
            no_willexecutor = self.bal_plugin.config_get(BalPlugin.NO_WILLEXECUTOR)
            #for txid in self.will_not_replaced_nor_invalidated():
            #    if not self.will[txid]['status']==BalPlugin.STATUS_NEW:
            #        self.will[txid]['status']+=BalPlugin.STATUS_REPLACED
            #    else:
            #        willtodelete.append((None,txid))
            willexecutors = Willexecutors.get_willexecutors(self.bal_plugin,update=True,window=self.window) 
            #current_will_is_valid = Util.is_will_valid(self.will, block_to_check, date_to_check, utxos)
            #print("current_will is valid",current_will_is_valid,self.will)
            try:
                for heir in self.heirs:
                    h=self.heirs[heir]
                    self.heirs[heir]=[h[0],h[1],self.will_settings['locktime']]
                Will.is_will_valid(self.will, block_to_check, date_to_check, self.will_settings['tx_fees'],self.window.wallet.get_utxos(),heirs=self.heirs,willexecutors=Willexecutors.get_willexecutors(self.bal_plugin),self_willexecutor=no_willexecutor,callback_not_valid_tx=self.delete_not_valid)
            except WillExpiredException as e:
                tx = Will.invalidate_will(self.will,self.wallet,self.will_settings['tx_fees'])
                self.window.show_message(_("Current Will have to be invalidated a transaction have to be signed and broadcasted to the bitcoin network"))
                self.show_transaction(tx)

                return

            except NotCompleteWillException as e:
                print(type(e),":",e)
                message = ""
                if isinstance(e,HeirChangeException):
                    message ="heirs changed:"
                elif isinstance(e,WillexecutorNotPresent):
                    message = "Willexecutor not present:"
                elif isinstance(e,WillexecutorChangeException):
                    message = "Willexecutor changed"
                elif isinstance(e,TxFeesChangedException):
                    message = "txfees are changed"
                elif isinstance(e,HeirNotFoundException):
                    message = "heir not found"
                self.window.show_message(f"{_(message)}: {e}")
                self.build_will(date_to_check,willexecutors,ignore_duplicate,keep_original)
                try:
                    Will.is_will_valid(self.will, block_to_check, date_to_check, self.will_settings['tx_fees'], self.window.wallet.get_utxos(),heirs=self.heirs,willexecutors=Willexecutors.get_willexecutors(self.bal_plugin),self_willexecutor=no_willexecutor,callback_not_valid_tx=self.delete_not_valid)
                except WillExpiredException as e:
                    tx = Will.invalidate_will(self.will,self.wallet,self.bal_plugin.config_get(BalPlugin.TX_FEES))
                    Util.print_var(tx,"INVALIDATE_TX")
                    self.window.show_message(_("Was not possible to write the will as it is already expired please publish this transaction") + str(e))
                    self.show_transaction(tx)
                except NotCompleteWillException as e:
                    self.window.show_error( str(e))

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

    def show_transaction(self,tx=None,txid=None,parent = None):
        print("parent:",parent)
        if not parent:
            parent = self.window
        if txid !=None and txid in self.will:
            tx=self.will[txid]['tx']
        if not tx:
            raise Exception(_("no tx"))
        return show_transaction(tx,parent=parent)
            #self.show_transaction(self.will[key]['tx'], parent=self.bal_window.window.top_level_window())


    def invalidate_will(self):
        def on_success(result):
            if result:
                self.window.show_message(_("Please sign and broadcast this transaction to invalidate current will"))
                a=self.show_transaction(result)
            else:
                self.window.show_message(_("No transactions to invalidate"))
        def on_failure(exec_info):
            self.window.show_error(f"ERROR:{exec_info}")
            Util.print_var(exec_info)
        #txs = Will.invalidate_will(self.will)
        fee_per_byte=self.bal_plugin.config_get(BalPlugin.TX_FEES)
        task = partial(Will.invalidate_will,self.will,self.wallet,fee_per_byte)
        msg = _("Calculating Transactions")
        self.waiting_dialog = WaitingDialog(self.window, msg, task, on_success, on_failure)

    def get_will_widget(self,father=None,parent = None):
        box = QWidget()
        vlayout = QVBoxLayout()
        box.setLayout(vlayout)
        decimal_point = self.bal_plugin.config.get_decimal_point()
        base_unit_name = decimal_point_to_base_unit_name(decimal_point)
        for w in self.will:
            if self.will[w][BalPlugin.STATUS_REPLACED] and self.bal_plugin._hide_replaced:
                continue
            if self.will[w][BalPlugin.STATUS_INVALIDATED] and self.bal_plugin._hide_invalidated:
                continue
            f = self.will[w].get("father",None)
            if father == f:
                qwidget = QWidget()
                childWidget = QWidget()
                hlayout=QHBoxLayout(qwidget)
                qwidget.setLayout(hlayout)
                vlayout.addWidget(qwidget)
                detailw=QWidget()
                detaillayout=QVBoxLayout()
                detailw.setLayout(detaillayout)
                
                willpushbutton = QPushButton(w)
            
                willpushbutton.clicked.connect(partial(self.show_transaction,txid=w, parent = parent))
                detaillayout.addWidget(willpushbutton)
                locktime = Util.locktime_to_str(self.will[w]['tx'].locktime)
                detaillayout.addWidget(QLabel(_(f"<b>Locktime:</b>\t{locktime}")))
                detaillayout.addWidget(QLabel(_("<b>Heirs:</b>")))
                for heir in self.will[w]['heirs']:
                    if "w!ll3x3c\"" not in heir:
                        decoded_amount = Util.decode_amount(self.will[w]['heirs'][heir][3],decimal_point)
                        detaillayout.addWidget(QLabel(f"{heir}:\t{decoded_amount} {base_unit_name}"))
                if self.will[w]['willexecutor']:
                    detaillayout.addWidget(QLabel(_("<b>Willexecutor:</b:")))
                    decoded_amount = Util.decode_amount(self.will[w]['willexecutor']['base_fee'],decimal_point)
                    
                    detaillayout.addWidget(QLabel(f"{self.will[w]['willexecutor']['url']}:\t{decoded_amount} {base_unit_name}"))
                detaillayout.addStretch()
                pal = QPalette()
                if self.will[w].get(BalPlugin.STATUS_INVALIDATED,False):
                    pal.setColor(QPalette.Background, QColor(255,0, 0))
                elif self.will[w].get(BalPlugin.STATUS_REPLACED,False):
                    pal.setColor(QPalette.Background, QColor(255, 255, 0))
                else:
                    pal.setColor(QPalette.Background, QColor("#57c7d4"))
                detailw.setAutoFillBackground(True)
                detailw.setPalette(pal)

                hlayout.addWidget(detailw)
                hlayout.addWidget(self.get_will_widget(w,parent = parent))
        return box

    def preview_modal_dialog(self):
        Will.add_willtree(self.will)
        print(self.will)
        d = QDialog(parent = None)
        d.config = self.window.config
        d.wallet = self.wallet
        d.format_amount = self.window.format_amount
        d.base_unit = self.window.base_unit
        d.format_fiat_and_units = self.window.format_fiat_and_units
        d.fx = self.window.fx
        d.format_fee_rate = self.window.format_fee_rate
        d.setMinimumSize(670,700)
        vlayout= QVBoxLayout()
        scroll = QScrollArea()
        viewport = QWidget(scroll)
        willlayout = QVBoxLayout(viewport)
        willlayout.addWidget(self.get_will_widget(parent = d))




        scroll.setWidget(viewport)
        viewport.setLayout(willlayout)
        i=0
        vlayout.addWidget(QLabel(_("DON'T PANIC !!! everything is fine, all possible futures are covered")))
        vlayout.addWidget(scroll)
        w=QWidget()
        hlayout = QHBoxLayout(w)
        print(Will.only_valid_list(self.will))
        hlayout.addWidget(QLabel(_("Valid Txs:")+ str(len(Will.only_valid_list(self.will)))))
        hlayout.addWidget(QLabel(_("Total Txs:")+ str(len(self.will))))
        vlayout.addWidget(w)
        d.setLayout(vlayout)
        if not d.show():
            return


            
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
        heir_ping_willexecutors = bal_checkbox(self.bal_plugin, BalPlugin.PING_WILLEXECUTORS)
        heir_ask_ping_willexecutors = bal_checkbox(self.bal_plugin, BalPlugin.ASK_PING_WILLEXECUTORS)
        heir_no_willexecutor = bal_checkbox(self.bal_plugin, BalPlugin.NO_WILLEXECUTOR)

        

        grid=QGridLayout(d)
        #add_widget(grid,"Refresh Time Days",heir_locktime_time,0,"Delta days for inputs to  be invalidated and transactions resubmitted")
        #add_widget(grid,"Refresh Blocks",heir_locktime_blocks,1,"Delta blocks for inputs to be invalidated and transaction resubmitted")
        #add_widget(grid,"Transaction fees",heir_tx_fees,1,"Default transaction fees")
        #add_widget(grid,"Broadcast transactions",heir_broadcast,3,"")
        #add_widget(grid," - Ask before",heir_ask_broadcast,4,"")
        #add_widget(grid,"Invalidate transactions",heir_invalidate,5,"")
        #add_widget(grid," - Ask before",heir_ask_invalidate,6,"")
        #add_widget(grid,"Show preview before sign",heir_preview,7,"")
        add_widget(grid,"Ping Willexecutors",heir_ping_willexecutors,0,"Ping willexecutors to get payment info before compiling will")
        add_widget(grid," - Ask before",heir_ask_ping_willexecutors,1,"Ask before to ping willexecutor")
        add_widget(grid,"Backup Transaction",heir_no_willexecutor,2,"Add transactions without willexecutor")
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

