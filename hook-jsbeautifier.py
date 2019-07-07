import os
import jsbeautifier
hiddenimports = ['six']
datas = [(r'{}\*.py'.format(os.path.join(os.path.dirname(os.path.abspath(jsbeautifier.__file__)),'unpackers')),'jsbeautifier/unpackers')]
