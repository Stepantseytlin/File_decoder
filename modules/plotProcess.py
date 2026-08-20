from modules import PlotProcessUtils
from modules.PlotProcessUtils import MainWind
from multiprocessing import Process
import multiprocessing as mp
import sys

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
win = MainWind()
win.show()
sys.exit(app.exec()) 