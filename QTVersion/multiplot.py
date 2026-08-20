from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QComboBox, QGraphicsProxyWidget
from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QColor, QEnterEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
@dataclass
class AxisDescriptor:
    name: str
    color: str
    view_box: pg.ViewBox
    axis: pg.AxisItem
from PySide6.QtGui import QPainterPath

class SharedDragViewBox(pg.ViewBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._y_views: list[pg.ViewBox] = [self]

    def add_y_view(self, view_box: pg.ViewBox) -> None:
        if view_box not in self._y_views:
            self._y_views.append(view_box)

    def mouseDragEvent(self, event, axis=None):
        # События от конкретных AxisItem оставляем независимыми.
        if axis is not None:
            return super().mouseDragEvent(event, axis=axis)

        # Общую X двигает только основной ViewBox.
        pg.ViewBox.mouseDragEvent(
            self,
            event,
            axis=pg.ViewBox.XAxis,
        )

        # Один и тот же вертикальный drag получают все ViewBox.
        for view_box in self._y_views:
            pg.ViewBox.mouseDragEvent(
                view_box,
                event,
                axis=pg.ViewBox.YAxis,
            )
class InteractiveAxisItem(pg.AxisItem):
    def __init__(
        self,
        *args,
        hit_padding: float = 18,
        **kwargs,
    ):
        print(f"keywf: {args , kwargs}")
        super().__init__(*args, **kwargs)
        self.hit_padding = hit_padding

    def _interaction_rect(self):
        rect = self.mapRectFromParent(self.geometry())
        
        if self.orientation in ("left", "right"):
            return rect.adjusted(
                -self.hit_padding,
                0,
                self.hit_padding,
                0,
            )

        return rect.adjusted(
            0,
            -self.hit_padding,
            0,
            self.hit_padding,
        )

    def boundingRect(self):
        return super().boundingRect().united(
            self._interaction_rect()
        )

    def shape(self):
        print(f"hitting space = {super().boundingRect().united(self._interaction_rect())}")
        path = QPainterPath()
        path.addRect(self._interaction_rect())
        return path
    def _view_axis(self) -> int:
        if self.orientation in ("left", "right"):
            return pg.ViewBox.YAxis
        return pg.ViewBox.XAxis

    def wheelEvent(self, event) -> None:
        view_box = self.linkedView()

        if view_box is None:
            event.ignore()
            return

        view_box.wheelEvent(
            event,
            axis=self._view_axis(),
        )

    def mouseDragEvent(self, event):
        view_box = self.linkedView()

        if view_box is None:
            event.ignore()
            return

        return view_box.mouseDragEvent(
            event,
            axis=self._view_axis(),
        )

class AxisMarker(QWidget):
    """
    Узкий цветной маркер свернутой оси.
    """

    def __init__(
        self,
        color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._color = QColor(color)

        self.setFixedWidth(8)
        self.setMinimumHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


class AxisPopup(QWidget):
    """
    Плавающее окно с настоящими AxisItem.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            # Qt.WindowType.Tool
            # | Qt.WindowType.FramelessWindowHint,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setWindowFlag(
            Qt.WindowType.WindowDoesNotAcceptFocus,
            True,
        )

        self.setObjectName("axisPopup")

        self.setStyleSheet("""
            QWidget#axisPopup {
                background: palette(window);
                border: 1px solid palette(mid);
            }
        """)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn#ScrollBarAsNeeded
        )

        # QWidget, внутри которого находится QGraphicsScene.
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setContentsMargins(0,0,0,0)
        self.scroll_area.setWidget(self.graphics_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(100)
        layout.addWidget(self.scroll_area)

        # self.resize(700, 320)
        self.setSizePolicy(
    QSizePolicy.Policy.Preferred,
    QSizePolicy.Policy.Expanding,
)

        self.scroll_area.setWidgetResizable(True)

        self.graphics_widget.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMinimumWidth(80)
        self.setMaximumWidth(90)

    def add_axis(
        self,
        axis: pg.AxisItem,
        column: int,
    ) -> None:
        """
        Добавляет AxisItem в горизонтальный ряд.
        """

        self.graphics_widget.ci.addItem(
            axis,
            row=0,
            col=column,
        )

        # В popup каждая ось получает фиксированную ширину.
        axis.setWidth(80)
        
        required_width = max(
            1,
            column + 1,
        ) * 90

        self.graphics_widget.setMinimumWidth(required_width+60)
        self.graphics_widget.setMinimumHeight(280)


class CollapsibleAxesPanel(QWidget):
    """
    Свернутая панель осей с popup при наведении.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.axes: list[AxisDescriptor] = []

        self.setMouseTracking(True)

        self.marker_container = QWidget(self)
        self.marker_layout = QHBoxLayout(self.marker_container)
        self.marker_layout.setContentsMargins(2, 2, 2, 2)
        self.marker_layout.setSpacing(2)

        self.popup = AxisPopup(self.window())

        # Закрываем не мгновенно, иначе мышь не успеет
        # перейти со свернутой панели в popup.
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.setInterval(250)
        self.close_timer.timeout.connect(self._try_close_popup)

        self.popup.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.marker_container)

        self.setFixedWidth(50)

    def add_axis(
        self,
        *,
        name: str,
        color: str,
        view_box: pg.ViewBox,
        yticks : dict = None
    ) -> pg.AxisItem:
        """
        Создает настоящую ось в popup и маркер
        в свернутой панели.
        """

        if yticks:
            try:
                yticks={int(a):b for a,b in list(yticks.items())}
            except:
                yticks={int(b):a for a,b in list(yticks.items())}
        axis = MyAxis(#InteractiveAxisItem(
            orientation="left",
            hit_padding=0,
            yticks = yticks
        )
        # axis = pg.AxisItem(
        #     orientation="left",
        # )

        axis.setLabel(
            text=name,
            color=color,
        )
        axis.setPen(pg.mkPen(color))
        axis.setTextPen(pg.mkPen(color))

        # Ось остается постоянно связанной со своим ViewBox.
        axis.linkToView(view_box)

        descriptor = AxisDescriptor(
            name=name,
            color=color,
            view_box=view_box,
            axis=axis,
        )

        self.axes.append(descriptor)

        marker = AxisMarker(color)
        marker.installEventFilter(self)

        self.marker_layout.addWidget(marker)

        self.popup.add_axis(
            axis,
            column=len(self.axes) - 1,
        )

        return axis

    def enterEvent(
        self,
        event: QEnterEvent,
    ) -> None:
        self.close_timer.stop()
        self.open_popup()
        super().enterEvent(event)

    def leaveEvent(
        self,
        event: QEvent,
    ) -> None:
        self.close_timer.start()
        super().leaveEvent(event)

    def eventFilter(
        self,
        watched,
        event: QEvent,
    ) -> bool:
        if watched is self.popup:
            if event.type() == QEvent.Type.Enter:
                self.close_timer.stop()

            elif event.type() == QEvent.Type.Leave:
                self.close_timer.start()

        elif isinstance(watched, AxisMarker):
            if event.type() == QEvent.Type.Enter:
                self.close_timer.stop()
                self.open_popup()

        return super().eventFilter(watched, event)

    def open_popup(self) -> None:
        """
        Показывает popup рядом со свернутой полосой.
        """

        # global_position = self.mapToGlobal(
        #     QPoint(self.width(), 0)
        # )

        # self.popup.move(global_position)
        self.popup.show()
        # self.popup.raise_()

    def _try_close_popup(self) -> None:
        """
        Закрывает окно, только если курсор не находится
        ни над свернутой панелью, ни над popup.
        """

        cursor_position = self.cursor().pos()

        over_panel = self.rect().contains(
            self.mapFromGlobal(cursor_position)
        )

        over_popup = self.popup.rect().contains(
            self.popup.mapFromGlobal(cursor_position)
        )

        if not over_panel and not over_popup:
            self.popup.hide()

