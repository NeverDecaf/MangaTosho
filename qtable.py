import re
import operator
import os
import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from mangasql import SQLManager
import parsers
import time
import subprocess
import random
from qtrayico import Systray
from functools import partial
import collections,queue
from constants import *

def isfloat(string):
    try:
        float(string)
        return True
    except:
        return False

class trayIcon(Systray):
    def __init__(self,window):
        super(trayIcon,self).__init__(window)
    def createActions(self):
        from PyQt5 import QtCore, QtGui, QtWidgets
        self.actions=[]

        self.addAction= QtWidgets.QAction(self.tr("&Add Series"), self)
        self.addAction.triggered.connect(self.main_window.addevent)

        self.readerAction= QtWidgets.QAction(self.tr("&Open Reader"), self)
        self.readerAction.triggered.connect(self.main_window.openreader)
        
        self.quitAction = QtWidgets.QAction(self.tr("&Quit"), self)
        self.quitAction.triggered.connect(QtWidgets.QApplication.quit)
        
        self.actions.append(self.addAction)
        self.actions.append(self.readerAction)
        self.actions.append(self.quitAction)

def main():
    from PyQt5 import QtGui

    app = QApplication(sys.argv)
##    app.setStyle('Plastique')
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
    addSeries = pyqtSignal('QString')
    updateSeries = pyqtSignal(int)
    removeSeries = pyqtSignal(QModelIndex, int)
    rollbackSeries = pyqtSignal(QModelIndex)
    exploreSeries = pyqtSignal(QModelIndex)
    completeSeries = pyqtSignal(QModelIndex)
    editSeriesUrl = pyqtSignal(QModelIndex,'QString')

    def __init__(self, *args): 
        QMainWindow.__init__(self, *args) 


        self.parserFetcher = parsers.ParserFetch()
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
        self.saddAction.triggered.connect(self.addevent)
        
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.saddAction)

        self.readerAction=QAction(self.tr("&Change Reader"), self)
        self.readerAction.triggered.connect(self.changeReaderEvent)
        fileMenu.addAction(self.readerAction)

        self.credsAction= QAction(self.tr("&Add Credentials"), self)
        self.credsAction.triggered.connect(self.addCredentials)
        fileMenu.addAction(self.credsAction)


        self.historyMenu = menubar.addMenu('&History')
        

        self.sinfoAction=QAction(self.tr("&Supported Sites"), self)
        self.sinfoAction.triggered.connect(self.sinfoevent)

        self.tipsAction=QAction(self.tr("&Tips"), self)
        self.tipsAction.triggered.connect(self.tips)

        self.legendAction=QAction(self.tr("&Color Legend"), self)
        self.legendAction.triggered.connect(self.colorLegend)

        
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(self.sinfoAction)
        helpMenu.addAction(self.legendAction)
        # helpMenu.addAction(self.tipsAction) # all the tips are outdated so just remove the option for now.
##        helpMenu.addAction(self.MFConvertAction)
        
        self.quitAction = QAction(("&Quit"), self)
        self.quitAction.triggered.connect(QApplication.quit)
        fileMenu.addAction(self.quitAction)


        


        self.geometry=None
        self.state=None

        self.removeAction=QAction("&Remove", self)
        self.right_menu = RightClickMenu(self.removeAction)

        self.explorerAction=QAction("&Show in Explorer", self)
        if os.name=='nt':
            self.right_menu.addAction(self.explorerAction)
        
        self.updateAction=QAction("&Update", self)
        self.right_menu.addAction(self.updateAction)

        self.urlAction=QAction("&Edit URL", self)
        self.right_menu.addAction(self.urlAction)
        
        self.rollbackAction=QAction("&Rollback 1ch", self)
        self.right_menu.addAction(self.rollbackAction)

        self.completeAction=QAction("&Toggle Completion", self)
        self.right_menu.addAction(self.completeAction)

        self.setHistory(self.tm.getHistory())
        
    def setHistory(self,data):
        self.historyMenu.clear()
        for title,num,path in data:
            tmpaction = QAction(self.tr("&{0} {1:g}".format(title,float(num))),self)
            self.historyMenu.addAction(tmpaction)
            tmpaction.triggered.connect(partial(self.tm.readpath,path))

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
                        \n- Yellow - Site no longer supported.\
                        \nThe more saturation, the longer that state has persisted. Dark red/green series need attention; you may need to change sites or skip a chapter for these series.\nMouse over an errored series for details.')
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
                self.addSeries.emit(reply[0])
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
        header = TABLE_COLUMNS # ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime', 'Error', 'SuccessTime']
        tm = MyTableModel(header, self.parserFetcher, self)
        self.tm=tm
