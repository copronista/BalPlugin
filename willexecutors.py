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


def push_transactions_to_willexecutors(will):
    willexecutors ={}
    for wid in will:
        willitem = will[wid]
        if willitem['Valid']:
            if willitem['Signed']:
                if not willitem['Pushed']:
                    if 'willexecutor' in willitem:
                        willexecutor=willitem['willexecutor']
                        if  willexecutor and is_selected(willexecutor):
                            url=willexecutor['url']
                            if not url in willexecutors:
                                willexecutor['txs']=""
                                willexecutor['txsids']=[]
                                willexecutors[url]=willexecutor
                            willexecutors[url]['txs']+=str(willitem['tx'])+"\n"
                            willexecutors[url]['txsids'].append(wid)
    if not willexecutors:
        return
    for url in willexecutors:
        willexecutor = willexecutors[url]
        if is_selected(willexecutor):
            if 'txs' in willexecutor:
                if push_transactions_to_willexecutor(willexecutors[url]['txs'],url):
                    for wid in willexecutors[url]['txsids']:
                        will[wid]['Pushed']=True
                        will[wid]['status']+='.Pushed'
                del willexecutor['txs']

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


def push_transactions_to_willexecutor(strtxs,url):
    try:
        return send_request('post', url+"/"+constants.net.NET_NAME+"/pushtxs", data=strtxs.encode('ascii'))
    except:
        return False

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
        _logger.error("errore aprendo willexecutors.json:",e)
        return {}

def check_transaction(txid,url):
    _logger.debug(f"{url}:{txid}")
    try:
        w = send_request('post',url+"/searchtx",data=txid.encode('ascii'))
        return w
    except Exception as e:
        raise e
        _logger.error(f"error contacting {url} for checking txs {e}")
