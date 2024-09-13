# Copyright (C) 2020 The Electrum developers
# Distributed under the MIT software license, see the accompanying
# file LICENCE or http://www.opensource.org/licenses/mit-license.php

import time
from datetime import datetime
from typing import Optional, Any

from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtGui import QPalette, QPainter
from PyQt5.QtWidgets import (QWidget, QLineEdit, QStyle, QStyleOptionFrame, QComboBox,
                             QHBoxLayout, QDateTimeEdit)

from electrum.i18n import _
from electrum.bitcoin import NLOCKTIME_MIN, NLOCKTIME_MAX, NLOCKTIME_BLOCKHEIGHT_MAX

from electrum.gui.qt.util import char_width_in_lineedit, ColorScheme


class HeirsLockTimeEdit(QWidget):

    valueEdited = pyqtSignal()

    def __init__(self, parent=None,default_index = 1,on_change = None):
        QWidget.__init__(self, parent)

        hbox = QHBoxLayout()
        self.setLayout(hbox)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        self.locktime_raw_e = LockTimeRawEdit(self,on_change=on_change)
        #self.locktime_height_e = LockTimeHeightEdit(self)
        self.locktime_date_e = LockTimeDateEdit(self,on_change=on_change)
        #self.editors = [self.locktime_raw_e, self.locktime_height_e, self.locktime_date_e]
        self.editors = [self.locktime_raw_e, self.locktime_date_e]

        self.combo = QComboBox()
        #options = [_("Raw"), _("Block height"), _("Date")]
        options = [_("Raw"),_("Date")]
        option_index_to_editor_map = {
            0: self.locktime_raw_e,
            #1: self.locktime_height_e,
            1: self.locktime_date_e,
            #2: self.locktime_date_e,
        }
        self.combo.addItems(options)

        def on_current_index_changed(i):
            for w in self.editors:
                w.setVisible(False)
                w.setEnabled(False)
            prev_locktime = self.editor.get_locktime()
            self.editor = option_index_to_editor_map[i]
            if self.editor.is_acceptable_locktime(prev_locktime):
                self.editor.set_locktime(prev_locktime)
            self.editor.setVisible(True)
            self.editor.setEnabled(True)

        self.editor = option_index_to_editor_map[default_index]
        self.combo.currentIndexChanged.connect(on_current_index_changed)
        self.combo.setCurrentIndex(default_index)
        on_current_index_changed(default_index)

        hbox.addWidget(self.combo)
        for w in self.editors:
            hbox.addWidget(w)
        hbox.addStretch(1)

        #self.locktime_height_e.textEdited.connect(self.valueEdited.emit)
        self.locktime_raw_e.textEdited.connect(self.valueEdited.emit)
        self.locktime_date_e.dateTimeChanged.connect(self.valueEdited.emit)
        self.combo.currentIndexChanged.connect(self.valueEdited.emit)

    def get_locktime(self) -> Optional[str]:
        return self.editor.get_locktime()

    def set_locktime(self, x: Any) -> None:
        self.editor.set_locktime(x)


class _LockTimeEditor:
    min_allowed_value = NLOCKTIME_MIN
    max_allowed_value = NLOCKTIME_MAX

    def get_locktime(self) -> Optional[int]:
        raise NotImplementedError()

    def set_locktime(self, x: Any) -> None:
        raise NotImplementedError()

    @classmethod
    def is_acceptable_locktime(cls, x: Any) -> bool:
        if not x:  # e.g. empty string
            return True
        try:
            x = int(x)
        except Exception:
            return False
        return cls.min_allowed_value <= x <= cls.max_allowed_value