##        im=ColoredCell()
##        im.setSourceModel(tm)
        tv.setModel(tm)

##        tv.setContextMenu(self.right_menu)

        # set the minimum size
        tv.setMinimumSize(600, 400)

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

        show = set(['Title','Read','Chapters','Unread','Site','Rating'])
        for col in set(header)-show:
            tv.setColumnHidden(header.index(col),True)

##        tv.setColumnHidden(header.index('Url'),True)
##        tv.setColumnHidden(header.index('Complete'),True)
##        tv.setColumnHidden(header.index('UpdateTime'),True)
##        tv.setColumnHidden(header.index('Error'),True)
##        tv.setColumnHidden(header.index('SuccessTime'),True)
        
        self.addSeries['QString'].connect(tm.addSeries)
        self.updateSeries[int].connect(tm.updateSeries)
        self.removeSeries[QModelIndex, int].connect(tm.removeSeries)
        self.rollbackSeries[QModelIndex].connect(tm.rollbackSeries)
        self.exploreSeries[QModelIndex].connect(tm.openInFileExplorer)
        self.completeSeries[QModelIndex].connect(tm.completeSeries)
        self.editSeriesUrl[QModelIndex,str].connect(tm.editSeriesUrl)
        tv.customContextMenuRequested[QPoint].connect(self.alart)
        
        #initial sort
        tv.sortByColumn(header.index('Title'),Qt.AscendingOrder)
        tv.sortByColumn(header.index('Unread'),Qt.DescendingOrder)
        
        
        return tv
    
    def alart(self,pos):
        globalpos = self.tv.viewport().mapToGlobal(pos)
        localpos=self.right_menu.exec_(globalpos)
        if self.updateAction==localpos:
            self.updateSeries.emit(self.tv.indexAt(pos).row())
        if self.removeAction==localpos:
            title = self.tm.getTitle(self.tv.indexAt(pos)) # this line does not obey the signal-slot methodology
            reply = QMessageBox.question(self, 'Careful!',
            "Are you sure want to remove the series: "+title+"?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
            if reply==QMessageBox.Yes:
                removeData = QMessageBox.question(self, 'Careful!',
                        "Do you also wish to remove all data associated\nwith the series (all downloaded chapters)?", QMessageBox.Yes | 
                        QMessageBox.No, QMessageBox.No)
                self.removeSeries.emit(self.tv.indexAt(pos), removeData)
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
                    self.rollbackSeries.emit(self.tv.indexAt(pos))
        if self.completeAction==localpos:
            title = self.tm.getTitle(self.tv.indexAt(pos)) # this line does not obey the signal-slot methodology
            complete = self.tm.getComplete(self.tv.indexAt(pos))
            if not complete:
                reply = QMessageBox.question(self, 'Mark Complete',
                "Are you sure want to mark the series: "+title+" as complete?\nDoing so means the series will no longer be updated in any way.\n(This action can be reversed.)", QMessageBox.Yes | 
                QMessageBox.No, QMessageBox.No)
                if reply==QMessageBox.Yes:
                    self.completeSeries.emit(self.tv.indexAt(pos))
            else:
                self.completeSeries.emit(self.tv.indexAt(pos))
        if self.urlAction==localpos:
            url = self.tm.getUrl(self.tv.indexAt(pos))
            site = self.tm.getSite(self.tv.indexAt(pos))
            reply = QInputDialog.getText(self, self.tr("Enter URL"), self.tr("URL"), text=url)
            if reply[1]:
                match = self.parserFetcher.match(reply[0])
                if match and match.ABBR==site and reply[0] != url:
                    self.editSeriesUrl.emit(self.tv.indexAt(pos),reply[0])
                elif reply[0] == url:
                    QMessageBox.information(self, 'Error changing URL', 'New URL is the same as existing one.')
                else:
                    QMessageBox.information(self, 'Error changing URL', 'New URL is not valid for this site (%s)'%site)
        if self.explorerAction==localpos:
            self.exploreSeries.emit(self.tv.indexAt(pos))
        
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

#https://github.com/python/cpython/blob/3.6/Lib/queue.py
class UniqueDeque(queue.Queue):
    'Double-ended queue which allows only unique items to be inserted'
    def __init__(self, maxsize=0, key=lambda x:str(x)):
        'key can be passed and is used when comparing elements (for appending, not sorting)'
        super().__init__(maxsize)
        self.keyfunc = key
        
    def putLeft(self, item, block=True, timeout=None):
        with self.not_full:
            if self.maxsize > 0:
                if not block:
                    if self._qsize() >= self.maxsize:
                        raise queue.Full
                elif timeout is None:
                    while self._qsize() >= self.maxsize:
                        self.not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                else:
                    endtime = time() + timeout
                    while self._qsize() >= self.maxsize:
                        remaining = endtime - time()
                        if remaining <= 0.0:
                            raise queue.Full
                        self.not_full.wait(remaining)
            self._putLeft(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()
    # Initialize the queue representation
    def _init(self, maxsize):
        self.queue = collections.deque()
        self.set = set()

    def _qsize(self):
        return len(self.queue)

    # Put a new item in the queue
    def _put(self, item):
        if self.keyfunc(item) not in self.set:
            self.queue.append(item)
            self.set.add(self.keyfunc(item))

    def _putLeft(self, item):
        if self.keyfunc(item) not in self.set:
            self.queue.appendleft(item)
            self.set.add(self.keyfunc(item))

    # Get an item from the queue
    def _get(self):
        item = self.queue.popleft()
        self.set.discard(self.keyfunc(item))
        return item
        
class UpdateThread(QThread):
    errorRow = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject')
    updateRow = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject')

    def __init__(self, sqlmanager, headerdata, site_locks, series_locks, update_queue, parent = None):
        QThread.__init__(self, parent)
        self.sql=sqlmanager
        self.headerdata=headerdata
        self.site_locks=site_locks
        self.series_locks=series_locks
        self.queue = update_queue

    def updateSeries(self,datum):
        sitelock_aquired = False
        try:
            site_lock = self.site_locks.setdefault(datum[self.headerdata.index('Site')],QSemaphore(MAX_SIMULTANEOUS_UPDATES_PER_SITE))
            if not site_lock.tryAcquire():
                self.queue.put(datum) # re-queue the data
                time.sleep(10) # lazy solution
                return
            sitelock_aquired = True
            lockset = self.series_locks.setdefault(datum[self.headerdata.index('Url')],[QMutex(),0])
            thislock = lockset[0]
            thislock.lock()
            try:
                complete = datum[self.headerdata.index('Complete')]
                if complete:
                    return
                err,data = self.sql.updateSeries(datum) # this method does not access the sqlite db and therefore can function in a separate thread.
                if err>0:
                    self.errorRow.emit(datum, err, data)
                elif len(data):
                    if lockset[1]:
                        # means a change occured mid-update, in this case we don't want to overwrite the data.
                        lockset[1]=0
                    else:
                        self.updateRow.emit(datum, data, err)
                else:
                    self.errorRow.emit(datum, 0, [''])
                time.sleep(random.uniform(*parsers.CHAPTER_DELAY)) # sleep between series (same delay as between chapters)
            finally:
                thislock.unlock()
        except Exception as e:
            fh=open('CRITICAL ERROR SEARCH QTABLE FOR THIS LINE','w')
            fh.write('%r'%e)
            fh.close()
            raise
        finally:
            if sitelock_aquired:
                site_lock.release()
            
    def run(self):
        while True:
            data = self.queue.get()
            if data is None:
                break
            self.updateSeries(data)

    def stop(self):
        self.queue.putLeft(None)
        self.wait()

class MyTableModel(QAbstractTableModel): 
    dataChanged = pyqtSignal(QModelIndex, QModelIndex)
    layoutAboutToBeChanged = pyqtSignal()
    layoutChanged = pyqtSignal()
    

    def __init__(self, headerdata, parserFetch, parent=None, *args): 
        """ datain: a list of lists
            headerdata: a list of strings
        """
        QAbstractTableModel.__init__(self, parent, *args)

        

        self.myparent = parent
        self.sql=SQLManager(parserFetch)
        # create lock for threads
        self.site_locks = {}
        self.series_locks = {}
        
        self.arraydata = self.sql.getSeries()
        self.headerdata = headerdata
        
        self.current_col = self.headerdata.index("Read")
        self.total_col = self.headerdata.index("Chapters")
        self.title_col = self.headerdata.index("Title")
        self.editable_cols = (self.current_col, self.headerdata.index("Rating"))

        self.sort_order=Qt.AscendingOrder
        self.sort_column=self.headerdata.index("Unread")

        self.second_sort_order=Qt.DescendingOrder
        self.second_sort_column=self.headerdata.index("Title")
        
        self.setReader(self.sql.getReader())

        self.updateThreads=[]
        self.updateQueue = UniqueDeque(key = lambda x: x[self.headerdata.index("Url")])
        
        for i in range(MAX_UPDATE_THREADS):
            thread = UpdateThread(self.sql,self.headerdata,self.site_locks,self.series_locks,self.updateQueue)
            thread.updateRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.updateRow)
            thread.errorRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.errorRow)
            thread.start()
            self.updateThreads.append(thread)

        timer = QTimer(self)
        timer.timeout.connect(self.updateAll)
        timer.start(SERIES_UPDATE_FREQ)
        self.updateAll()
        
    def setCredentials(self,creds):
        self.sql.setCredentials(creds)

    def getCredentials(self):
        return self.sql.getCredentials()

    def getHistory(self):
        return self.sql.getHistory()
    
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
            QMessageBox.information(self.myparent, 'Series Add Failed','The URL you provided is not valid. Make sure you are linking the series page/chapter list and not a specific chapter or page')
            #not valid url
        elif data == False:
            #series already exists.
            QMessageBox.information(self.myparent, 'Series Add Failed','You are already reading this series.')
        elif data == -1:
            #other error
            QMessageBox.information(self.myparent, 'Series Add Failed','Error adding this series. Check to make sure your URL is valid. (This may be a bug)')
        else:
            old=self.rowCount(None)
            self.beginInsertRows(QModelIndex(),old,old)
            self.arraydata.append(data)
            self.endInsertRows()
            self.resort()
            QMessageBox.information(self.myparent, 'Series Added','New series was added successfully.')
            self.updateSeries(self.arraydata.index(data))

    def updateSeries(self,indexrow):
        self.series_locks.setdefault(self.arraydata[indexrow][self.headerdata.index('Url')],[QMutex(),0])
        self.updateQueue.putLeft(self.arraydata[indexrow])

    def updateAll(self):
        for d in self.sql.getToUpdate():
            self.series_locks.setdefault(d[self.headerdata.index('Url')],[QMutex(),0])
            self.updateQueue.put(d)

    def updateRow(self,olddata,newdata,errcode):
        try:
            row=self.arraydata.index(olddata)
        except ValueError:
            return
        if errcode==0:
            newdata[self.headerdata.index('UpdateTime')]=time.time()
        newdata[self.headerdata.index('SuccessTime')]=time.time()
        newdata[self.headerdata.index('Error')]=0
        newdata[self.headerdata.index('Error Message')] = None
        newdata[self.headerdata.index('LastUpdateAttempt')]=time.time()

        
        for i in range(len(self.arraydata[row])):
            self.arraydata[row][i] = newdata[i]
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        self.dataChanged.emit(idx, idx2)
        self.resort()
        self.sql.changeSeries(newdata)

    def getTitle(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Title')]

    def getComplete(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Complete')]
    
    def getSite(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Site')]
    
    def getUnread(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Unread')]
    
    def getUrl(self,index):
        return self.arraydata[index.row()][self.headerdata.index('Url')]
    
    def errorRow(self,data,errcode,errmsg):
        #errmsg is an array of messages (len 1 though)
        try:
            row=self.arraydata.index(data)
        except ValueError:
            return
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        self.arraydata[row][self.headerdata.index('Error')] = errcode
        self.arraydata[row][self.headerdata.index('Error Message')] = errmsg[0]
        if errcode<1:
            self.arraydata[row][self.headerdata.index('SuccessTime')]=time.time()
        self.arraydata[row][self.headerdata.index('LastUpdateAttempt')]=time.time()
        self.dataChanged.emit(idx, idx2)
        self.sql.changeSeries(self.arraydata[row])

    def setData(self, index, value, role=Qt.EditRole, user=False):
        if not user and not value.replace('.','',1).isdigit(): # enforces float values for chapter num
            return False
        locked = 0
        if self.arraydata[index.row()][self.headerdata.index('Url')] in self.series_locks:
            lockset = self.series_locks[self.arraydata[index.row()][self.headerdata.index('Url')]]
            lock = lockset[0]
            if lock.tryLock():
                locked=lock
                lockset[1] = 0
            else:
                lockset[1] = 1 # data changed but lock could not be aquired, meaning update in progress
        try:
            self.arraydata[index.row()][index.column()] = str(value)
            self.dataChanged.emit(index, index)
            self.sql.changeSeries(self.arraydata[index.row()])
            self.resort()
        finally:
            if locked:
                lock.unlock()
        return True
    
    def openInFileExplorer(self,index):
        toopen=os.path.abspath(SQLManager.cleanName(self.arraydata[index.row()][self.headerdata.index('Title')]))
        if os.path.exists(toopen):
            subprocess.Popen('explorer.exe "{}"'.format(os.path.abspath(toopen)))
     
    def removeSeries(self,index,removedata):
        self.beginRemoveRows(QModelIndex(),index.row(),index.row())
        self.series_locks.setdefault(self.arraydata[index.row()][self.headerdata.index('Url')],[QMutex(),0])[1]=0
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
            self.dataChanged.emit(idx, idx2)
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
            self.dataChanged.emit(idx, idx2)
        except:
            pass

    def editSeriesUrl(self,index,newurl):
        row=index.row()
        idx = self.createIndex(row,0)
        idx2 = self.createIndex(row,len(self.headerdata)-1)
        url=self.arraydata[index.row()][self.headerdata.index('Url')]
        try:
            self.arraydata[index.row()][self.headerdata.index('Url')] = newurl
            self.sql.updateSeriesUrl(url,newurl)
            self.dataChanged.emit(idx, idx2)
        except:
            pass
        
    def rowCount(self, parent):
        return len(self.arraydata)

    def readSeries(self, index):
        if index.column() in self.editable_cols:
            return

        locked = 0
        if self.arraydata[index.row()][self.headerdata.index('Url')] in self.series_locks:
            lockset = self.series_locks[self.arraydata[index.row()][self.headerdata.index('Url')]]
            lock = lockset[0]
            if lock.tryLock():
                locked=lock
                lockset[1] = 0
            else:
                lockset[1] = 1 # data changed but lock could not be aquired, meaning update in progress
        try:
            last=self.arraydata[index.row()][self.headerdata.index('Read')]#last read chapter

            sdir=SQLManager.cleanName(self.arraydata[index.row()][self.headerdata.index('Title')])#name of series
            if os.path.exists(sdir):
                chapters = sorted(os.listdir(sdir))
            else:
                chapters=[]

            if not len(chapters):
    ##            self.resort()
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
            if os.path.exists(os.path.realpath(toopen)):
                self.readpath(toopen)
                
                self.arraydata[index.row()][self.headerdata.index('Unread')]=0
                self.arraydata[index.row()][self.current_col] = self.arraydata[index.row()][self.total_col]
                idx = self.createIndex(index.row(),0)
                idx2 = self.createIndex(index.row(),len(self.headerdata)-1)
                self.dataChanged.emit(idx, idx2)
                self.sql.changeSeries(self.arraydata[index.row()])
                history_last_read = os.path.basename(toopen)
                self.sql.addHistory(self.arraydata[index.row()], history_last_read, toopen)
                self.resort()
                self.myparent.setHistory(self.sql.getHistory())
##                self.myparent.addHistory("{0} {1:g}".format(self.arraydata[index.row()][self.headerdata.index('Title')],float(history_last_read)),toopen)
        finally:
            if locked:
                locked.unlock()
##        self.resort()

    def readpath(self, path):
        if os.name=='nt':
            if self.readercmd=='MMCE':
                subprocess.Popen(resource_path(MMCE)+' "'+os.path.realpath(path)+'"')
            else:
                subprocess.Popen(self.readercmd+' "'+os.path.realpath(path)+'"')
        else:
            subprocess.Popen(self.readercmd+' "'+os.path.realpath(path)+'"', shell=True)
        
    def columnCount(self, parent):
##        try:
##            return len(self.arraydata[0])
##        else:
        return len(self.headerdata)

    def flags(self,index):
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() in self.editable_cols:
            flags|=Qt.ItemIsEditable
        return flags
 
    def data(self, index, role):
        if role==Qt.DisplayRole and index.column() == self.headerdata.index('Rating'):
            stars = min(10,int(self.arraydata[index.row()][self.headerdata.index('Rating')]))
            if stars<0:
                return ""
            return "{}{}{}".format("\u2605"*(stars//2),
                                   "\u00bd" if stars%2 else '',
                                   "\u2606"*((10-stars)//2))
            # "\u2bea" is unicode half star but isn't supported on most systems i assume
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
                # 4=site/series not supported

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
                if error==4:
                    return QBrush(QColor(255, 255, 130)) # yellow
            # for last updated, let's scale it a little longer since some series take a while to update
            mod=min(180,(time.time()-self.arraydata[row][self.headerdata.index('UpdateTime')])/(34560*2))#divide into days,  added *2 to give it way more time.
            color = QColor(255-mod,255-mod,255) # shades of blue
            return QBrush(color)
        elif role == Qt.ToolTipRole:
            row = index.row()
            if self.arraydata[row][self.headerdata.index('Error')]>0:
                return self.arraydata[row][self.headerdata.index('Error Message')]
            else:
                return 'Updated %i days ago'%((time.time()-self.arraydata[row][self.headerdata.index('UpdateTime')])//86400)        
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
        self.layoutAboutToBeChanged.emit()
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
        self.layoutChanged.emit()
         
class SettingsDialog(QDialog):
    def __init__(self,initialSettings, parent=None):
        from PyQt5.QtCore import Qt


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

        optionsLayout.addRow("<b>Add credentials to enable these sites:</b>",None)
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
        
        self.cancelButton.released.connect(self.close)
        self.saveButton.released.connect(self.saveValues)

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
