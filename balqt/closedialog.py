from .baldialog import BalDialog
from . import qt_resources

if qt_resources.QT_VERSION == 5:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QCheckBox
    from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot, QObject,QEventLoop
else:
    from PyQt6.QtCore import pyqtProperty, pyqtSignal, pyqtSlot, QObject,QEventLoop
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QCheckBox
import time
from electrum.i18n import _
from electrum.gui.qt.util import WindowModalDialog, TaskThread
from electrum.network import Network,TxBroadcastError, BestEffortRequestFailed
from electrum.logging import get_logger,Logger


from functools import partial
import copy

from .. import util as Util
from .. import will as Will

from .. import willexecutors as Willexecutors
_logger = get_logger(__name__)


class BalCloseDialog(BalDialog):

    def __init__(self,bal_window):
        BalDialog.__init__(self,bal_window.window,"Closing BAL")
        self.bal_window=bal_window
        self.message_label = QLabel("Closing BAL:")
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.message_label)
        #self.checking.connect(self.msg_set_checking)
        #self.invalidating.connect(self.msg_set_invalidating)
        #self.building.connect(self.msg_set_building)
        #self.signing.connect(self.msg_set_signing)
        #self.pushing.connect(self.msg_set_pushing)

        #self.askpassword.connect(self.ask_password)
        #self.passworddone.connect(self.password_done)
        self.check_row = None
        self.inval_row = None
        self.build_row = None
        self.sign_row = None
        self.push_row = None
        self.network = Network.get_instance()
        self._stopping = False
        self.thread = TaskThread(self)
        self.thread.finished.connect(self.task_finished)  # see #3956
    def task_finished(self):
        _logger.debug("task finished")
        
    def close_plugin_task(self):
        self.thread.add(self.task_phase1,on_success=self.on_success_phase1,on_done=self.on_accept,on_error=self.on_error_phase1)
        self.show()
        self.exec()

    def task_phase1(self):
        self.msg_set_checking()
        have_to_build=False
        try:
            self.bal_window.init_class_variables()
            self.bal_window.check_will()
            self.msg_set_checking('Ok')
        except Will.WillExpiredException as e:
            self.msg_set_checking("Expired")
            fee_per_byte=self.bal_window.will_settings.get('tx_fees',1)
            return None, Will.invalidate_will(self.bal_window.willitems,self.bal_window.wallet,fee_per_byte)
        except Will.NoHeirsException:
            self.msg_set_checking("No Heirs")
        except Will.NotCompleteWillException as e:
            message = False
            have_to_build=True
            if isinstance(e,Will.HeirChangeException):
                message ="Heirs changed:"
            elif isinstance(e,Will.WillExecutorNotPresent):
                message = "Will-Executor not present"
            elif isinstance(e,Will.WillexecutorChangeException):
                message = "Will-Executor changed"
            elif isinstance(e,Will.TxFeesChangedException):
                message = "Txfees are changed"
            elif isinstance(e,Will.HeirNotFoundException):
                message = "Heir not found"
            if message:
                self.msg_set_checking(message)
            else:
                self.msg_set_checking("New")

        if have_to_build:
            self.msg_set_building()
            try:
                self.bal_window.build_will()
                self.bal_window.check_will()
                for wid in Will.only_valid(self.bal_window.willitems):
                    self.bal_window.wallet.set_label(wid,"BAL Transaction")
                self.msg_set_building("Ok")
            except Exception as e:
                self.msg_set_building(self.msg_error(e))

        have_to_sign = False
        for wid in Will.only_valid(self.bal_window.willitems):
            if not self.bal_window.willitems[wid].get_status("COMPLETE"):
                have_to_sign = True
                break
        return have_to_sign, None
        
    def on_accept(self):
        pass

    def on_accept_phase2(self):
        pass

    def on_error_push(self):
        pass

    def wait(self,secs):
        wait_row=None
        for i in range(secs,0,-1):
            if self._stopping:
                return
            wait_row = self.msg_edit_row(f"Please wait {i}secs",      wait_row)
            time.sleep(1)
        self.msg_del_row(wait_row)

    def loop_broadcast_invalidating(self,tx):
        self.msg_set_invalidating("Broadcasting")
        try:
            tx.add_info_from_wallet(self.bal_window.wallet)
            self.network.run_from_another_thread(tx.add_info_from_network(self.network))
            txid = self.network.run_from_another_thread(self.network.broadcast_transaction(tx,timeout=120),timeout=120)
            self.msg_set_invalidating("Ok")
            _logger.error(f"txid: {txid}")
            

        except TxBroadcastError as e:
            _logger.error(e)
            msg = e.get_message_for_gui()
            self.msg_set_invalidating(self.msg_error(msg))
        except BestEffortRequestFailed as e:
            self.msg_set_invalidating(self.msg_error(e))
        #    self.loop_broadcast_invalidating(tx)

    def loop_push(self):
        self.msg_set_pushing("Broadcasting")
        retry = False
        try:
            willexecutors=Willexecutors.get_willexecutor_transactions(self.bal_window.willitems)
            for url,willexecutor in willexecutors.items():
                try:
                    if not Willexecutors.push_transactions_to_willexecutor(willexecutor):
                        for wid in willexecutor['txsids']:
                            self.bal_window.willitems[wid].set_status('PUSH_FAIL',True)
                        retry=True
                    else:
                        for wid in willexecutor['txsids']:
                            self.bal_window.willitems[wid].set_status('PUSHED',True)
                except Willexecutors.AlreadyPresentException:
                    for wid in willexecutor['txsids']:
                        row = self.msg_edit_row("checking {} - {} : {}".format(self.bal_window.willitems[wid].we['url'],wid, "Waiting"))
                        self.bal_window.willitems[wid].check_willexecutor()
                        row = self.msg_edit_row("checked {} - {} : {}".format(self.bal_window.willitems[wid].we['url'],wid,self.bal_window.willitems[wid] ),row)
                        
                            
                except Exception as e:
                    _logger.error(e)
                    raise e
            if retry:
                raise Exception("retry")

        except Exception as e:
            self.msg_set_pushing(self.msg_error(e))
            self.wait(10)
            if not self._stopping:
                self.loop_push()


    def invalidate_task(self,tx,password):
        _logger.debug(f"invalidate tx: {tx}")
        tx = self.bal_window.wallet.sign_transaction(tx,password)
        try:
            if tx:
                if tx.is_complete():
                    _logger.debug("is complete")
                    self.loop_broadcast_invalidating(tx)
                    self.wait(5)
                else:
                    raise
            else:
                raise
        except:
            self.msg_set_invalidating("Error")
            raise Exception("Impossible to sign")
    def on_success_invalidate(self,success):
        _logger.debug("SUCCESS")
        self.thread.add(self.task_phase1,on_success=self.on_success_phase1,on_done=self.on_accept,on_error=self.on_error_phase1)
    def on_error(self,error):
        _logger.error(error)
        pass
    def on_success_phase1(self,result):
        have_to_sign,tx = list(result)
        _logger.debug(f"have to sign: {have_to_sign}")
        password=None
        if have_to_sign is None:
            self.msg_set_invalidating()
           #need to sign invalidate and restart phase 1
            password = self.bal_window.get_wallet_password("Invalidate your old will",parent=self)
            if password is False:
                self.msg_set_invalidating("Aborted")
                self.wait(3)
                self.close()
                return
            self.thread.add(partial(self.invalidate_task,tx,password),on_success=self.on_success_invalidate, on_done=self.on_accept, on_error=self.on_error)
            
            return
        elif have_to_sign:
            password = self.bal_window.get_wallet_password("Sign your will",parent=self)
            if password is False:
                self.msg_set_signing('Aborted')
        else:
            self.msg_set_signing('Nothig to do')
        self.thread.add(partial(self.task_phase2,password),on_success=self.on_success_phase2,on_done=self.on_accept_phase2,on_error=self.on_error_phase2)
        return
    
    def on_success_phase2(self,arg):
        self.thread.stop()
        self.bal_window.save_willitems()
        self.msg_edit_row("Finished")
        self.close()

    def closeEvent(self,event):
        self._stopping=True
        self.thread.stop()

    def task_phase2(self,password):

        try:
            if txs:=self.bal_window.sign_transactions(password):
                for txid,tx in txs.items():
                    self.bal_window.willitems[txid].tx = copy.deepcopy(tx)
                self.bal_window.save_willitems()
                self.msg_set_signing("Ok")
        except Exception as e:
            self.msg_set_signing(self.msg_error(e))
        self.msg_set_pushing()
        have_to_push = False
        for wid in Will.only_valid(self.bal_window.willitems):
            w=self.bal_window.willitems[wid]
            if w.we and w.get_status("COMPLETE") and not w.get_status("PUSHED"):
                have_to_push = True
        _logger.debug(f"have to push: :{have_to_push}")
        if not have_to_push:
            self.msg_set_pushing("Nothing to do")
        else:
            try:
                self.loop_push()
                self.msg_set_pushing("Ok")

            except Exception as e:
                self.msg_set_pushing(self.msg_error(e))
        self.msg_edit_row("Ok")
        self.wait(5)

    def on_error_phase1(self,error):
        _logger.error(f"error phase1: {error}")

    def on_error_phase2(self,error):
        _logger.error("error phase2: { error}")


    def msg_set_checking(self, status = None, row = None):
        row = self.check_row if row is None else row
        self.check_row = self.msg_set_status("Checking your will",    row,  status)

    def msg_set_invalidating(self, status = None, row = None):
        row = self.inval_row if row is None else row
        self.inval_row = self.msg_set_status("Invalidating old will",    self.inval_row,  status)

    def msg_set_building(self, status = None, row = None):
        row = self.build_row if row is None else row
        self.build_row = self.msg_set_status("Building your will",    self.build_row,  status)

    def msg_set_signing(self, status = None, row = None):
        row = self.sign_row if row is None else row
        self.sign_row = self.msg_set_status("Signing your will",      self.sign_row,   status)

    def msg_set_pushing(self, status = None, row = None):
        row = self.push_row if row is None else row
        self.push_row = self.msg_set_status("Broadcasting your will to executors",      self.push_row,   status)

    def msg_set_waiting(self, status = None, row = None):
        row = self.wait_row if row is None else row
        self.wait_row = self.msg_edit_row(f"Please wait {status}secs",      self.wait_row)

    def msg_error(self,e):
        return "Error: {}".format(e)

    def msg_set_status(self,msg,row,status=None):
        status= "Wait" if status is None else status
        line="{}:\t{}".format(_(msg), status)
        return self.msg_edit_row(line,row)
        
        #return v$msg_edit_row("{}:\t{}".format(_(msg), status), row)
    
    def ask_password(self,msg=None):
        self.password=self.bal_window.get_wallet_password(msg,parent=self)

    def msg_edit_row(self,line,row=None):
        _logger.debug(f"{row},{line}")
        msg=self.get_text()
        rows=msg.split("\n")
        try:
            rows[row]=line
        except:
            rows.append(line)
        row=len(rows)-1
        self.update("\n".join(rows))
    
        return row

    def msg_del_row(self,row):
        _logger.debug(f"del row: {row}")
        try:
            msg=self.get_text()
            rows=msg.split("\n")
            del rows[row]
            self.update("\n".join(rows))
        except:
            pass

    def update(self,msg):
        self.message_label.setText(msg)
        self.message_label.update()
        self.message_label.repaint()

    def get_text(self):
        return self.message_label.text()
def ThreadStopped(Exception):
    pass
