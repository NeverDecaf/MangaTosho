REM pip install cfscrape --upgrade
REM add Tree(r'!MMCE_Win32', prefix=r'!MMCE_Win32') + [(r'book.ico',r'book.ico','DATA')], as arg to EXE()
REM in Analysis() change datas=[] to datas=[(r'node.exe','.')]
REM change name to MT.exe
REM pyi-makespec --onefile --noconsole --icon book.ico qtable.py
pip3 install fake_useragent -U
pip3 install cfscrape -U
pyinstaller --clean --noconfirm MT.spec