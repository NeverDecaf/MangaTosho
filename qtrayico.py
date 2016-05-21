#! /usr/bin/env python
import sys
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import *
'''
to use a tray icon just copy the main method.
For your main window you must subclass HideableWindow
then subclass systray and redefine createActions if you wish
'''
class HideableWindow(QtGui.QMainWindow):
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
import os
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class HelloWindow(QtGui.QMainWindow):

	def __init__(self, win_parent = None):
		#Init the base class
		QtGui.QMainWindow.__init__(self, win_parent)
		self.create_widgets()

	def create_widgets(self):
		#Widgets
		self.label = QtGui.QLabel("Say hello:")
		self.hello_edit = QtGui.QLineEdit()
		self.hello_button = QtGui.QPushButton("Push Me!")
		#Horizontal layout
		h_box = QtGui.QHBoxLayout()
		h_box.addWidget(self.label)
		h_box.addWidget(self.hello_edit)
		h_box.addWidget(self.hello_button)
		#Create central widget, add layout and set
		central_widget = QtGui.QWidget()
		central_widget.setLayout(h_box)
		self.setCentralWidget(central_widget)
	def closeEvent(self,event):
            self.hide()
            event.ignore()
		
class Systray(QtGui.QWidget):
    def __init__(self,main_window):
        QtGui.QWidget.__init__(self)
        
        self.main_window=main_window
        
        self.createActions()
        self.createTrayIcon()
        self.actions=[]
        self.trayIcon.show()

    def createActions(self):
        self.actions=[]
        self.quitAction = QtGui.QAction(self.tr("&Quit"), self)
        QtCore.QObject.connect(self.quitAction, QtCore.SIGNAL("triggered()"),
        QtGui.qApp, QtCore.SLOT("quit()"))
        self.actions.append(self.quitAction)

    def createTrayIcon(self):
        self.trayIconMenu = QtGui.QMenu(self)
        for action in self.actions:
                self.trayIconMenu.addAction(action)

        self.trayIcon = QtGui.QSystemTrayIcon(QtGui.QIcon(resource_path("book.ico")), self)#was (self)
        self.trayIcon.setContextMenu(self.trayIconMenu)
        self.trayIcon.activated.connect(self.click_trap)
        
    def click_trap(self, value):
        if value == QtGui.QSystemTrayIcon.DoubleClick: 
            self.main_window.showNormal()
##            if self.main_window.windowState() == Qt.WindowMinimized:
##                    self.main_window.showNormal()
##            else:
##                    self.main_window.showMinimized() # in theory this should work but im doing something wrong.
            self.main_window.activateWindow()

if __name__=='__main__':
    app = QtGui.QApplication(sys.argv)
    main_window = HelloWindow()#should be HideableWindow()
    x = Systray(main_window)
    main_window.show()

    sys.exit(app.exec_())



##if __name__ == "__main__":
##    app = QtGui.QApplication([])
##
##    tray = SystemTrayIcon()
##    tray.show()
##    
##    #set the exec loop going
##    sys.exit(app.exec_())

##def createActions(self):
##
##        self.quitAction = QtGui.QAction(self.tr("&Quit"), self)
##        QtCore.QObject.connect(self.quitAction, QtCore.SIGNAL("triggered()"),
##                               QtGui.qApp, QtCore.SLOT("quit()"))
