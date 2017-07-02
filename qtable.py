import re
import operator
import os
import sys
from PyQt4.QtCore import * 
from PyQt4.QtGui import * 
from mangasql import SQLManager
import time
import subprocess
from qtrayico import Systray
from parsers import ParserFetch

def isfloat(string):
    try:
        float(string)
        return True
    except:
        return False
    
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class trayIcon(Systray):
    def __init__(self,window):
        super(trayIcon,self).__init__(window)
    def createActions(self):
        from PyQt4 import QtGui, QtCore
        self.actions=[]

        self.addAction= QtGui.QAction(self.tr("&Add Series"), self)
        self.connect(self.addAction, QtCore.SIGNAL("triggered()"),self.main_window.addevent)

        self.readerAction= QtGui.QAction(self.tr("&Open Reader"), self)
        self.connect(self.readerAction, QtCore.SIGNAL("triggered()"),self.main_window.openreader)
        
        self.quitAction = QtGui.QAction(self.tr("&Quit"), self)
        QtCore.QObject.connect(self.quitAction, QtCore.SIGNAL("triggered()"),
        QtGui.qApp, QtCore.SLOT("quit()"))
        
        self.actions.append(self.addAction)
        self.actions.append(self.readerAction)
        self.actions.append(self.quitAction)

MMCE=resource_path("!MMCE_Win32\MMCE_Win32.exe")
def main():
    from PyQt4 import QtGui
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = MyWindow()
    w.setWindowTitle('MT')
    w.setWindowIcon(QtGui.QIcon(resource_path("book.ico")))
    x=trayIcon(w)
    if '-q' not in sys.argv and '/q' not in sys.argv and '/silent' not in sys.argv:
        w.show()
    sys.exit(app.exec_()) 

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
        
class MyWindow(QMainWindow): 
    def __init__(self, *args): 
        QMainWindow.__init__(self, *args) 


        self.parserFetcher = ParserFetch()
        if self.parserFetcher.version_mismatch():
            msg = QMessageBox()
            msg.setWindowTitle('Version Out of Date')
            msg.setTextFormat(Qt.RichText)
            msg.setIcon(QMessageBox.Warning)
            msg.setText('Parsers will not longer be up-to-date until you update to a newer version of <a href="https://github.com/NeverDecaf/MangaTosho/releases/latest">MangaTosho</a>.')
            msg.exec_()

        # create table
        self.table = self.createTable() 

        self.setCentralWidget(self.table)
        menubar = self.menuBar()

        self.saddAction=QAction(self.tr("&Add Series"), self)
        self.connect(self.saddAction, SIGNAL("triggered()"),self.addevent)
        
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.saddAction)

        self.readerAction=QAction(self.tr("&Change Reader"), self)
        self.connect(self.readerAction, SIGNAL("triggered()"),self.changeReaderEvent)
        fileMenu.addAction(self.readerAction)

        self.credsAction= QAction(self.tr("&Add Credentials"), self)
        self.connect(self.credsAction, SIGNAL("triggered()"),self.addCredentials)
        fileMenu.addAction(self.credsAction)

        self.sinfoAction=QAction(self.tr("&Supported Sites"), self)
        self.connect(self.sinfoAction, SIGNAL("triggered()"),self.sinfoevent)

        self.tipsAction=QAction(self.tr("&Tips"), self)
        self.connect(self.tipsAction, SIGNAL("triggered()"),self.tips)

        self.legendAction=QAction(self.tr("&Color Legend"), self)
        self.connect(self.legendAction, SIGNAL("triggered()"),self.colorLegend)
        
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(self.sinfoAction)
        helpMenu.addAction(self.legendAction)
        # helpMenu.addAction(self.tipsAction) # all the tips are outdated so just remove the option for now.
