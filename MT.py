#!/usr/bin/env python3
import os,sys
import re
import operator
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from mangasql import SQLManager
import parsers
import time
import subprocess
import random
from qtrayico import Systray, HideableWindow
from functools import partial
import collections,queue
from constants import *
import math

def isfloat(string):
    try:
        float(string)
        return True
    except:
        return False
def set_registry(windows_startup, minimized):
    if os.name=='nt':
        settings = QSettings(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run", QSettings.NativeFormat)
        if windows_startup:
            try:
                sys._MEIPASS
                cmd = '"{}"'.format(sys.executable)
            except:
                cmd = '"{}"'.format(__file__)
            if minimized:
                cmd += ' -q'
            settings.setValue("MT",cmd)
        else:
            settings.remove("MT")

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
    
STAR_POLYGON = QPolygonF()
for i in range(5):
    STAR_POLYGON << QPointF(0.5 + 0.45 * math.cos((0.8 * i - 0.5) * math.pi),
                                0.5 + 0.45 * math.sin((0.8 * i - 0.5) * math.pi))
DIAMOND_POLYGON = QPolygonF()
DIAMOND_POLYGON << QPointF(0.4, 0.5) \
                    << QPointF(0.5, 0.4) \
                    << QPointF(0.6, 0.5) \
                    << QPointF(0.5, 0.6) \
                    << QPointF(0.4, 0.5)
# based on stardelegate example: https://github.com/baoboa/pyqt5/blob/master/examples/itemviews/stardelegate.py
class StarRating(object):
    # enum EditMode
    Editable, ReadOnly = range(2)

    PaintingScaleFactor = 20

    def __init__(self, starCount=1, maxStarCount=5):
        self._starCount = starCount
        self._maxStarCount = maxStarCount
        self.starPolygon = STAR_POLYGON
        self.diamondPolygon = DIAMOND_POLYGON


    def starCount(self):
        return self._starCount

    def maxStarCount(self):
        return self._maxStarCount

    def setStarCount(self, starCount):
        self._starCount = starCount

    def setMaxStarCount(self, maxStarCount):
        self._maxStarCount = maxStarCount

    def sizeHint(self):
        return self.PaintingScaleFactor * QSize(self._maxStarCount, 1) / 2

    def paint(self, painter, rect, palette, editMode):
        painter.save()

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        
        if editMode == StarRating.Editable:
            painter.setBrush(palette.highlight())
        else:
            painter.setBrush(palette.windowText())
        painter.fillRect(rect, palette.window())

        yOffset = (rect.height() - self.PaintingScaleFactor) / 2
        painter.translate(rect.x(), rect.y() + yOffset)
        painter.scale(self.PaintingScaleFactor, self.PaintingScaleFactor)
        half = QRectF(0.5,0,0.5,1)
        for i in range(self._maxStarCount):
            if i < self._starCount:
                painter.drawPolygon(self.starPolygon, Qt.WindingFill)
                if not i%2:
                    painter.fillRect(half,palette.window())
            elif editMode == StarRating.Editable:
                painter.drawPolygon(self.diamondPolygon, Qt.WindingFill)
            if i%2:
                painter.translate(1.0, 0.0)
        painter.restore()


class StarEditor(QWidget):

    editingFinished = pyqtSignal()

    def __init__(self, parent = None):
        super(StarEditor, self).__init__(parent)

        self._starRating = StarRating()

        self.setMouseTracking(True)
        self.setAutoFillBackground(True)

    def setStarRating(self, starRating):
        self._starRating = starRating

    def starRating(self):
        return int(self._starRating.starCount())

    def sizeHint(self):
        return self._starRating.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        self._starRating.paint(painter, self.rect(), self.palette(),
                StarRating.Editable)

    def mouseMoveEvent(self, event):
        star = self.starAtPosition(event.x())

        if star != self._starRating.starCount() and star != -1:
            self._starRating.setStarCount(star)
            self.update()

    def mouseReleaseEvent(self, event):
        self.editingFinished.emit()

    def starAtPosition(self, x):
        # Enable a star, if pointer crosses the center horizontally.
        starwidth = self._starRating.sizeHint().width() // self._starRating.maxStarCount()
        star = (x + starwidth / 2) // starwidth
        if 0 <= star <= self._starRating.maxStarCount():
            return star

        return -1

class StarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        starRating = index.data()
        if isinstance(starRating, StarRating):
            if option.state  & QStyle.State_Selected:
                if option.state & QStyle.State_Active or sys.platform != 'win32':
                    option.palette.setBrush(option.palette.Background,option.palette.highlight())
            else:
                option.palette.setBrush(option.palette.Background,index.data(Qt.BackgroundRole))
            starRating.paint(painter, option.rect, option.palette,
                    StarRating.ReadOnly)
        else:
            if index.column() not in (TABLE_COLUMNS.index('Title'),TABLE_COLUMNS.index('Unread')):
                option.decorationPosition = QStyleOptionViewItem.Right;
            super(StarDelegate, self).paint(painter, option, index)

    def sizeHint(self, option, index):
        starRating = index.data()
        if isinstance(starRating, StarRating):
            return starRating.sizeHint()
        else:
            return super(StarDelegate, self).sizeHint(option, index)

    def createEditor(self, parent, option, index):
        starRating = index.data()
        if isinstance(starRating, StarRating):
            editor = StarEditor(parent)
            editor.editingFinished.connect(self.commitAndCloseEditor)
            return editor
        else:
            return super(StarDelegate, self).createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        starRating = index.data()
        if isinstance(starRating, StarRating):
            editor.setStarRating(starRating)
        else:
            super(StarDelegate, self).setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        starRating = index.data()
        if isinstance(starRating, StarRating):
            model.setData(index, editor.starRating())
        else:
            super(StarDelegate, self).setModelData(editor, model, index)

    def commitAndCloseEditor(self):
        editor = self.sender()
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)

