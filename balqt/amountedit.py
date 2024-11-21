# -*- coding: utf-8 -*-

from typing import Union
from decimal import Decimal

from . import qt_resources
if qt_resources.QT_VERSION == 5:
    from PyQt5.QtWidgets import (QLineEdit, QStyle, QStyleOptionFrame, QSizePolicy)
    from PyQt5.QtGui import QPalette, QPainter
    from PyQt5.QtCore import pyqtSignal, Qt, QSize
else:
    from PyQt6.QtWidgets import (QLineEdit, QStyle, QStyleOptionFrame, QSizePolicy)
    from PyQt6.QtGui import QPalette, QPainter
    from PyQt6.QtCore import pyqtSignal, Qt, QSize


from electrum.util import (format_satoshis_plain, decimal_point_to_base_unit_name,
                           FEERATE_PRECISION, quantize_feerate, DECIMAL_POINT, UI_UNIT_NAME_FEERATE_SAT_PER_VBYTE)

from electrum.gui.qt.amountedit import BTCAmountEdit, char_width_in_lineedit, ColorScheme

_NOT_GIVEN = object()  # sentinel value


class PercAmountEdit(BTCAmountEdit):
    def __init__(self, decimal_point, is_int=False, parent=None, *, max_amount=_NOT_GIVEN):
        super().__init__(decimal_point, is_int, parent, max_amount=max_amount)

    def numbify(self):
        text = self.text().strip()
        if text == '!':
            self.shortcut.emit()
            return
        pos = self.cursorPosition()
        chars = '0123456789%'
        chars += DECIMAL_POINT
        
        s = ''.join([i for i in text if i in chars])

        if '%' in s:
            self.is_perc=True
            s=s.replace('%','')
        else:
            self.is_perc=False

        if DECIMAL_POINT in s:
            p = s.find(DECIMAL_POINT)
            s = s.replace(DECIMAL_POINT, '')
            s = s[:p] + DECIMAL_POINT + s[p:p+8]
        if self.is_perc:
            s+='%'


        #if self.max_amount:
        #    if (amt := self._get_amount_from_text(s)) and amt >= self.max_amount:
        #        s = self._get_text_from_amount(self.max_amount)
        self.setText(s)
        # setText sets Modified to False.  Instead we want to remember
        # if updates were because of user modification.
        self.setModified(self.hasFocus())
        self.setCursorPosition(pos)
        #if len(s>0)
        #    self.drawText("")

    def _get_amount_from_text(self, text: str) -> Union[None, Decimal, int]:
        try:
            text = text.replace(DECIMAL_POINT, '.')
            text = text.replace('%', '')
            return (Decimal)(text)
        except Exception:
            return None

    def _get_text_from_amount(self, amount):
        out = super()._get_text_from_amount(amount)
        if self.is_perc: out+='%'
        return out

    def paintEvent(self, event):
        QLineEdit.paintEvent(self, event)
        if self.base_unit:
            panel = QStyleOptionFrame()
            self.initStyleOption(panel)
            textRect = self.style().subElementRect(QStyle.SubElement.SE_LineEditContents, panel, self)
            textRect.adjust(2, 0, -10, 0)
            painter = QPainter(self)
            painter.setPen(ColorScheme.GRAY.as_color())
            if len(self.text())==0:
                painter.drawText(textRect, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), self.base_unit() + " or perc value")

