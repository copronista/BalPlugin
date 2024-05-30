import random
import os
from hashlib import sha256
from typing import NamedTuple, Optional, Dict, Tuple

from electrum.plugin import BasePlugin
from electrum.util import to_bytes, bfh
from electrum import json_db
from electrum.transaction import tx_from_any

from .util import print_var
json_db.register_dict('heirs', tuple, None)
json_db.register_dict('will', lambda x: get_will(x), None)

def get_will(x):
    try:
        x['tx']=tx_from_any(x['tx'])
    except Exception as e:
        print_var(x)
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
    SELECTED_WILLEXECUTORS = "bal_selected_willexecutors"



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
        WILLEXECUTORS:  {
            'https://bitcoinafter.life/': {
                "base_fee": 100000,
                "status": 0,
                "info":"Bitcoin After Life Will Executor"
            }
        },
        SELECTED_WILLEXECUTORS:[],
    }


    LATEST_VERSION = '1'
    KNOWN_VERSIONS = ('0', '1')
    assert LATEST_VERSION in KNOWN_VERSIONS

    SIZE = (159, 97)

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.base_dir = os.path.join(config.electrum_path(), 'bal')
        self.parent = parent
        self.config = config
        self.name = name
        self.willexecutors = {}

    def config_get(self,key):
        v = self.config.get(key,None)
        if v is None:
            self.config.set_key(key,self.DEFAULT_SETTINGS[key],save=True)
            v = self.DEFAULT_SETTINGS[key]
        return v

