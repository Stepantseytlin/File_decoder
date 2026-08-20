from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt, QTimer,QThread,Signal, Slot)
from multiprocessing import Queue
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget)
import PySide6
import PySide6.QtWidgets as QtWidgets
import pyqtgraph as pg
import numpy as np
class UPDworker(QObject):
    UpdateData = Signal(object)

    def __init__(self, queue:Queue):
        super().__init__()
        self.que = queue
        self.dataPolling = QTimer()
        self.dataPolling.setInterval(1000)
        self.dataPolling.timeout.connect(self.check_updates)
        self.dataPolling.start()
    @Slot()
    def check_updates(self):
            try :
                update = self.que.get(timeout=0.1)
                print(f"got update {update}")
                data_to_update = update["data"]
                self.UpdateData.emit(data_to_update)
            except:
                pass


class UIWidget(object):
    def setupUI(self,Widget):
        if not Widget.objectName():
            Widget.setObjectName(u"Widget")
            Widget.resize(1149, 609)
            sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
            sizePolicy.setHeightForWidth(Widget.sizePolicy().hasHeightForWidth())
            Widget.setSizePolicy(sizePolicy)
            self.gridLayout = QGridLayout(Widget)
            self.gridLayout.setObjectName(u"gridLayout")
            self.horizontalLayout = QHBoxLayout()
            self.horizontalLayout.setObjectName(u"horizontalLayout")
            self.Graphs = QVBoxLayout()
            self.Graphs.setObjectName(u"Graphs")
            self.verticalLayout_7 = QVBoxLayout()
            self.verticalLayout_7.setObjectName(u"verticalLayout_7")
            self.verticalLayout_5 = QVBoxLayout()
            self.verticalLayout_5.setObjectName(u"verticalLayout_5")
            self.verticalLayout_3 = QVBoxLayout()
            self.verticalLayout_3.setObjectName(u"verticalLayout_3")
            self.horizontalLayout_2 = QHBoxLayout()
            self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")

            



            self.plots = QScrollArea(Widget)
            self.plots.setObjectName(u"plots")
            self.plots.setMaximumSize(QSize(900, 900))
            self.plots.setWidgetResizable(True)
            self.plots1 = QWidget()
            self.plots1.setObjectName(u"plots1")
            self.plots1.setGeometry(QRect(0, 0, 714, 595))
            self.verticalLayout = QVBoxLayout(self.plots1)
            self.verticalLayout.setObjectName(u"verticalLayout")
            self.PulseWave = QWidget(self.plots1)
            self.PulseWave.setObjectName(u"PulseWave")
            self.label = QLabel(self.PulseWave)
            self.label.setObjectName(u"label")
            self.label.setGeometry(QRect(330, 10, 37, 12))

            self.verticalLayout.addWidget(self.PulseWave)

            self.Fr = QWidget(self.plots1)
            self.Fr.setObjectName(u"Fr")
            self.verticalLayout.addWidget(self.Fr)
            self.Frequency = QWidget(self.plots1)
            self.Frequency.setObjectName(u"Frequency")

            self.plots.setWidget(self.plots1)

            self.gridLayout.addWidget(self.plots, 0, 1, 1, 1)