class LockTimeRawEdit(QLineEdit, _LockTimeEditor):

    def __init__(self, parent=None,on_change=None):
        QLineEdit.__init__(self, parent)
        self.setFixedWidth(14 * char_width_in_lineedit())
        self.textChanged.connect(self.numbify)
        self.isdays = False
        self.isyears = False
        self.isblocks = False
        self.on_change=on_change

    def replace_str(self,text):
        return str(text).replace('d','').replace('y','').replace('b','')

    def checkbdy(self,s,pos,appendix):
        try:
            charpos = pos-1
            charpos = max(0,charpos)
            charpos = min(len(s)-1,charpos)
            if appendix ==  s[charpos]:
                s=self.replace_str(s)+appendix
                pos = charpos
        except Exception as e:
            pass
        return pos, s

    def numbify(self):
        text = self.text().strip()
        #chars = '0123456789bdy' removed the option to choose locktime by block
        chars = '0123456789dy'
        pos = posx = self.cursorPosition()
        pos = len(''.join([i for i in text[:pos] if i in chars]))
        s = ''.join([i for i in text if i in chars])
        self.isdays = False
        self.isyears = False
        self.isblocks = False

        pos,s = self.checkbdy(s,pos,'d')
        pos,s = self.checkbdy(s,pos,'y')
        pos,s = self.checkbdy(s,pos,'b')

        if 'd' in s: self.isdays = True 
        if 'y' in s: self.isyears = True
        if 'b' in s: self.isblocks = True


        if self.isdays: s= self.replace_str(s) + 'd'
        if self.isyears: s = self.replace_str(s) + 'y'
        if self.isblocks: s= self.replace_str(s) + 'b'

        self.set_locktime(s)
        # setText sets Modified to False.  Instead we want to remember
        # if updates were because of user modification.
        self.setModified(self.hasFocus())
        self.setCursorPosition(pos)
        if self.on_change:
            self.on_change(s)

    def get_locktime(self) -> Optional[str]:
        try:
            return str(self.text())
        except Exception as e:
            return None

    def set_locktime(self, x: Any) -> None:
        out = str(x)
        if 'd' in out:
            out = self.replace_str(x)+'d'
        elif 'y' in out:
            out = self.replace_str(x)+'y'
        elif 'b' in out:
            out = self.replace_str(x)+'b'
        else:
            try:
                out = int(x)
            except Exception as e:
                self.setText('')
                return
            out = max(out, self.min_allowed_value)
            out = min(out, self.max_allowed_value)
        print("set locktime:",str(out))
        self.setText(str(out))


class LockTimeHeightEdit(LockTimeRawEdit):
    max_allowed_value = NLOCKTIME_BLOCKHEIGHT_MAX

    def __init__(self, parent=None,on_change=None):
        LockTimeRawEdit.__init__(self, parent)
        self.setFixedWidth(20 * char_width_in_lineedit())
        self.on_change = on_change

    def paintEvent(self, event):
        super().paintEvent(event)
        panel = QStyleOptionFrame()
        self.initStyleOption(panel)
        textRect = self.style().subElementRect(QStyle.SE_LineEditContents, panel, self)
        textRect.adjust(2, 0, -10, 0)
        painter = QPainter(self)
        painter.setPen(ColorScheme.GRAY.as_color())
        painter.drawText(textRect, int(Qt.AlignRight | Qt.AlignVCenter), "height")


def get_max_allowed_timestamp() -> int:
    ts = NLOCKTIME_MAX
    # Test if this value is within the valid timestamp limits (which is platform-dependent).
    # see #6170
    try:
        datetime.fromtimestamp(ts)
    except (OSError, OverflowError):
        ts = 2 ** 31 - 1  # INT32_MAX
        datetime.fromtimestamp(ts)  # test if raises
    return ts


class LockTimeDateEdit(QDateTimeEdit, _LockTimeEditor):
    min_allowed_value = NLOCKTIME_BLOCKHEIGHT_MAX + 1
    max_allowed_value = get_max_allowed_timestamp()

    def __init__(self, parent=None,on_change=None):
        QDateTimeEdit.__init__(self, parent)
        self.setMinimumDateTime(datetime.fromtimestamp(self.min_allowed_value))
        self.setMaximumDateTime(datetime.fromtimestamp(self.max_allowed_value))
        self.setDateTime(QDateTime.currentDateTime())
        self.on_change = on_change

    def get_locktime(self) -> Optional[int]:
        dt = self.dateTime().toPyDateTime()
        locktime = int(time.mktime(dt.timetuple()))
        return locktime

    def set_locktime(self, x: Any) -> None:
        if not self.is_acceptable_locktime(x):
            self.setDateTime(QDateTime.currentDateTime())
            return
        try:
            x = int(x)
        except Exception:
            self.setDateTime(QDateTime.currentDateTime())
            return
        dt = datetime.fromtimestamp(x)
        self.setDateTime(dt)
        if self.on_change:
            self.on_change(x)