class MyWindow(HideableWindow): 
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
        self.sqlmanager = SQLManager(self.parserFetcher)
        # create table
        self.table = self.createTable() 

        self.setCentralWidget(self.table)
        menubar = self.menuBar()

        self.saddAction=QAction(self.tr("&Add Series"), self)
        self.saddAction.triggered.connect(self.addevent)
        
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.saddAction)

        self.historyMenu = menubar.addMenu('&History')
        

        self.sinfoAction=QAction(self.tr("&Supported Sites"), self)
        self.sinfoAction.triggered.connect(self.sinfoevent)

        self.tipsAction=QAction(self.tr("&Tips"), self)
        self.tipsAction.triggered.connect(self.tips)

        self.legendAction=QAction(self.tr("&Legend"), self)
        self.legendAction.triggered.connect(self.colorLegend)

        self.settingsMenu = menubar.addMenu('&Settings')

        self.readerAction=QAction(self.tr("&Change Reader"), self)
        self.readerAction.triggered.connect(self.changeReaderEvent)
        self.settingsMenu.addAction(self.readerAction)

        self.credsAction= QAction(self.tr("&Add Credentials"), self)
        self.credsAction.triggered.connect(self.addCredentials)
        self.settingsMenu.addAction(self.credsAction)

        self.optionsAction= QAction(self.tr("&Options"), self)
        self.optionsAction.triggered.connect(self.setOptions)
        self.settingsMenu.addAction(self.optionsAction)
        
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

        self.explorerAction=QAction("&Open Directory", self)
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

        settings_dict = self.sqlmanager.readSettings()
        set_registry(int(settings_dict['start_with_windows']) == 2, int(settings_dict['start_hidden']) == 2)
        if '-q' not in sys.argv and '/q' not in sys.argv and '/silent' not in sys.argv and 0==int(settings_dict['start_hidden']):
            self.show()
        
    def setHistory(self,data):
        self.historyMenu.clear()
        for title,num,path in data:
            tmpaction = QAction(self.tr("&{0} {1:g}".format(title,float(num))),self)
            self.historyMenu.addAction(tmpaction)
            tmpaction.triggered.connect(partial(self.tm.readpath,path))

    def sinfoevent(self):
        QMessageBox.information(self, 'Supported Manga Sites',self.parserFetcher.get_valid_sites())

    def colorLegend(self):
        class LegendDialog(QDialog):
            def __init__(self, parent=None):
                from PyQt5.QtCore import Qt


                super(LegendDialog, self).__init__(parent)
                self.result=None
                self.setWindowTitle(self.tr("Legend"))
                self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

                mainLayout = QVBoxLayout()
                mainLayout.setAlignment(Qt.AlignCenter)

                optionsLayout = QFormLayout()
                confirmLayout = QGridLayout()

                top=QWidget()
                bottom=QWidget()
                top.setLayout(optionsLayout)
                bottom.setLayout(confirmLayout)

                q = QLabel()
                q.setPixmap(ERROR_ICON)
                for k,v in (
                    (COMPLETE_ICON,'Completed'),
                    (STALLED_ICON,'Stalled (No Update in {} Days)'.format(STALLED_TIME//86400)),
                    (ONGOING_ICON,'Ongoing'),
                    (UNREAD_ICON,'Unread Chapters'),
                    (ERROR_ICON,'Minor Error, May be Temporary'),
                    (SEVERE_ERROR_ICON,'Persistent Error, Needs Attention'),
                    (RIP_ICON,'Series no Longer Supported.')
                    ):
                    q = QLabel()
                    q.setPixmap(k)
                    optionsLayout.addRow(q,QLabel(v))
                optionsLayout.addRow(QLabel("Hover over a series to get error details."))

                self.okButton=QPushButton('Ok')
                
                confirmLayout.addWidget(self.okButton,0,0)
                
                self.okButton.released.connect(self.close)

                mainLayout.addWidget(top)
                mainLayout.addWidget(bottom)
                self.setLayout(mainLayout)

        d = LegendDialog(self)
        d.exec_()
        d.deleteLater()

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

    def openreader(self):
        if os.name=='nt':
            if self.tm.readercmd=='MMCE':
                subprocess.Popen('"{}"'.format(resource_path(MMCE)))
            else:
                subprocess.Popen('"{}"'.format(self.tm.readercmd))
        else:
            subprocess.Popen(self.tm.readercmd, shell=True)

    def changeReaderEvent(self):
        reply = QInputDialog.getText(self, self.tr("Enter reader command"), self.tr("Command (Leave blank to use built-in MMCE)"),text=self.tr(self.tm.getReader()))
        if reply[1]:
            self.tm.setReader(reply[0])
        
    def addCredentials(self):
        d=CredsDialog(self.tm.getCredentials(),self)
        d.exec_()
        if d.getValues():
            settings = d.getValues()
            self.tm.setCredentials(settings)
        d.deleteLater()
        
    def setOptions(self):
        d=OptionsDialog(self.tm.getSettings(),self)
        d.exec_()
        if d.getValues():
            settings = d.getValues()
            self.tm.applySettings(settings)
        d.deleteLater()

    def createTable(self):
        # create the view
        tv = QTableView()
        self.tv=tv
        
        # set the table model
        header = TABLE_COLUMNS # ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime', 'Error', 'SuccessTime']
        tm = MyTableModel(header, self.sqlmanager, self)
        self.tm=tm
##        im=ColoredCell()
##        im.setSourceModel(tm)
        tv.setModel(tm)
        self.tv.setItemDelegate(StarDelegate())
##        self.tv.setItemDelegateForColumn(3, IconDelegate())
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

##        hh.setStretchLastSection(False)
##        hh.setSectionResizeMode(1,QHeaderView.Stretch)

        # set column width to fit contents
        tv.resizeColumnsToContents()
        
        if tv.columnWidth(TABLE_COLUMNS.index('Title')) < 250:
            tv.setColumnWidth(TABLE_COLUMNS.index('Title'),250)
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
                if match:
                    if match.ABBR==site and reply[0] != url:
                        self.editSeriesUrl.emit(self.tv.indexAt(pos),reply[0])
                    elif reply[0] == url:
                        QMessageBox.information(self, 'Error changing URL', 'New URL is the same as existing one.')
                    else:
                        self.addSeries.emit(reply[0])
                else:
                    QMessageBox.information(self, 'Error changing URL', 'New URL is not valid.')
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
    'None can be inserted any number of times, and ignores key func'
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
            
    def contains(self, item):
        return self.keyfunc(item) in self.set
        
    # Initialize the queue representation
    def _init(self, maxsize):
        self.queue = collections.deque()
        self.set = set()

    def _qsize(self):
        return len(self.queue)

    # Put a new item in the queue
    def _put(self, item):
        if item is None:
            self.queue.append(item)
        elif self.keyfunc(item) not in self.set:
            self.queue.append(item)
            self.set.add(self.keyfunc(item))

    def _putLeft(self, item):
        if item is None:
            self.queue.appendleft(item)
        elif self.keyfunc(item) not in self.set:
            self.queue.appendleft(item)
            self.set.add(self.keyfunc(item))

    # Get an item from the queue
    def _get(self):
        item = self.queue.popleft()
        if item is not None:
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
            try:
                site_lock = self.site_locks[datum[self.headerdata.index('Site')]]
            except KeyError:
                self.errorRow.emit(datum, 4,['Parser Error: Site/series no longer supported.'])
                return
            if not site_lock.tryAcquire():
                self.queue.put(datum) # re-queue the data
                time.sleep(1) # lazy solution
                return
            sitelock_aquired = True
            lockset = self.series_locks.setdefault(datum[self.headerdata.index('Url')],[QMutex(),0,QMutex()])
            thislock = lockset[0]
            thislock.lock()
            try:
                complete = datum[self.headerdata.index('Complete')]
                if complete:
                    return
                err,data = self.sql.updateSeries(datum) # this method does not access the sqlite db and therefore can function in a separate thread.
                lockset[2].lock()
                try:
                    if err>0:
                        self.errorRow.emit(datum, err, data)
                    elif len(data):
                        self.updateRow.emit(datum, data, err)                        
                    else:
                        self.errorRow.emit(datum, 0, [''])
                finally:
                    lockset[2].unlock()
                time.sleep(random.uniform(*parsers.CHAPTER_DELAY)) # sleep between series (same delay as between chapters)
            finally:
                thislock.unlock()
        except Exception as e:
            fh=open(storage_path('CRITICAL ERROR SEARCH MT.py FOR THIS LINE'),'w')
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

class SiteLocker(QThread):
    def __init__(self, tolock, lockamt, parent=None):
        QThread.__init__(self, parent)
        self.semaphores = tolock
        self.numlocks = lockamt

    def run(self):
        for sema in self.semaphores.values():
            sema.acquire(self.numlocks)
    
class MyTableModel(QAbstractTableModel): 
    dataChanged = pyqtSignal(QModelIndex, QModelIndex)
    layoutAboutToBeChanged = pyqtSignal()
    layoutChanged = pyqtSignal()
    

    def __init__(self, headerdata, sqlmanager, parent=None, *args): 
        """ datain: a list of lists
            headerdata: a list of strings
        """
        QAbstractTableModel.__init__(self, parent, *args)

        

        self.myparent = parent
        self.sql = sqlmanager
        
        self.site_locks = {}
        self.series_locks = {}

        self.arraydata = self.sql.getSeries()
        self.headerdata = headerdata + [' ']
        
        self.current_col = self.headerdata.index("Read")
        self.total_col = self.headerdata.index("Chapters")
        self.title_col = self.headerdata.index("Title")
        self.editable_cols = (self.current_col, self.headerdata.index("Rating"))

        self.sort_order=Qt.AscendingOrder
        self.sort_column=self.headerdata.index("Unread")

        self.second_sort_order=Qt.DescendingOrder
        self.second_sort_column=self.headerdata.index("Title")
        
        self.setReader(self.sql.getReader())

        self.updateQueue = UniqueDeque(key = lambda x: x[self.headerdata.index("Url")])

        init_settings = self.getSettings()
        # also set the reg keys
        self.global_threadsmax = int(init_settings['global_threadsmax'])
        self.site_threadsmax = int(init_settings['site_threadsmax'])
        
        for site in self.sql.parserFetch.get_valid_site_abbrs():
            self.site_locks[site] = QSemaphore(self.site_threadsmax)
        
        for i in range(self.site_threadsmax):
            thread = UpdateThread(self.sql,self.headerdata,self.site_locks,self.series_locks,self.updateQueue,parent=self)
            thread.updateRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.updateRow)
            thread.errorRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.errorRow)
            thread.start()

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

    def applySettings(self, settings_dict):
        self.sql.writeSettings(settings_dict)
        #apply site settings:
        if int(settings_dict['site_threadsmax']) > self.site_threadsmax:
            for sema in self.site_locks.values():
                sema.release(int(settings_dict['site_threadsmax'])-self.site_threadsmax)
        elif int(settings_dict['site_threadsmax']) < self.site_threadsmax:
            SiteLocker(self.site_locks,self.site_threadsmax-int(settings_dict['site_threadsmax']),self).start()
        #apply global settings:
        if int(settings_dict['global_threadsmax']) > self.global_threadsmax:
            for i in range(int(settings_dict['global_threadsmax'])-self.global_threadsmax):
                thread = UpdateThread(self.sql,self.headerdata,self.site_locks,self.series_locks,self.updateQueue,parent=self)
                thread.updateRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.updateRow)
                thread.errorRow['PyQt_PyObject', 'PyQt_PyObject', 'PyQt_PyObject'].connect(self.errorRow)
                thread.start()
        elif int(settings_dict['global_threadsmax']) < self.global_threadsmax:
            for i in range(self.global_threadsmax-int(settings_dict['global_threadsmax'])):
                self.updateQueue.putLeft(None)
        #apply startup settings:
        set_registry(int(settings_dict['start_with_windows']) == 2, int(settings_dict['start_hidden']) == 2)

    def getSettings(self):
        return self.sql.readSettings()

    def addSeries(self,url):
        display_success_message = True
        try:
            series = self.sql.parserFetch.fetch(url)
            if not isinstance(series,parsers.SeriesParser):
                QMessageBox.information(self.myparent, 'Series Add Failed','The URL you provided is not valid. Make sure you are linking the series page/chapter list and not a specific chapter or page')
                return None
        except:
            QMessageBox.information(self.myparent, 'Series Add Failed','Error adding this series. Check to make sure your URL is valid. (This may be a bug)')
            return None
        err,data=self.sql.addSeries(series)
        if err == self.sql.SERIES_URL_CONFLICT:
            QMessageBox.information(self.myparent, 'Series Add Failed','You are already reading this series.')
            return None
        elif err == self.sql.SERIES_TITLE_CONFLICT:
            display_success_message = False
            #present user with merge dialog
            d=MergeDialog(data, self.myparent)
            d.exec_()
            if d.result == d.MERGE_OPTION:
                # xfer rating and read to new
                row = [a[TABLE_COLUMNS.index('Url')] for a in self.arraydata].index(data[TABLE_COLUMNS.index('Url')])
                idx = self.createIndex(row,0)
                self.removeSeries(idx,QMessageBox.No)
                err,data=self.sql.addSeries(series, read = data[self.headerdata.index('Read')],
                                            chapters = data[self.headerdata.index('Chapters')],
                                            unread = data[self.headerdata.index('Unread')],
                                            rating = data[self.headerdata.index('Rating')])
            elif d.result == d.DUPLICATE_OPTION:
                # rename new adding (2)
                for i in range(2,50):
                    err,data=self.sql.addSeries(series, alt_title = "{} ({})".format(series.get_title(), i))
                    if err == self.sql.SERIES_NO_CONFLICT:
                        break # success
            elif d.result == d.REPLACE_OPTION:
                #delete old + files, xfer rating only.
                row = [a[TABLE_COLUMNS.index('Url')] for a in self.arraydata].index(data[TABLE_COLUMNS.index('Url')])
                idx = self.createIndex(row,0)
                self.removeSeries(idx,QMessageBox.Yes)
                err,data=self.sql.addSeries(series, rating = data[self.headerdata.index('Rating')])
            d.deleteLater()
            if d.result == d.CANCEL_OPTION:
                return None
        # finally add the series to table
        if err == self.sql.SERIES_NO_CONFLICT:
            datalist = list(data)
            old=self.rowCount(None)
            self.beginInsertRows(QModelIndex(),old,old)
            self.arraydata.append(datalist)
            self.endInsertRows()
            self.resort()
            if display_success_message:
                QMessageBox.information(self.myparent, 'Series Added','New series was added successfully.')
            self.updateSeries([a[TABLE_COLUMNS.index('Url')] for a in self.arraydata].index(datalist[TABLE_COLUMNS.index('Url')]))
            return None
        QMessageBox.information(self.myparent, 'Series Add Failed','Error adding this series. Check to make sure your URL is valid. (This may be a bug)')
        return None
    
    def _updateHelper(self,data):
        self.series_locks.setdefault(data[self.headerdata.index('Url')],[QMutex(),0,QMutex()])
        self.updateQueue.putLeft(data)
        # acquire the lock? idk

    def updateSeries(self,indexrow):
        self._updateHelper(self.arraydata[indexrow])

    def updateAll(self):
        settings = self.getSettings()
        for d in self.sql.getToUpdate(60*int(settings['series_update_freq'])):
            self._updateHelper(d)

    def updateRow(self,olddata,newdata,errcode):
        try:
            row = [a[TABLE_COLUMNS.index('Url')] for a in self.arraydata].index(olddata[TABLE_COLUMNS.index('Url')])
        except ValueError:
            return
        if errcode<1:
            newdata[self.headerdata.index('SuccessTime')]=time.time()
        newdata[self.headerdata.index('UpdateTime')]=time.time()
        newdata[self.headerdata.index('Error')] = errcode # always 0
        newdata[self.headerdata.index('Error Message')] = None
        newdata[self.headerdata.index('LastUpdateAttempt')]=time.time()
        dataChanged = 0
        if self.arraydata[row][self.headerdata.index('Url')] in self.series_locks:
            lockset = self.series_locks[self.arraydata[row][self.headerdata.index('Url')]]
            dataChanged = lockset[1]
        if dataChanged:
            for col in self.editable_cols:
                newdata[col] = self.arraydata[row][col]
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
            row = [a[TABLE_COLUMNS.index('Url')] for a in self.arraydata].index(data[TABLE_COLUMNS.index('Url')])
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
        if index.column() == TABLE_COLUMNS.index('Read') and not user and not value.replace('.','',1).isdigit(): # enforces float values for chapter num
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
        toopen=storage_path(SQLManager.cleanName(self.arraydata[index.row()][self.headerdata.index('Title')]))
        if os.path.exists(toopen):
            if sys.platform == 'darwin':
                subprocess.call('open "{}"'.format(toopen), shell=True)
            if sys.platform == 'win32':
                subprocess.call('explorer "{}"'.format(toopen))
            else:
                subprocess.call('xdg-open "{}"'.format(toopen), shell=True)
     
    def removeSeries(self,index,removedata):
        self.beginRemoveRows(QModelIndex(),index.row(),index.row())
        self.series_locks.setdefault(self.arraydata[index.row()][self.headerdata.index('Url')],[QMutex(),0,QMutex()])[1]=0
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
        updatelocked = 0
        if self.arraydata[index.row()][self.headerdata.index('Url')] in self.series_locks:
            lockset = self.series_locks[self.arraydata[index.row()][self.headerdata.index('Url')]]
            lock = lockset[0]
            if lock.tryLock():
                locked=lock
                if self.updateQueue.contains(self.arraydata[index.row()]):
                    lockset[1] = 1 # update is queued, notify of changed data.
                else:
                    lockset[1] = 0 # update not queued, proceed normally.
            else:
                lockset[1] = 1 # data changed but lock could not be aquired, meaning update in progress
                updatelocked = lockset[2]
                updatelocked.lock()
        try:
            last=self.arraydata[index.row()][self.headerdata.index('Read')]#last read chapter

            sdir=storage_path(SQLManager.cleanName(self.arraydata[index.row()][self.headerdata.index('Title')]))#name of series
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
            if updatelocked:
                updatelocked.unlock()
