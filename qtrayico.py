#! /usr/bin/env python
import sys
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import *
from constants import *
'''
to use a tray icon just copy the main method.
For your main window you must subclass HideableWindow
then subclass systray and redefine createActions if you wish
'''
class HideableWindow(QtWidgets.QMainWindow):
    def __init__(self,parent=None):
                super(HideableWindow,self).__init__(parent)
                self.geometry=None
                self.state=None
##                QTimer.singleShot(2000,lambda:self.resize(self.sizeHint()))
        
    def closeEvent(self,event): #override default close functionality to minimize to tray instead
         self.geometry = self.saveGeometry()
         self.state = self.saveState()
         self.hide()
         event.ignore()
         
    def showEvent(self,event):
        if not event.spontaneous():
            if self.geometry:
                QTimer.singleShot(0,self.restorePosition)
                
    def restorePosition(self):
        if self.state:
            self.restoreGeometry(self.geometry)
            self.restoreState(self.state) # restore state second to avoid flashing
        
class Systray(QtWidgets.QWidget):
    def __init__(self,main_window):
        QtWidgets.QWidget.__init__(self)
        
        self.main_window=main_window
        
        self.createActions()
        self.createTrayIcon()
        self.actions=[]
        self.trayIcon.show()

    def createActions(self):
        self.actions=[]
        self.quitAction = QtWidgets.QAction(self.tr("&Quit"), self)
        self.quitAction.triggered.connect(QtWidgets.QApplication.quit)
        self.actions.append(self.quitAction)

    def createTrayIcon(self):
        self.trayIconMenu = QtWidgets.QMenu(self)
        for action in self.actions:
                self.trayIconMenu.addAction(action)

        self.trayIcon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(resource_path("book_tray.ico")), self)#was (self)
        self.trayIcon.setContextMenu(self.trayIconMenu)
        self.trayIcon.activated.connect(self.toggle_show)
    
    def toggle_show(self, value):
        if self.main_window.isHidden():
            self.main_window.showNormal()
            self.main_window.activateWindow()
        else:
            self.main_window.close()