class MainWind(QWidget,UIWidget, QObject):
    StartPollingThread = Signal()
    def __init__(self,queue:Queue):
        super(MainWind, self).__init__()
        self.plottedParameters = []
        self.SW_q = queue
        self.setupUI(self)
        # self.plot = pg.PlotWidget()
        # self.plotCR = pg.PlotWidget()
        # self.cr = QVBoxLayout(self.PulseWave)
        self.canv = None
        self.worker = UPDworker(self.SW_q)
        
        self.pollingTH = QThread()
        self.worker.moveToThread(self.pollingTH)

        self.pollingTH.start()
        self.StartPollingThread.connect(self.worker.check_updates)
        self.StartPollingThread.emit()


        self.worker.UpdateData.connect(self.update_plots)
     

        
    #     except:
    #         pass
    def deleteItemsOfLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                else:
                    self.deleteItemsOfLayout(item.layout())
    def removeplot(self, widg):
        for w in widg:
            self.deleteItemsOfLayout(w[2])
            self.deleteItemsOfLayout(self.canv)
            self.canv.removeWidget(w[0])
            self.verticalLayout.removeWidget(w[0])
            # for i in range(len(self.plottedParameters)):
            #     w[1].removeItem(i)
            # for lab in w[1]:
            #     self.canv.removeWidget(lab)
            #     self.verticalLayout.removeWidget(lab)
            self.canv.removeItem(w[2])
            self.verticalLayout.removeItem(w[2])

        print(f"removed widget plots")


    def oncheck(self, checked  ):
        for num, plot in enumerate(self.plots):
            print(f"\nplot {num}\n")
            # print(f"plot items are: {plot[0].findChild(pg.PlotDataItem, plot[1][0].text())}, {plot[0].getPlotItem().objectName()}")
            for CB in plot[1]:
                if CB.isChecked():
                    line = plot[0].findChild(pg.PlotDataItem, CB.text()) 
                    if not line:
                        line = plot[0].plot([], [], pen=pg.mkPen("#0f766e", width=2))
                        line.setData(np.arange(len(self.currentData[CB.text()])),self.currentData[CB.text()])
                        line.setParent(plot[0])
                        line.setObjectName(CB.text())
                elif (not CB.isChecked()) :
                    line = plot[0].findChild(pg.PlotDataItem, CB.text()) 
                    if line:
                        line.clear()
                        plot[0].removeItem(line)
                        plot[0].update()
                        print(f"{CB.text()} at plot {num} is not checked")
                        print(f"{line} to be deleted")
                    

                print(f"{self.currentData[CB.text()],CB.text()} - {CB.isChecked()}\n")



    def update_plots(self, data):
        self.currentData = data
        if self.canv: 
            self.removeplot(self.plots)
                
        else:
            self.canv = QVBoxLayout( )
            self.verticalLayout.addLayout(self.canv,1)
                
        newPlots = []
        self.plots = []
        for parameter in data:
            
            if parameter in self.plottedParameters:
                newPlots.append(parameter)
                
            
            newPlots.append(parameter)
            plottoadd=pg.PlotWidget()
            
            horizontalLayoutpar = QHBoxLayout()
            horizontalLayoutpar.setAlignment(PySide6.QtCore.Qt.AlignmentFlag.AlignLeft)
            label1 = QtWidgets.QCheckBox(f"{parameter}",)
            print(f"created {label1.text()}")
            label1.setChecked(True)
            horizontalLayoutpar.addWidget(label1,alignment=PySide6.QtCore.Qt.AlignmentFlag.AlignLeft)
            label1.stateChanged.connect(self.oncheck)
            acessoryLabels=[label1]
            for num, par in enumerate(data):
                    if par==parameter:
                        continue
                    labelac = QtWidgets.QCheckBox(f"{par}")
                    print(f"appended {labelac.text()}")
                    horizontalLayoutpar.addWidget(labelac)
                    acessoryLabels.append(labelac)
                    labelac.stateChanged.connect(self.oncheck)
                    
                    

            # label = QtWidgets.QCheckBox()

            # label.addItem(f"{parameter}",(parameter,data[parameter]))
            
            # label.setCurrentIndex(0*(len(newPlots)-1))

            # label.setCurrentText(f"{parameter}")
            # label.
            plottoadd.setMinimumSize(QSize(200,300))
            
            line : pg.PlotDataItem = plottoadd.plot([], [], pen=pg.mkPen("#0f766e", width=2))
            line.setParent(plottoadd)
            self.plotData(line, data[parameter])
            line.setObjectName(f"{parameter}")
            menu = plottoadd.getPlotItem().getMenu()

            translations = {
                "Export...": "Экспорт...",
                "View All": "Показать всё",
                "Mouse Mode": "Режим мыши",
                "Plot Options": "Настройки графика",
            }

            for action in menu.actions():
                if action.text() in translations:
                    action.setText(translations[action.text()])
            print(line)
            
            self.canv.addLayout(horizontalLayoutpar)
            self.canv.addWidget(plottoadd,1)
            self.plots.append((plottoadd,acessoryLabels,horizontalLayoutpar))
            
        self.plottedParameters = newPlots

    def plotData(self, plot : pg.PlotWidget,data):
        plot.setData(np.arange(len(data)),data)
        