##        self.resort()

    def readpath(self, path):
        if os.name=='nt':
            if self.readercmd=='MMCE':
                subprocess.Popen('"{}" "{}"'.format(resource_path(MMCE),os.path.realpath(path)))
            else:
                subprocess.Popen('"{}" "{}"'.format(self.readercmd,os.path.realpath(path)))
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
                return StarRating(0,10)
            return StarRating(stars,10)
            # "\u2bea" is unicode half star but isn't supported on most systems i assume
        if not index.isValid(): 
            return QVariant()
        elif role==Qt.BackgroundRole:
            if index.row()%2:
                return QBrush(QColor(255,255,255))
            else:
                return QBrush(QColor(235,234,233))
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
        elif role == Qt.DecorationRole:
            if index.column() == self.headerdata.index('Title'):
                if self.arraydata[index.row()][self.headerdata.index('Complete')]:
                    return COMPLETE_ICON
                elif time.time() - self.arraydata[index.row()][self.headerdata.index('UpdateTime')] > STALLED_TIME:
                    return STALLED_ICON
                else:
                    return ONGOING_ICON
            elif index.column() == self.headerdata.index('Unread') and self.arraydata[index.row()][self.headerdata.index('Unread')]:
                return UNREAD_ICON
            elif index.column() == self.headerdata.index('Chapters') and self.arraydata[index.row()][self.headerdata.index('Error')] in (1,2,3):
                if self.arraydata[index.row()][self.headerdata.index('Error')] in (1,2) and time.time() - self.arraydata[index.row()][self.headerdata.index('SuccessTime')] < SEVERE_ERROR_TIME:
                    return ERROR_ICON
                else:
                    return SEVERE_ERROR_ICON
            elif index.column() == self.headerdata.index('Site') and self.arraydata[index.row()][self.headerdata.index('Error')] == 4:
                return RIP_ICON
            else:
                return QVariant()
                
        elif role != Qt.DisplayRole: 
            return QVariant()
        if index.column() < len(self.headerdata) -1 :
            return QVariant(self.arraydata[index.row()][index.column()])
        
        return QVariant()

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
        if self.sort_column == self.headerdata.index('Title'):
            self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.sort_column))
        elif self.sort_column == self.headerdata.index('Site'):
            self.arraydata = sorted(self.arraydata, key=operator.itemgetter(self.sort_column,self.title_col))
        else:
            self.arraydata = sorted(self.arraydata, key=lambda x: (SQLManager.formatName(x[self.sort_column]),x[self.title_col]))
        if self.sort_order == Qt.DescendingOrder:
            self.arraydata.reverse()
        self.layoutChanged.emit()

