from electrum.i18n import _
import subprocess
commit = "v0.0"
try:
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
except:
    pass
fullname = _('B.A.L.')
description = ''.join([
    _("Bitcoin After Life"), '<br/>',
    _("For more information, visit"),
    " <a href=\"https://bitcoin-after.life/\">https://bitcoin-after.life/</a><br/>",
    "<p style='font-size:8pt;'>Version: ", commit,"</p>"
])
#available_for = ['qt', 'cmdline', 'qml']
available_for = ['qt']