##        helpMenu.addAction(self.MFConvertAction)
        
        self.quitAction = QAction(("&Quit"), self)
        QObject.connect(self.quitAction, SIGNAL("triggered()"),
            qApp, SLOT("quit()"))
        fileMenu.addAction(self.quitAction)

        

        self.geometry=None
        self.state=None

        self.removeAction=QAction("&Remove", self)
        self.right_menu = RightClickMenu(self.removeAction)
        
        self.updateAction=QAction("&Update", self)
        self.right_menu.addAction(self.updateAction)

        self.rollbackAction=QAction("&Rollback 1ch", self)
        self.right_menu.addAction(self.rollbackAction)

        self.completeAction=QAction("&Toggle Completion", self)
        self.right_menu.addAction(self.completeAction)
        
    def closeEvent(self,event): #override default close functionality to minimize to tray instead
         self.geometry = self.saveGeometry()
         self.state = self.saveState()
         self.hide()
         event.ignore()
         
    def showEvent(self,event):
        if not event.spontaneous():
            if self.geometry:
##                self.restoreGeometry(self.geometry)
##                self.restoreState(self.state)
##                self.showMinimized() # hide the window while we set the geometry
                QTimer.singleShot(0,self.restorePosition)
                
            
    def restorePosition(self):
        if self.state:
            self.restoreGeometry(self.geometry)
            self.restoreState(self.state) # restore state second to avoid flashing
##            QTimer.singleShot(0,self.show)
    def sinfoevent(self):
        QMessageBox.information(self, 'Supported Manga Sites',self.parserFetcher.get_valid_sites())

    def colorLegend(self):
        QMessageBox.information(self, 'Color Legend','- Green/Red - Error parsing/downloading.\
                        \n- Blue - Normal.\
                        \n- Gray - Series marked as complete.\
                        \n- Purple - Series is licensed and not available on this site.\
                        \nThe more saturation, the longer that state has persisted. Dark red/green series need attention; you may need to change sites or skip a chapter for these series.')
    def tips(self):
        QMessageBox.information(self, 'Some Useful Tips','- Try to avoid MangaPark, they commonly have multiple "Versions" of a series which means 2x filesize and/or chapters out of order or missing everywhere.\
                        \n- MangaFox has removed access to all their series from the US. Most urls can be directly converted by replacing mangafox with mangahere.\
                        \n- KissManga doesn\'t have a well defined chapter naming system, you should not use it unless you have to.\
                        \n- mangapanda.net seems to be an underground copy of mangapanda which means it may contain titles that aren\'t on the main site.\
                        \n- It is highly recommended that you use batoto if possible as they provide full quality scans and are scanlation group sanctioned.')

    def addevent(self):
        reply = QInputDialog.getText(self, self.tr("Enter URL"), self.tr("URL"))
        if reply[1]:
            if self.parserFetcher.match(reply[0])!=None:
                self.emit(SIGNAL("addSeries(QString)"),reply[0])
            else:
                msg="The URL you provided is not valid.\nSupported sites are as follows:\n"
                names=[]
                for parser in self.parserFetcher.get_valid_parsers():
                    names.append(parser.SITE_URL)
                msg+=', '.join(names)
                QMessageBox.information(self, 'Error adding URL',msg)
        #now your challenge is to signal the model and then
        # somehow add rows to the table.

    def openreader(self):
        if os.name=='nt':
            if self.tm.readercmd=='MMCE':
                subprocess.Popen(resource_path(MMCE))
            else:
                subprocess.Popen(self.tm.readercmd)
        else:
            subprocess.Popen(self.tm.readercmd, shell=True)

    def changeReaderEvent(self):
        reply = QInputDialog.getText(self, self.tr("Enter reader command"), self.tr("Command (Leave blank to use built-in MMCE)"),text=self.tr(self.tm.getReader()))
        if reply[1]:
            self.tm.setReader(reply[0])
        
    def addCredentials(self):
        d=SettingsDialog(self.tm.getCredentials(),self)
        d.exec_()
        if d.getValues():
            settings = d.getValues()
            self.tm.setCredentials(settings)
        d.deleteLater()

    def createTable(self):
        # create the view
        tv = QTableView()
        self.tv=tv
        # set the table model
        header = SQLManager.COLUMNS # ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime', 'Error', 'SuccessTime']
        tm = MyTableModel(header, self.parserFetcher, self)
        self.tm=tm
##        im=ColoredCell()
##        im.setSourceModel(tm)
        tv.setModel(tm)