class MergeDialog(QDialog):
    DUPLICATE_OPTION = 3
    REPLACE_OPTION = 2
    MERGE_OPTION = 1
    CANCEL_OPTION = 0
    
    def __init__(self, existingSeries, parent=None):
        from PyQt5.QtCore import Qt
        super(MergeDialog, self).__init__(parent)
        self.result=self.CANCEL_OPTION
        self.setWindowTitle(self.tr("Merge Series"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

        mainLayout = QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignCenter)

        descLayout = QFormLayout()
        buttonLayout = QGridLayout()

        top=QWidget()
        bottom=QWidget()
        top.setLayout(descLayout)
        bottom.setLayout(buttonLayout)
        
        hyperlink = QLabel('You are already reading a series with the same name from <a href="{}">{}</a>'.format(existingSeries[TABLE_COLUMNS.index('Url')],existingSeries[TABLE_COLUMNS.index('Site')]))
        hyperlink.setOpenExternalLinks(True)
        descLayout.addRow(hyperlink)
        descLayout.addRow(QLabel("Choose how you wish to proceed:"))
        descLayout.addRow(QLabel("<b>Merge:</b> Old follow will be updated to new url. Read progress and downloaded files will be saved"))
        descLayout.addRow(QLabel("<b>Overwrite:</b> Old follow and all downloaded files will be deleted, read will be reset to 0"))
        descLayout.addRow(QLabel("<b>Keep Both:</b> New follow will be renamed to \"{} (2)\"".format(existingSeries[TABLE_COLUMNS.index('Title')])))

        choices = (
            ('Merge',self.MERGE_OPTION),
            ('Overwrite',self.REPLACE_OPTION),
            ('Keep Both',self.DUPLICATE_OPTION),
            ('Cancel',self.CANCEL_OPTION),
            )
        self.buttons = []
        for i,(text,opt) in enumerate(choices):
            b = QPushButton(text)
            buttonLayout.addWidget(b,0,i)
            self.buttons.append(b)
            b.released.connect(partial(self.saveAndExit,opt))

        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

    def saveAndExit(self,value):
        self.result = value
        self.close()
        
class CredsDialog(QDialog):
    def __init__(self,initialSettings, parent=None):
        from PyQt5.QtCore import Qt


        super(CredsDialog, self).__init__(parent)
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
        
class OptionsDialog(QDialog):
    def __init__(self, initialSettings, parent=None):
        from PyQt5.QtCore import Qt
        super(OptionsDialog, self).__init__(parent)
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

        self.options = {}

        optionsLayout.addRow("Series update checking frequency (minutes):",None)
        self.options['series_update_freq'] = QSpinBox()
        self.options['series_update_freq'].setRange(SERIES_UPDATE_FREQ//60000, MAX_UPDATE_FREQ//60)
        self.options['series_update_freq'].setValue(int(initialSettings['series_update_freq']))
        optionsLayout.addRow(self.options['series_update_freq'])
        
        optionsLayout.addRow("Maximum simultaneous downloads:",None)
        self.options['global_threadsmax'] = QSpinBox()
        self.options['global_threadsmax'].setRange(1,64)
        self.options['global_threadsmax'].setValue(int(initialSettings['global_threadsmax']))
        optionsLayout.addRow(self.options['global_threadsmax'])
        self.options['global_threadsmax'].valueChanged.connect(self.setSiteMax)

        optionsLayout.addRow("Maximum simultaneous downloads per site:",None)
        self.options['site_threadsmax'] = QSpinBox()
        self.options['site_threadsmax'].setRange(1,64)
        self.options['site_threadsmax'].setValue(int(initialSettings['site_threadsmax']))
        optionsLayout.addRow(self.options['site_threadsmax'])

        self.options['start_with_windows'] = QCheckBox("Start with Windows")
        self.options['start_with_windows'].setCheckState(int(initialSettings['start_with_windows']))
        optionsLayout.addRow(self.options['start_with_windows'])
        self.options['start_hidden'] = QCheckBox("Start minimized to tray")
        self.options['start_hidden'].setCheckState(int(initialSettings['start_hidden']))
        optionsLayout.addRow(self.options['start_hidden'])

        if os.name!='nt':
            self.options['start_with_windows'].setDisabled(True)

        self.saveButton=QPushButton('Save')
        self.cancelButton=QPushButton('Cancel')
        
        confirmLayout.addWidget(self.saveButton,0,0)
        confirmLayout.addWidget(self.cancelButton,0,1)
        
        self.cancelButton.released.connect(self.close)
        self.saveButton.released.connect(self.saveValues)

        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)
        
    def setSiteMax(self):
        self.options['site_threadsmax'].setMaximum(self.options['global_threadsmax'].value())
        
    def getValues(self):
        return self.result
    
    def saveValues(self):
        self.result={}
        for key in self.options:
            try:
                self.result[key] = self.options[key].value()
            except AttributeError:
                self.result[key] = self.options[key].checkState()
        self.close()
        
if __name__ == "__main__":
    main_app = QApplication(sys.argv)
    SEVERE_ERROR_ICON = QPixmap(SEVERE_ERROR_ICON_PATH)
    COMPLETE_ICON = QPixmap(COMPLETE_ICON_PATH)
    STALLED_ICON = QPixmap(STALLED_ICON_PATH)
    ONGOING_ICON = QPixmap(ONGOING_ICON_PATH)
    UNREAD_ICON = QPixmap(UNREAD_ICON_PATH)
    ERROR_ICON = QPixmap(ERROR_ICON_PATH)
    RIP_ICON = QPixmap(RIP_ICON_PATH)
##    main_app.setStyle('Plastique')
    main_app.setQuitOnLastWindowClosed(False)
    main_window = MyWindow()
    main_window.setWindowTitle('MT')
    main_window.setWindowIcon(QIcon(resource_path("book.ico")))
    tray_icon = trayIcon(main_window)
    sys.exit(main_app.exec_())
