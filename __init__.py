from electrum.i18n import _
import subprocess
import os
BUILD_NUMBER = 20
REVISION_NUMBER = 0
VERSION_NUMBER = 0
def version():
    return f'{VERSION_NUMBER}.{REVISION_NUMBER}-{BUILD_NUMBER}'

def bal_get_path():
    return os.path.split(os.path.realpath(__file__))[0]
def bal_resource_path(*parts): 
        return os.path.join(bal_get_path(), *parts)
fullname = _('B.A.L.')
description = ''.join([
    "<img src='",bal_resource_path('icons','bal.png'),"'>", _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.life/</a><br/>",
    "<p style='font-size:8pt;vertialAlign:bottom'>Version: ", version(),"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
