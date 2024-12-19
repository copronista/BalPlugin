import json
from datetime import datetime
from functools import partial
from aiohttp import ClientResponse

from electrum.network import Network
from electrum import constants
from electrum.logging import get_logger
from electrum.gui.qt.util import WaitingDialog
from electrum.i18n import _

from .balqt.baldialog import BalWaitingDialog
from . import util as Util

DEFAULT_TIMEOUT = 5
_logger = get_logger(__name__)

def get_willexecutors(bal_plugin, update = False,bal_window=False,force=False,task=True):
    willexecutors = bal_plugin.config_get(bal_plugin.WILLEXECUTORS)
    for w in willexecutors:
        initialize_willexecutor(willexecutors[w],w)

    bal=bal_plugin.DEFAULT_SETTINGS[bal_plugin.WILLEXECUTORS]
    for bal_url,bal_executor in bal.items():
        if not bal_url in willexecutors:
            _logger.debug("replace bal")
            willexecutors[bal_url]=bal_executor
    if update:
        found = False
        for url,we in willexecutors.items():
            if is_selected(we):
                found = True
        if found or force:
            if bal_plugin.config_get(bal_plugin.PING_WILLEXECUTORS) or force:
                ping_willexecutors = True
                if bal_plugin.config_get(bal_plugin.ASK_PING_WILLEXECUTORS) and not force:
                    ping_willexecutors = bal_window.window.question(_("Contact willexecutors servers to update payment informations?"))
                if ping_willexecutors:
                    if task:
                        bal_window.ping_willexecutors(willexecutors)
                    else:
                        bal_window.ping_willexecutors_task(willexecutors)
    return willexecutors

def is_selected(willexecutor,value=None):
    if not value is None:
        willexecutor['selected']=value
    try:
        return willexecutor['selected']
    except:
        willexecutor['selected']=False
        return False

def get_willexecutor_transactions(will, force=False):
    willexecutors ={}
    for wid,willitem in will.items():
        if willitem.get_status('VALID'):
            if willitem.get_status('COMPLETE'):
                if not willitem.get_status('PUSHED') or force:
                    if willexecutor := willitem.we:
                        if  willexecutor and is_selected(willexecutor):
                            url=willexecutor['url']
                            if not url in willexecutors:
                                willexecutor['txs']=""
                                willexecutor['txsids']=[]
                                willexecutor['broadcast_status']= _("Waiting...")
                                willexecutors[url]=willexecutor
                            willexecutors[url]['txs']+=str(willitem.tx)+"\n"
                            willexecutors[url]['txsids'].append(wid)

    return willexecutors

def push_transactions_to_willexecutors(will):
    willexecutors = get_transactions_to_be_pushed()
    for url in willexecutors:
        willexecutor = willexecutors[url]
        if is_selected(willexecutor):
            if 'txs' in willexecutor:
                push_transactions_to_willexecutor(willexecutors[url]['txs'],url)

def send_request(method, url, data=None, *, timeout=10):
    network = Network.get_instance()
    if not network:
        raise ErrorConnectingServer('You are offline.')
    _logger.debug(f'<-- {method} {url} {data}')
    headers = {}
    headers['user-agent'] = 'BalPlugin'
    headers['Content-Type']='text/plain'

    try:
        if method == 'get':
            response = Network.send_http_on_proxy(method, url,
                                                  params=data,
                                                  headers=headers,
                                                  on_finish=handle_response,
                                                  timeout=timeout)
        elif method == 'post':
            response = Network.send_http_on_proxy(method, url,
                                                  body=data,
                                                  headers=headers,
                                                  on_finish=handle_response,
                                                  timeout=timeout)
        else:
            raise Exception(f"unexpected {method=!r}")
    except Exception as e:
        _logger.error(f"exception sending request {e}")
        raise e
    else:
        _logger.debug(f'--> {response}')
        return response
async def handle_response(resp:ClientResponse):
    r=await resp.text()
    try:
        r=json.loads(r)
        r['status'] = resp.status
        r['selected']=is_selected(willexecutor)
        r['url']=url
    except:
        pass    
    return r

class AlreadyPresentException(Exception):
    pass
def push_transactions_to_willexecutor(willexecutor):
    out=True
    try:
        _logger.debug(f"willexecutor['txs']")
        if w:=send_request('post', willexecutor['url']+"/"+constants.net.NET_NAME+"/pushtxs", data=willexecutor['txs'].encode('ascii')):
            willexecutor['broadcast_stauts'] = _("Success")
            _logger.debug(f"pushed: {w}")
            if w !='thx':
                logger._debug(f"error: {w}")
                raise Exception(w)
        else:
            raise Exception("empty reply from:{willexecutor['url']}")
    except Exception as e:
        _logger.debug(f"error:{e}")
        if str(e) == "already present":
            raise AlreadyPresentException()
        out=False
        willexecutor['broadcast_stauts'] = _("Failed")

    return out

def ping_servers(willexecutors):
    for url,we in willexecutors.items():
        willexecutors[url]=get_info_task(url,we)


def get_info_task(url,willexecutor):
    w=None
    try:
        _logger.info("GETINFO_WILLEXECUTOR")
        _logger.debug(url)
        w = send_request('get',url+"/"+constants.net.NET_NAME+"/info")
        willexecutor['status'] = w['status']
        willexecutor['base_fee'] = w['base_fee']
        willexecutor['address'] = w['address']
        if not willexecutor['info']:
            willexecutor['info'] = w['info']
        _logger.debug(f"response_data {w['address']}")
    except Exception as e:
        _logger.error(f"error {e} contacting {url}: {w}")
        willexecutor['stauts']="KO"
    
    willexecutor['last_update'] = datetime.now().timestamp()
    return willexecutor

def initialize_willexecutor(willexecutor,url,status=None,selected=None):
    willexecutor['url']=url
    if not status is None:
        willexecutor['status'] = status
    willexecutor['selected'] = is_selected(willexecutor,selected)

def get_willexecutors_list_from_json(bal_plugin):
    try:
        with open("willexecutors.json") as f:
            willexecutors = json.load(f)
            for w in willexecutors:
                willexecutor=willexecutors[w]
                willexecutors.initialize_willexecutor(willexecutor,w,'New',False)
            bal_plugin.config.set_key(bal_plugin.WILLEXECUTORS,willexecutors,save=True)
            return h
    except Exception as e:
        _logger.error(f"errore aprendo willexecutors.json: {e}")
        return {}

def check_transaction(txid,url):
    _logger.debug(f"{url}:{txid}")
    try:
        w = send_request('post',url+"/searchtx",data=txid.encode('ascii'))
        return w
    except Exception as e:
        raise e
        _logger.error(f"error contacting {url} for checking txs {e}")
