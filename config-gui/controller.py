#!/usr/bin/env python3

#
# This file is part of ibus-bogo-python project.
#
# Copyright (C) 2012 Long T. Dam <longdt90@gmail.com>
# Copyright (C) 2012-2013 Trung Ngo <ndtrung4419@gmail.com>
# Copyright (C) 2013 Duong H. Nguyen <cmpitg@gmail.com>
#
# ibus-bogo-python is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ibus-bogo-python is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ibus-bogo-python.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import logging
import hashlib
import json
from PySide.QtCore import *
from PySide.QtGui import *
from PySide.QtUiTools import QUiLoader
from gi.repository import Notify
import charset_converter

# Import stuff from BoGo
current_dir = os.path.dirname(__file__)

sys.path.append(os.path.abspath(os.path.join(current_dir, "..")))
sys.path.append(os.path.abspath(os.path.join(current_dir, "..", "ibus_engine")))

from base_config import BaseConfig
import vncharsets


# Find the config file or create one if none exists
_dirname = os.path.expanduser("~/.config/ibus-bogo/")
if not os.path.exists(_dirname):
    os.makedirs(_dirname)
config_path = os.path.join(_dirname, "config.json")
jsonData = open(config_path)

# Fill in some global data
config = json.load(jsonData)
inputMethodList = list(config["default-input-methods"].keys())

if "custom-input-methods" in config:
    inputMethodList += list(config["custom-input-methods"].keys())

charsetList = [
    "utf-8",
    "tcvn3",
    "vni"
]

DEFAULT_LOCALE = "vi_VN"

# logging.basicConfig(level=logging.DEBUG)


class Settings(BaseConfig, QObject):
    # TODO: Make this thing reactive

    changed = Signal()

    def __init__(self, path):
        BaseConfig.__init__(self, config_path)
        # QObject.__init__()

        self.fileHash = hashlib.md5(str(self.keys).encode('utf-8')).hexdigest()
        self.watcher = QFileSystemWatcher([path])
        self.watcher.fileChanged.connect(self._on_file_changed)

    def _on_file_changed(self, path):
        self.read_config(path)
        h = hashlib.md5(str(self.keys).encode('utf-8')).hexdigest()
        if h != self.fileHash:
            self.changed.emit()
            self.fileHash = h
            logging.debug("File changed")


class Window(QWidget):

    def __init__(self, app, settings):
        super(Window, self).__init__()

        self.app = app
        self.settings = settings
        self.settings.changed.connect(self.refreshGui)

        if "gui-language" in settings:
            locale = settings["gui-language"]
        else:
            locale = DEFAULT_LOCALE

        self.translator = QTranslator()
        self.translator.load(os.path.join(current_dir, "locales", locale))
        app.installTranslator(self.translator)

        loader = QUiLoader()
        loader.setLanguageChangeEnabled(True)
        self.win = loader.load(os.path.join(current_dir, "controller.ui"), self)
        QMetaObject.connectSlotsByName(self)

        # Define GUI items
        self.inputCombo = self.win.findChild(QComboBox, "inputMethodComboBox")
        self.charsetCombo = self.win.findChild(QComboBox, "charsetComboBox")
        self.skipNonVNCheckBox = self.win.findChild(QCheckBox, "skipNonVNCheckBox")
        self.guiLanguageComboBox = self.win.findChild(QComboBox, "guiLanguageComboBox")

        self.sourceCharsetCombo = self.win.findChild(QComboBox, "sourceCharsetCombo")

        # Set their initial values
        for i in range(len(inputMethodList)):
            self.inputCombo.insertItem(i, inputMethodList[i])

        for i in range(len(charsetList)):
            self.charsetCombo.insertItem(i, charsetList[i])
            if charsetList[i] != "utf-8":
                self.sourceCharsetCombo.insertItem(i, charsetList[i].upper())

        self.setupLanguages()
        self.refreshGui()

        box = QVBoxLayout()
        box.addWidget(self.win)
        self.setLayout(box)

    @Slot()
    def on_closeButton_clicked(self):
        self.close()

    @Slot()
    def on_helpButton_clicked(self):
        logging.debug("help")

    @Slot()
    def on_resetButton_clicked(self):
        self.settings.reset()

    @Slot(str)
    def on_inputMethodComboBox_activated(self, index):
        logging.debug("inputComboChanged: %s", index)
        self.settings["input-method"] = index

    @Slot(str)
    def on_charsetComboBox_activated(self, index):
        logging.debug("charsetComboChanged: %s", index)
        self.settings["output-charset"] = index

    @Slot(bool)
    def on_skipNonVNCheckBox_clicked(self, state):
        logging.debug("skipNonVNCheckBoxChanged: %s", str(state))
        self.settings["skip-non-vietnamese"] = state

    @Slot(int)
    def on_guiLanguageComboBox_activated(self, index):
        self.switchLanguage(self.guiLanguages[index][0])
        self.settings["gui-language"] = self.guiLanguages[index][0]

    @Slot()
    def on_convertButton_clicked(self):
        # TODO Don't always process when the button is pressed.
        clipboard = self.app.clipboard()
        mime = clipboard.mimeData()
        sourceEncoding = self.sourceCharsetCombo.currentText().lower()
        try:
            if mime.hasHtml() or mime.hasText():
                html, text = mime.html(), mime.text()
                html, text = charset_converter.convert(html, text, sourceEncoding)

                new_mime = QMimeData()
                new_mime.setHtml(html)
                new_mime.setText(text)

                clipboard.setMimeData(new_mime)
                n = Notify.Notification.new("Converted", sourceEncoding + "-> utf-8", "")
            else:
                n = Notify.Notification.new("Cannot convert", "No HTML/plain text data in clipboard.", "")
        except UnicodeEncodeError:
            n = Notify.Notification.new("Cannot convert", "Mixed Unicode in clipboard.", "")
        n.show()

    def switchLanguage(self, locale):
        logging.debug("switchLanguage: %s", locale)
        if locale == "en_US":
            self.app.removeTranslator(self.translator)
        else:
            self.app.removeTranslator(self.translator)
            self.translator.load(os.path.join(current_dir, "locales", locale))
            self.app.installTranslator(self.translator)

    def setupLanguages(self):
        self.guiLanguages = [
            ("en_US", "English (US)"),
            ("vi_VN", "Vietnamese")
        ]

        self.guiLanguageComboBox.clear()
        for index, lang in enumerate(self.guiLanguages):
            self.guiLanguageComboBox.insertItem(index, QIcon(os.path.join(current_dir, "locales", lang[0] + ".png")), lang[1])
        if "gui-language" in self.settings:
            index = [y[0] for y in self.guiLanguages].index(self.settings["gui-language"])
        else:
            index = [y[0] for y in self.guiLanguages].index(DEFAULT_LOCALE)
        self.guiLanguageComboBox.setCurrentIndex(index)

    def refreshGui(self):
        self.inputCombo.setCurrentIndex(inputMethodList.index(self.settings["input-method"]))
        self.charsetCombo.setCurrentIndex(charsetList.index(self.settings["output-charset"]))
        self.skipNonVNCheckBox.setChecked(self.settings["skip-non-vietnamese"])
        if "gui-language" in self.settings:
            self.switchLanguage(self.settings["gui-language"])

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            self.setWindowTitle(self.tr("IBus BoGo Settings"))


def main():
    vncharsets.init()
    Notify.init("IBus BoGo Settings")
    app = QApplication(sys.argv)

    settings = Settings(config_path)

    win = Window(app, settings)
    win.show()

    app.exec_()
    sys.exit()


if __name__ == '__main__':
    main()
