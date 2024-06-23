from electrum.i18n import _
import subprocess
try:
    from electrum.plugins.BalPlugin._version import version
except:
    print("oh oh init")
    from ._version import version

BUILD_NUMBER = 2
fullname = _('B.A.L.')
description = ''.join([
    _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.lif1e/</a><br/>",
    "<p style='font-size:8pt;vertialAlign:bottom'>Version: ", version(),"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
