import random
import os
from hashlib import sha256
from typing import NamedTuple, Optional, Dict, Tuple

from electrum.plugin import BasePlugin
from electrum.util import to_bytes, bfh
from electrum import json_db
from electrum.transaction import tx_from_any

from . import util as Util
from . import willexecutors as Willexecutors
import os
json_db.register_dict('heirs', tuple, None)
json_db.register_dict('will', lambda x: get_will(x), None)
json_db.register_dict('will_settings', lambda x:x, None)

def get_will(x):
    try:
        #print("______________________________________________________________________________________________________")
        #print(x)
        x['tx']=tx_from_any(x['tx'])
    except Exception as e:
        Util.print_var(x)
        raise e

    return x


class BalPlugin(BasePlugin):
    LOCKTIME_TIME = "bal_locktime_time"
    LOCKTIME_BLOCKS = "bal_locktime_blocks"
    LOCKTIMEDELTA_TIME = "bal_locktimedelta_time"
    LOCKTIMEDELTA_BLOCKS = "bal_locktimedelta_blocks"
    TX_FEES = "bal_tx_fees"
    BROADCAST = "bal_broadcast"
    ASK_BROADCAST = "bal_ask_broadcast"
    INVALIDATE = "bal_invalidate"
    ASK_INVALIDATE = "bal_ask_invalidate"
    PREVIEW = "bal_preview"
    SAVE_TXS = "bal_save_txs"
    WILLEXECUTORS = "bal_willexecutors"
    PING_WILLEXECUTORS = "bal_ping_willexecutors"
    ASK_PING_WILLEXECUTORS = "bal_ask_ping_willexecutors"
    NO_WILLEXECUTOR = "bal_no_willexecutor"
    HIDE_REPLACED = "bal_hide_replaced"
    HIDE_INVALIDATED = "bal_hide_invalidated"
    ALLOW_REPUSH = "bal_allow_repush"



    DEFAULT_SETTINGS={
        LOCKTIME_TIME: 90,
        LOCKTIME_BLOCKS: 144*90,
        LOCKTIMEDELTA_TIME: 7,
        LOCKTIMEDELTA_BLOCKS:144*7,
        TX_FEES: 100,
        BROADCAST: True,
        ASK_BROADCAST: True,
        INVALIDATE: True,
        ASK_INVALIDATE: True,
        PREVIEW: True,
        SAVE_TXS: True,
        PING_WILLEXECUTORS: False,
        ASK_PING_WILLEXECUTORS: False,
        NO_WILLEXECUTOR: False,
        HIDE_REPLACED:True,
        HIDE_INVALIDATED:True,
        ALLOW_REPUSH: False,
        WILLEXECUTORS:  {
            'https://bitcoin-after.life/': {
                "base_fee": 100000,
                "status": "New",
                "info":"Bitcoin After Life Will Executor",
                "address":"bcrt1qa5cntu4hgadw8zd3n6sq2nzjy34sxdtd9u0gp7"
            }
        },
    }

    STATUS_NEW = 'New'
    STATUS_COMPLETE = 'Signed'
    STATUS_BROADCASTED = 'Broadcasted'
    STATUS_PUSHED = 'Pushed'
    STATUS_NOT_PUSHED = 'Push Failed'
    STATUS_EXPORTED = 'Exported'
    STATUS_REPLACED = 'Replaced'
    STATUS_INVALIDATED = 'Invalidated' 
    STATUS_ANTICIPATED = 'Anticipated'
    STATUS_RESTORED = 'Restored'
    STATUS_VALID = 'Valid'
    STATUS_CHECKED = 'Checked'
    STATUS_NOT_CHECKED = 'Check Failed'

    LATEST_VERSION = '1'
    KNOWN_VERSIONS = ('0', '1')
    assert LATEST_VERSION in KNOWN_VERSIONS

    SIZE = (159, 97)

    def __init__(self, parent, config, name):
        """
        print("registered_dicts:",json_db.registered_dicts)
        print("registered_names:",json_db.registered_names)
        if not "heirs" in json_db.registered_dicts:
            print("heir NOT registered")
            json_db.register_dict('heirs', tuple, None)

        if not "will" in json_db.registered_dicts:
            print("will NOT registered")
            json_db.register_dict('will', lambda x: get_will(x), None)
            json_db.register_name('will', lambda x: get_will(x))
        """
        BasePlugin.__init__(self, parent, config, name)
        self.base_dir = os.path.join(config.electrum_path(), 'bal')
        print(self.base_dir)
        self.parent = parent
        self.config = config
        self.name = name
        self._hide_invalidated= self.config_get(self.HIDE_INVALIDATED)
        self._hide_replaced= self.config_get(self.HIDE_REPLACED)

        self.plugin_dir = os.path.split(os.path.realpath(__file__))[0]

        #self.willexecutors = Willexecutors.get_willexecutors(self)

        #self.selected_willexecutors = self.get_config(self.SELECTED_WILLEXECUTORS)

    def resource_path(self,*parts):
        return os.path.join(self.plugin_dir, *parts)


    def config_get(self,key):
        v = self.config.get(key,None)
        if v is None:
            self.config.set_key(key,self.DEFAULT_SETTINGS[key],save=True)
            v = self.DEFAULT_SETTINGS[key]
        return v

    def hide_invalidated(self):
        self._hide_invalidated = not self._hide_invalidated
        self.config.set_key(BalPlugin.HIDE_INVALIDATED,self.hide_invalidated,save=True)

    def hide_replaced(self):
        self._hide_replaced = not self._hide_replaced
        self.config.set_key(BalPlugin.HIDE_REPLACED,self.hide_invalidated,save=True)