class MyAxis(InteractiveAxisItem):#pg.AxisItem):
    def __init__(self, yticks = None,*args, **kwargs):
        self.labels = yticks or {}
        super().__init__(*args, **kwargs)

    def setTickLabel(self,yticks):
        self.labels = yticks or {}
    def tickStrings(self, values, scale, spacing):
        result = []
        for value in values:
            if value in self.labels:
                result.append(self.labels[value])
            else:
                result.append(f"{value:g}")

        return result
    

@dataclass
class PlotChannel:
    name: str
    color: str
    view_box: pg.ViewBox
    axis: pg.AxisItem
    curve: pg.PlotCurveItem


class MultiAxisPlot(QWidget): #(pg.PlotWidget):
    """
    График с общей осью X и отдельной осью Y для каждого канала.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # self.plot_widget = pg.PlotWidget()
        shared_view = SharedDragViewBox(enableMenu=True)

        self.plot_widget = pg.PlotWidget(
            viewBox=shared_view,
        )

        self.plot_item = self.plot_widget.getPlotItem()
        self.date_axis = pg.DateAxisItem(
            orientation="bottom",
            utcOffset=0,
        )
        self.plot_item.setAxisItems({"bottom": self.date_axis})
        self.date_axis.setLabel("Дата и время")
        self.main_view = self.plot_item.getViewBox()
        self.main_view.setZValue(100)
        self.plot_item = self.plot_widget.getPlotItem()
        self.main_view = self.plot_item.getViewBox()
        self.selected_main_view = self.main_view
        self.main_axis = MyAxis(orientation =  "left")#self.plot_item.getAxis("left")# 
        self.plot_item.setAxisItems({"left":self.main_axis})
        #self.plot_item.getAxis("left")
        # # # self.plot_item = self.getPlotItem()
        # # # self.main_view = self.plot_item.getViewBox()

        self.channels: list[PlotChannel] = []
        self.extra_views: list[pg.ViewBox] = []

        self.plot_item.showGrid(x=True, y=True, alpha=0.25)
        self.main_view.sigResized.connect(self._sync_view_geometry)

        # # # self.axes_panel = CollapsibleAxesPanel()

        # # # # container = QWidget(self)
        # # # layout = QVBoxLayout(self)
        # # # layout.setContentsMargins(0, 0, 0, 0)
        # # # layout.setSpacing(0)

        # # # layout.addWidget(self.axes_panel)
        # # # # layout.addItem(self.plot_item)
        self.axes_panel = CollapsibleAxesPanel(self)
        self.axes_popup = self.axes_panel.popup
        self.axes_popup.hide()

        self.main_view_combo = QComboBox(self)
        self.main_view_combo.setMinimumWidth(220)
        self.main_view_combo.setEnabled(False)
        self.main_view_combo.setToolTip(
            "Выберите канал, диапазон которого отображает главная левая ось"
        )
        self.main_view_combo.currentIndexChanged.connect(
            self._on_main_view_changed
        )

        selector_layout = QHBoxLayout()
        selector_layout.setContentsMargins(6, 6, 6, 2)
        selector_layout.addStretch(1)
        selector_layout.addWidget(QLabel("Главная левая ось:"))
        selector_layout.addWidget(self.main_view_combo)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self.axes_panel, 0)
        content_layout.addWidget(self.axes_popup, 0)
        content_layout.addWidget(self.plot_widget, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(selector_layout)
        layout.addLayout(content_layout, 1)

    def add_channel(
        self,
        name: str,
        color: str,
        x: np.ndarray,
        y: np.ndarray,
        yticks : dict = None
    ) -> int:
        channel_index = len(self.channels)

        if channel_index == 0:
            # Первый канал использует основной ViewBox и левую ось.
            view_box = self.main_view
            axis =MyAxis(yticks = yticks, orientation =  "left")#self.plot_item.getAxis("left")# 
            # self.plot_item.setAxisItems({"left":axis})
            # axis.linkToView(view_box)
            axis2 = self.plot_item.getAxis("left")# 
            # axis.setLabel(name, color=color)

            curve = pg.PlotCurveItem(
                x=x,
                y=y,
                pen=pg.mkPen(color, width=2),
            )

            view_box.addItem(curve)

        else:
            # Каждый последующий канал получает собственный ViewBox.
            view_box = pg.ViewBox(enableMenu=True)
            view_box.setZValue(0)
            self.plot_item.scene().addItem(view_box)

            # У всех каналов общая ось X.
            view_box.setXLink(self.main_view)
            self.main_view.add_y_view(view_box)
            if channel_index == 1:
                # Для второго канала используем встроенную правую ось.
                # self.plot_item.showAxis("left")
                # axis = self.plot_item.getAxis("left")
                # if yticks:
                #             yticks={int(b):a for a,b in list(yticks.items())}
                axis = MyAxis(yticks = yticks, orientation = "left", hit_padding=0,)#pg.AxisItem("left")
            else:
                # Для остальных добавляем дополнительные оси справа.
                # axis2 = InteractiveAxisItem(
                #             orientation = 'right',
                #             hit_padding=30,
                #         )
                # if yticks:
                #             yticks={int(b):a for a,b in list(yticks.items())}
                axis2 = MyAxis(yticks = yticks, orientation = "right",hit_padding=0,)#pg.AxisItem("right")
                
                # В стандартной разметке PlotItem:
                # column 2 — встроенная правая ось,
                # column 3 и далее — дополнительные оси.
                # layout_column = channel_index + 1
                

                # self.plot_item.layout.addItem(axis2, 2, layout_column)
                axis = axis2
            axis.linkToView(view_box)
            
            axis.setLabel(name, color=color)

            curve = pg.PlotCurveItem(
                x=x,
                y=y,
                pen=pg.mkPen(color, width=2),
            )
            
            view_box.addItem(curve)
            self.extra_views.append(view_box)

        channel = PlotChannel(
            name=name,
            color=color,
            view_box=view_box,
            axis=axis,
            curve=curve,
        )
        # if yticks:
        #     axis.setTicks([[(int(b),a) for a,b in list(yticks.items())]])
        self.axes_panel.add_axis(
    name=name,
    color=color,
    view_box=view_box,
    yticks = yticks
)
        self.channels.append(channel)

        self.main_view_combo.addItem(name, channel_index)
        combo_index = self.main_view_combo.count() - 1
        self.main_view_combo.setItemData(
            combo_index,
            QColor(color),
            Qt.ItemDataRole.ForegroundRole,
        )
        self.main_view_combo.setEnabled(True)

        if channel_index == 0:
            self.set_main_view(channel_index)

        self._sync_view_geometry()
        view_box.enableAutoRange(axis=pg.ViewBox.YAxis)
        maximum = max(x)
                
        minimum = min(x)
        

        self.main_view.setXRange(minimum, maximum, padding=0)
        return channel_index

    def _on_main_view_changed(self, combo_index: int) -> None:
        channel_index = self.main_view_combo.itemData(combo_index)
        if channel_index is None:
            return
        self._apply_main_view(int(channel_index))

    def set_main_view(self, channel_index: int) -> None:
        """Select which channel is represented by the main left Y axis."""
        if not 0 <= channel_index < len(self.channels):
            raise IndexError("channel_index находится вне диапазона каналов")

        combo_index = self.main_view_combo.findData(channel_index)
        if combo_index < 0:
            raise ValueError("Канал отсутствует в списке выбора главной оси")

        if self.main_view_combo.currentIndex() != combo_index:
            self.main_view_combo.setCurrentIndex(combo_index)
            return

        self._apply_main_view(channel_index)

    def _apply_main_view(self, channel_index: int) -> None:
        channel = self.channels[channel_index]
        self.selected_main_view = channel.view_box

        self.main_axis.linkToView(channel.view_box)
        self.main_axis.setLabel(channel.name, color=channel.color)
        self.main_axis.setPen(pg.mkPen(channel.color))
        self.main_axis.setTextPen(pg.mkPen(channel.color))
        self.main_axis.setRange(*channel.view_box.viewRange()[1])
        self.main_axis.setTickLabel(yticks= channel.axis.labels)
        self.plot_item.showAxis("left")

    def _sync_view_geometry(self) -> None:
        """
        Дополнительные ViewBox должны точно совпадать с областью
        основного ViewBox.
        """
        rect = self.main_view.sceneBoundingRect()

        for view_box in self.extra_views:
            view_box.setGeometry(rect)
            view_box.linkedViewChanged(
                self.main_view,
                pg.ViewBox.XAxis,
            )

    def set_y_range(
        self,
        channel_index: int,
        minimum: float,
        maximum: float,
    ) -> None:
        """
        Явно задаёт диапазон отдельной оси Y.
        """
        channel = self.channels[channel_index]

        channel.view_box.disableAutoRange(axis=pg.ViewBox.YAxis)
        channel.view_box.setYRange(
            minimum,
            maximum,
            padding=0,
        )

    def set_scale_and_zero_position(
        self,
        channel_index: int,
        units_per_division: float,
        zero_position: float = 0.5,
        division_count: int = 10,
    ) -> None:
        """
        units_per_division:
            Количество единиц данных на одно условное деление графика.

        zero_position:
            Положение нуля по высоте:
            0.0 — внизу;
            0.5 — посередине;
            1.0 — вверху.
        """
        if units_per_division <= 0:
            raise ValueError("units_per_division должен быть больше нуля")

        if not 0.0 <= zero_position <= 1.0:
            raise ValueError("zero_position должен находиться в диапазоне 0..1")

        full_range = units_per_division * division_count

        minimum = -zero_position * full_range
        maximum = (1.0 - zero_position) * full_range

        self.set_y_range(
            channel_index,
            minimum,
            maximum,
        )

    def set_data(
        self,
        channel_index: int,
        x: np.ndarray,
        y: np.ndarray,
        yticks : dict = None
    ) -> None:
        self.channels[channel_index].curve.setData(x, y)
        # if yticks:
        #    self.channels[channel_index].axis.setTicks([[(int(b),a) for a,b in list(yticks.items())]])
        maximum = max(x)
        minimum = min(x)
        self.main_view.setXRange(minimum, maximum, padding=0)


def main() -> None:
    app = QApplication(sys.argv)

    x = np.linspace(0, 10, 2000)

    plot = MultiAxisPlot()
    plot.resize(1100, 600)
    plot.setWindowTitle("Отдельная ось Y для каждой линии")

    voltage = 2.0 * np.sin(x)
    temperature = 50.0 + 20.0 * np.sin(x * 0.4)
    pressure = 1000.0 + 100.0 * np.cos(x * 0.7)
    pressure2 = 100.0 + 100.0 * np.cos(x * 0.2)
    pressure3 = 200.0 + 100.0 * np.cos(x * 0.9)
    pressure4 = 150.0 + 50.0 * np.cos(x * 1.7)
    voltage_channel = plot.add_channel(
        "Напряжение, В",
        "#e74c3c",
        x,
        voltage,
    )

    temperature_channel = plot.add_channel(
        "Температура, °C",
        "#3498db",
        x,
        temperature,
    )
    # temperature_channel = plot.add_channel(
    #         "pressure2, °C",
    #         "#3498db",
    #         x,
    #         pressure2,
    #     )
    # temperature_channel = plot.add_channel(
    #         "pressure3, °C",
    #         "#3498db",
    #         x,
    #         pressure3,
    #     )
    # temperature_channel = plot.add_channel(
    #         "pressure4, °C",
    #         "#3498db",
    #         x,
    #         pressure4,
    #     )
    pressure_channel = plot.add_channel(
        "Давление, кПа",
        "#2ecc71",
        x,
        pressure,
    )

    # Ноль посередине, диапазон примерно -5...+5.
    plot.set_scale_and_zero_position(
        voltage_channel,
        units_per_division=1.0,
        zero_position=0.5,
    )

    # Ноль ниже видимой области; удобно для данных около 50.
    plot.set_y_range(
        temperature_channel,
        minimum=0,
        maximum=100,
    )

    plot.set_y_range(
        pressure_channel,
        minimum=800,
        maximum=1200,
    )

    plot.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    
    main()
