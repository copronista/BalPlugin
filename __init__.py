from electrum.i18n import _
import subprocess
from . import bal_resources
BUILD_NUMBER = 20
REVISION_NUMBER = 0
VERSION_NUMBER = 0
def _version():
    return f'{VERSION_NUMBER}.{REVISION_NUMBER}-{BUILD_NUMBER}'

version = _version()
author = "Bal Enterprise inc."
fullname = _('B.A.L.')
description = ''.join([
    "<img src='",bal_resources.icon_path('bal16x16.png'),"'>", _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.life/</a><br/>",
    "<p style='font-size:8pt;vertialAlign:bottom'>Version: ", _version(),"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
