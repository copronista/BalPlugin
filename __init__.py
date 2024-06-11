from electrum.i18n import _
import subprocess
from electrum.plugins.BalPlugin._version import version

fullname = _('B.A.L.')
description = ''.join([
    _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.lif1e/</a><br/>",
    "<p style='font-size:8pt;vertialAlign:bottom'>Version: ", version(),"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
