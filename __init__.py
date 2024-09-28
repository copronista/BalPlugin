from electrum.i18n import _
import subprocess

BUILD_NUMBER = 20
REVISION_NUMBER = 0
VERSION_NUMBER = 0
def version():
    return f'{VERSION_NUMBER}.{REVISION_NUMBER}-{BUILD_NUMBER}'

fullname = _('B.A.L.')
description = ''.join([
    _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.life/</a><br/>",
    "<p style='font-size:8pt;vertialAlign:bottom'>Version: ", version(),"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