##        tv.setContextMenu(self.right_menu)

        # set the minimum size
        tv.setMinimumSize(400, 300)

        # hide grid
        tv.setShowGrid(False)

        # set the font
        font = QFont("Courier New", 8)
        tv.setFont(font)

        # hide vertical header
        vh = tv.verticalHeader()
        vh.setDefaultSectionSize(20)
        vh.setVisible(False)

        # set horizontal header properties
        hh = tv.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setHighlightSections(False)

        # set column width to fit contents
        tv.resizeColumnsToContents()

        # set row height
##        tv.resizeRowsToContents()
##        nrows = len(self.tabledata)
##        for row in xrange(nrows):
##            tv.setRowHeight(row, 18)

        # enable sorting
        tv.setSortingEnabled(True)

        #select entire row
        tv.setSelectionBehavior(QAbstractItemView.SelectRows)

        #set double click action
        tv.doubleClicked.connect(tm.readSeries)

        tv.setContextMenuPolicy(Qt.CustomContextMenu)

        show = set(['Title','Read','Chapters','Unread','Site'])
        for col in set(header)-show:
            tv.setColumnHidden(header.index(col),True)

##        tv.setColumnHidden(header.index('Url'),True)
##        tv.setColumnHidden(header.index('Complete'),True)
##        tv.setColumnHidden(header.index('UpdateTime'),True)
##        tv.setColumnHidden(header.index('Error'),True)
##        tv.setColumnHidden(header.index('SuccessTime'),True)
        
        self.connect(self, SIGNAL("addSeries(QString)"),tm.addSeries)
        self.connect(self, SIGNAL("updateSeries(int)"),tm.updateSeries)
        self.connect(self, SIGNAL("removeSeries(QModelIndex,int)"),tm.removeSeries)
        self.connect(self, SIGNAL("rollbackSeries(QModelIndex)"),tm.rollbackSeries)
        self.connect(self, SIGNAL("completeSeries(QModelIndex)"),tm.completeSeries)
        self.connect(tv,SIGNAL("customContextMenuRequested(QPoint)"),self.alart)
        
        #initial sort
        tv.sortByColumn(header.index('Title'),Qt.AscendingOrder)
        tv.sortByColumn(header.index('Unread'),Qt.DescendingOrder)
        
        
        return tv
    
    def alart(self,pos):
        globalpos = self.tv.viewport().mapToGlobal(pos)
        localpos=self.right_menu.exec_(globalpos)
        if self.updateAction==localpos:
            self.emit(SIGNAL("updateSeries(int)"),self.tv.indexAt(pos).row())
        if self.removeAction==localpos:
            title = self.tm.getTitle(self.tv.indexAt(pos)) # this line does not obey the signal-slot methodology
            reply = QMessageBox.question(self, 'Careful!',
            "Are you sure want to remove the series: "+title+"?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
            if reply==QMessageBox.Yes:
                removeData = QMessageBox.question(self, 'Careful!',
                        "Do you also wish to remove all data associated\nwith the series (all downloaded chapters)?", QMessageBox.Yes | 
                        QMessageBox.No, QMessageBox.No)
                self.emit(SIGNAL("removeSeries(QModelIndex,int)"),self.tv.indexAt(pos),removeData)
        if self.rollbackAction==localpos:
            title = self.tm.getTitle(self.tv.indexAt(pos)) # this line does not obey the signal-slot methodology
            unread = self.tm.getUnread(self.tv.indexAt(pos))
            try:
                unread = int(unread)
            except:
                unread = 999
            if not unread==0:
                QMessageBox.warning(self, 'Sorry', "You can only roll back a series with unread = 0")
            else:
                reply = QMessageBox.question(self, 'Warning',
                "This will delete the latest chapter of "+title+" and decrement the last read chapter by 1.\nAre you sure you wish to do this?", QMessageBox.Yes | 
                QMessageBox.No, QMessageBox.No)
                if reply==QMessageBox.Yes:
                    self.emit(SIGNAL("rollbackSeries(QModelIndex)"),self.tv.indexAt(pos))
        if self.completeAction==localpos:
            title = self.tm.getTitle(self.tv.indexAt(pos)) # this line does not obey the signal-slot methodology
            complete = self.tm.getComplete(self.tv.indexAt(pos))
            if not complete:
                reply = QMessageBox.question(self, 'Mark Complete',
                "Are you sure want to mark the series: "+title+" as complete?\nDoing so means the series will no longer be updated in any way.\n(This action can be reversed.)", QMessageBox.Yes | 
                QMessageBox.No, QMessageBox.No)
                if reply==QMessageBox.Yes:
                    self.emit(SIGNAL("completeSeries(QModelIndex)"),self.tv.indexAt(pos))
            else:
                self.emit(SIGNAL("completeSeries(QModelIndex)"),self.tv.indexAt(pos))
        
class RightClickMenu(QMenu):
    def __init__(self, removeAction, parent=None):
        QMenu.__init__(self, "Edit", parent)
        
        self.addAction(removeAction)
        
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
class Worker(QThread):

    def __init__(self, data, sqlmanager, headerdata, lock, parent = None):
        QThread.__init__(self, parent)
        self.sql=sqlmanager
        self.data=data
        self.headerdata=headerdata
        self.lock=lock
    def run(self):
        self.updateAll()
    def updateAll(self):
            for datum in self.data:
                try:
                    self.lock.lock()
                    complete = datum[self.headerdata.index('Complete')]
                    if complete:
                        continue
                    err,data = self.sql.updateSeries(datum)
        ##            print 'error code',err
                    if err>0:
                        self.emit(SIGNAL("errorRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),datum,err,data)
                    elif len(data):
                        self.emit(SIGNAL("updateRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),datum,data,err)
                    else:
                        self.emit(SIGNAL("errorRow(PyQt_PyObject,PyQt_PyObject)"),datum,0)
##                    self.lock.unlock()
                except:
                    fh=open('CRITICAL ERROR SEARCH QTABLE FOR THIS LINE','wb')
                    fh.close()
                finally:
                    self.lock.unlock()

class MyTableModel(QAbstractTableModel): 
    def __init__(self, headerdata, parserFetch, parent=None, *args): 
        """ datain: a list of lists
            headerdata: a list of strings
        """
        QAbstractTableModel.__init__(self, parent, *args)

        

        self.myparent = parent
        self.sql=SQLManager(parserFetch)
        # create lock for threads
        self.lock = QMutex()
        
        self.arraydata = self.sql.getSeries()
        self.headerdata = headerdata
        
        self.current_col = self.headerdata.index("Read")
        self.total_col = self.headerdata.index("Chapters")
        self.title_col = self.headerdata.index("Title")

##        self.updateTimer = QTimer()

        self.sort_order=Qt.AscendingOrder
        self.sort_column=self.headerdata.index("Unread")

        self.second_sort_order=Qt.DescendingOrder
        self.second_sort_column=self.headerdata.index("Title")
        
        self.setReader(self.sql.getReader())
        
        self.updateAll()
    def setCredentials(self,creds):
        self.sql.setCredentials(creds)

    def getCredentials(self):
        return self.sql.getCredentials()
    
    def setReader(self,new):
        self.readercmd=str(new)
        if not len(self.readercmd):
            self.readercmd='MMCE'
##            self.readercmd=resource_path(MMCE) # set to default reader if none given
        self.sql.setReader(self.readercmd)

    def getReader(self):
        return self.readercmd

    def addSeries(self,url):
        data=self.sql.addSeries(str(url))
        if data == None:
            QMessageBox.information(self.myparent, 'Series Add Failed','The URL you provided is not valid. Make sure you are linking the series\' "home page" and not a specific chapter or page')
            #not valid url
        elif data == False:
            #series already exists.
            QMessageBox.information(self.myparent, 'Series Add Failed','You are already reading this series.')
        else:
            old=self.rowCount(None)
            self.beginInsertRows(QModelIndex(),old,old)
            self.arraydata.append(data)
            self.endInsertRows()
            self.resort()
            QMessageBox.information(self.myparent, 'Series Added','New series was added successfully.')
            self.updateSeries(self.arraydata.index(data))
            

    def updateSeries(self,index):
        #Just do the same as updateAll except with an array of size 1.
        #create the business thread
        self.thread = Worker([self.arraydata[index]],self.sql,self.headerdata,self.lock)
        
        self.connect(self.thread, SIGNAL("updateRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),self.updateRow)
        self.connect(self.thread, SIGNAL("errorRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),self.errorRow)
        #no need for a finished() signal as we only want to run this once.
##        self.connect(self.thread, SIGNAL("finished()"),self.waitThenUpdate)
        
        self.thread.start()

    def waitThenUpdate(self):
        QTimer.singleShot(60*60*1000,self.updateAll)#update hourly. may want to increase or scale based on # of series
        
    def updateAll(self):
        #create the business thread
        self.thread = Worker(self.arraydata,self.sql,self.headerdata,self.lock)
        
        self.connect(self.thread, SIGNAL("updateRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),self.updateRow)
        self.connect(self.thread, SIGNAL("errorRow(PyQt_PyObject,PyQt_PyObject,PyQt_PyObject)"),self.errorRow)
        self.connect(self.thread, SIGNAL("finished()"),self.waitThenUpdate)
        
        self.thread.start()
        #use QTimer to call this again after a break

    def updateRow(self,olddata,newdata,errcode):
        erridx = self.headerdata.index('Error')
        row=self.arraydata.index(olddata)

        if errcode==0:
            newdata[self.headerdata.index('UpdateTime')]=time.time()
        newdata[self.headerdata.index('SuccessTime')]=time.time()
        newdata[erridx]=0
        
        for i in range(len(self.arraydata[row])):
            self.arraydata[row][i] = newdata[i]
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), idx,idx2)
        self.resort()
        self.sql.changeSeries(newdata)

    def getTitle(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Title')]

    def getComplete(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Complete')]

    def getUnread(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Unread')]

    def errorRow(self,data,errcode,errmsg=['']):
        #errmsg is an array of messages (len 1 though)
        row=self.arraydata.index(data)
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        self.arraydata[row][self.headerdata.index('Error')] = errcode
        self.arraydata[row][self.headerdata.index('Error Message')] = errmsg[0]
        if errcode<1:
            self.arraydata[row][self.headerdata.index('SuccessTime')]=time.time()
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), idx,idx2)
        self.sql.changeSeries(self.arraydata[row])

    def setData(self, index, value, role=Qt.EditRole, user=False):
        if not user and not value.toDouble()[1]: # enforces float values for chapter num
            return False
        self.arraydata[index.row()][index.column()] = str(value.toString())
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index,index)
        self.sql.changeSeries(self.arraydata[index.row()])
        self.resort()
        return True
    
    def removeSeries(self,index,removedata):
        self.beginRemoveRows(QModelIndex(),index.row(),index.row())
        title=self.arraydata[index.row()][self.headerdata.index('Title')]
        url=self.arraydata[index.row()][self.headerdata.index('Url')]
        del self.arraydata[index.row()]
        self.endRemoveRows()
        if removedata==QMessageBox.Yes:
            self.sql.removeSeries(url,title)
        else:
            self.sql.removeSeries(url)
            
    def rollbackSeries(self,index):
        row=index.row()
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        url=self.arraydata[index.row()][self.headerdata.index('Url')]
        try:
            title=self.arraydata[index.row()][self.headerdata.index('Title')]
            last_read = int(self.arraydata[index.row()][self.headerdata.index('Read')])
            self.arraydata[index.row()][self.headerdata.index('Read')] = last_read-1
            self.sql.rollbackSeries(url,last_read,title)
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), idx,idx2)
        except:
            pass
        
    def completeSeries(self,index):
        row=index.row()
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        url=self.arraydata[index.row()][self.headerdata.index('Url')]
        try:
            completion_status = int(self.arraydata[index.row()][self.headerdata.index('Complete')])
            self.arraydata[index.row()][self.headerdata.index('Complete')] = completion_status ^ 1
            self.sql.completeSeries(url,completion_status^1)
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), idx,idx2)
        except:
            pass
        
    def rowCount(self, parent):
        return len(self.arraydata)

    def readSeries(self, index):
        if index.column()==self.current_col:
            return
        last=self.arraydata[index.row()][self.headerdata.index('Read')]#last read chapter
        self.arraydata[index.row()][self.headerdata.index('Unread')]=0
        self.arraydata[index.row()][self.current_col] = self.arraydata[index.row()][self.total_col]
        idx = self.createIndex(index.row(),0)
        idx2 = self.createIndex(index.row(),len(self.headerdata)-1)
        self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'),idx,idx2)
        self.sql.changeSeries(self.arraydata[index.row()])

        sdir=SQLManager.cleanName(self.arraydata[index.row()][self.headerdata.index('Title')])#name of series
        chapters =sorted(os.listdir(sdir))

        if not len(chapters):
            self.resort()
            return
        
        toopen = os.path.join(sdir,chapters[0])

        last = SQLManager.formatName(last) # convert to proper form
        
        if os.path.exists(os.path.join(sdir,last)):
            try:
                toopen = os.path.join(sdir,chapters[chapters.index(last)+1])
            except:
                toopen = os.path.join(sdir,chapters[-1])
        elif is_number(last): # didn't find last anywhere but we'll try to fit it in
            nextIndex = SQLManager.fitnumber(last,[x for x in chapters if isfloat(x)])
            try:
                toopen = os.path.join(sdir,chapters[nextIndex])
            except:
                toopen = os.path.join(sdir,chapters[-1])
        if os.name=='nt':
            if self.readercmd=='MMCE':
                subprocess.Popen(resource_path(MMCE)+' "'+os.path.realpath(toopen)+'"')
            else:
                subprocess.Popen(self.readercmd+' "'+os.path.realpath(toopen)+'"')
        else:
            subprocess.Popen(self.readercmd+' "'+os.path.realpath(toopen)+'"', shell=True)
        self.resort()
        
    def columnCount(self, parent):
##        try:
##            return len(self.arraydata[0])
##        else:
        return len(self.headerdata)

    def flags(self,index):
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == self.current_col:
            flags|=Qt.ItemIsEditable
        return flags
 
    def data(self, index, role): 
        if not index.isValid(): 
            return QVariant()
        elif role==Qt.BackgroundRole:
            row = index.row()
            error=self.arraydata[row][self.headerdata.index('Error')]
            complete=self.arraydata[row][self.headerdata.index('Complete')]
            if complete:
                return QBrush(QColor(127,127,127))
            mod=min(200,(time.time()-self.arraydata[row][self.headerdata.index('SuccessTime')])/34560 + 20)#divide into days
            if error!=0:
                # 1 = parser error, 2= imgfetch error (dunno where i got this idea but it seems to actually just be a
                # generic Exception that wasnt caught by anything in sql.updateSeries), 3=licensed

                # after some observation, error 2 seems to be caused by a severely misconfigured parser
                if error==1:
##                    return QBrush(QColor(255,220,220))
                    return QBrush(QColor(255,255-mod,255-mod)) # shades of red
                if error==2:
##                    return QBrush(QColor(255,220,220))
                    return QBrush(QColor(255-mod,255,255-mod)) # shades of green
                if error==3:
##                    return QBrush(QColor(255,100,100))
                    return QBrush(QColor(150,50,255)) # purple
            # for last updated, let's scale it a little longer since some series take a while to update
            mod=min(180,(time.time()-self.arraydata[row][self.headerdata.index('UpdateTime')])/(34560*2))#divide into days,  added *2 to give it way more time.
            color = QColor(255-mod,255-mod,255) # shades of blue
            return QBrush(color)
        elif role == Qt.ToolTipRole:
            row = index.row()
            error_msg=self.arraydata[row][self.headerdata.index('Error Message')]
            if not error_msg:
                return 'Updated %i days ago'%((time.time()-self.arraydata[row][self.headerdata.index('UpdateTime')])//86400)
            else:
                return error_msg # this could be None but it won't break.
        
        elif role != Qt.DisplayRole: 
            return QVariant()
        return QVariant(self.arraydata[index.row()][index.column()])

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.headerdata[col])
        return QVariant()

    def resort(self):
        self.sortAction()
##        self.sort(self.sort_column,self.sort_order)
        
    def sort(self, Ncol, order):
        """Sort table by given column number.
        """
##        self.second_sort_order=self.sort_order
##        self.second_sort_column=self.sort_column # update the secondary sort
        self.sort_column=Ncol
        self.sort_order=order
        self.sortAction()
        
    def sortAction(self):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
##        self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.second_sort_column))
##        if self.second_sort_order == Qt.DescendingOrder:
##            self.arraydata.reverse()
##        self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.sort_column,self.title_col))
        if self.sort_column == self.headerdata.index('Title'):
            self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.sort_column))
        elif self.sort_column == self.headerdata.index('Site'):
            self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.sort_column,self.title_col))
        else:
            self.arraydata = sorted(self.arraydata, key=lambda x: (SQLManager.formatName(x[self.sort_column]),x[self.title_col]))
            
##        self.arraydata = sorted(self.arraydata, key=lambda x: (float(x[self.sort_column]),self.title_col))
        if self.sort_order == Qt.DescendingOrder:
            self.arraydata.reverse()
        self.emit(SIGNAL("layoutChanged()"))


class inputdialogdemo(QWidget):
   def __init__(self, parent = None):
      super(inputdialogdemo, self).__init__(parent)
		
      layout = QFormLayout()
      self.btn = QPushButton("Choose from list")
      self.btn.clicked.connect(self.getItem)
		
      self.le = QLineEdit()
      layout.addRow(self.btn,self.le)
      self.btn1 = QPushButton("get name")
      self.btn1.clicked.connect(self.gettext)
		
      self.le1 = QLineEdit()
      layout.addRow(self.btn1,self.le1)
      self.btn2 = QPushButton("Enter an integer")
      self.btn2.clicked.connect(self.getint)
		
      self.le2 = QLineEdit()
      layout.addRow(self.btn2,self.le2)
      self.setLayout(layout)
      self.setWindowTitle("Input Dialog demo")
		
   def getItem(self):
      items = ("C", "C++", "Java", "Python")
		
      item, ok = QInputDialog.getItem(self, "select input dialog", 
         "list of languages", items, 0, False)
			
      if ok and item:
         self.le.setText(item)
			
   def gettext(self):
      text, ok = QInputDialog.getText(self, 'Text Input Dialog', 'Enter your name:')
		
      if ok:
         self.le1.setText(str(text))
			
   def getint(self):
      num,ok = QInputDialog.getInt(self,"integer input dualog","enter a number")
		
      if ok:
         self.le2.setText(str(num))
         
class SettingsDialog(QDialog):
    def __init__(self,initialSettings, parent=None):
        from PyQt4.QtCore import Qt
        super(SettingsDialog, self).__init__(parent)
        self.result=None
        self.setWindowTitle(self.tr("Credentials"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

        mainLayout = QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QFormLayout()
        confirmLayout = QGridLayout()

        top=QWidget()
        bottom=QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)

        optionsLayout.addRow("<b>Add credentials to allow these sites:</b>",None)
        self.options = {}

        for site in initialSettings:
            self.options[site] = [QLineEdit(),QLineEdit()]
            optionsLayout.addRow(site + " Username",self.options[site][0])
            optionsLayout.addRow(site + " Password",self.options[site][1])
            self.options[site][1].setEchoMode(QLineEdit.Password)
            
        self.saveButton=QPushButton('Save')
        self.cancelButton=QPushButton('Cancel')
        
        confirmLayout.addWidget(self.saveButton,0,0)
        confirmLayout.addWidget(self.cancelButton,0,1)
        
        self.connect(self.cancelButton,SIGNAL("released()"),self.close)
        self.connect(self.saveButton,SIGNAL("released()"),self.saveValues)

        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        for key in initialSettings:
            try:
                self.options[key][0].setText(initialSettings[key][0])
                self.options[key][1].setText(initialSettings[key][1])
            except:
                'is blank'
                        
    def getValues(self):
        return self.result
    
    def saveValues(self):
        self.result={}
        for key in self.options:
            self.result[key] = (str(self.options[key][0].text()),str(self.options[key][1].text()))
        self.close()
        

        
if __name__ == "__main__":
    # chdir to the correct directory to ensure configs, etc. are loaded correctly.
    import os,sys
    try:
        sys._MEIPASS
        os.chdir(os.path.dirname(sys.argv[0]))
    except:
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
    main()
