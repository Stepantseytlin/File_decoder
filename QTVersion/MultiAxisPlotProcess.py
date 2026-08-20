from __future__ import annotations

import sys
from multiprocessing import Process, Queue
from queue import Empty

import numpy as np
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from multiplot import MultiAxisPlot
import pandas as pd
from datetime import datetime, timezone


def timestamp(value: str) -> float:
    return (
        datetime.strptime(value, "%d.%m.%Y %H:%M:%S.%f")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )

def _channel_arrays(channel_data):
    y_values = _numeric_values(channel_data["values"])
    yticks = channel_data["yticks"]
    dates = pd.to_datetime(
        channel_data["dates"],
        format="%d.%m.%Y %H:%M:%S.%f",
        errors="coerce",
    )

    valid = dates.notna() & np.isfinite(y_values)

    x_values = (
        dates.to_numpy(dtype="datetime64[ms]")
        .astype(np.int64)
        / 1000.0
    )

    return x_values[valid], y_values[valid],yticks

CHANNEL_COLORS = (
    "#e74c3c",
    "#3498db",
    "#2ecc71",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#ec407a",
    "#7f8c8d",
    "#00acc1",
)


def _numeric_values(values) -> np.ndarray:
    numeric_values = []
    for value in values:
        try:
            numeric_values.append(float(value))
        except (TypeError, ValueError, OverflowError):
            numeric_values.append(np.nan)
    return np.asarray(numeric_values, dtype=float)


class MultiAxisPlotController(QObject):
    def __init__(self, data_queue: Queue) -> None:
        super().__init__()
        self.data_queue = data_queue
        self.channel_names: list[str] = []
        self.window = self._create_window()

        self.data_polling = QTimer(self)
        self.data_polling.setInterval(100)
        self.data_polling.timeout.connect(self.check_updates)
        self.data_polling.start()

    @staticmethod
    def _create_window() -> MultiAxisPlot:
        window = MultiAxisPlot()
        window.resize(1100, 650)
        window.setWindowTitle("Мультиграфик параметров")
        window.show()
        return window

    def check_updates(self) -> None:
        latest_update = None
        while True:
            try:
                latest_update = self.data_queue.get_nowait()
            except Empty:
                break
            except (EOFError, OSError):
                QApplication.instance().quit()
                return

        if latest_update is None:
            return

        data = latest_update.get("data", {})
        if isinstance(data, dict):
            self.update_plot(data)

    def update_plot(self, data: dict) -> None:
        channel_names = list(data.keys())
        if channel_names != self.channel_names:
            self._rebuild_plot(data)
            return

        for channel_index, channel_name in enumerate(channel_names):
            #y_values = _numeric_values(data[channel_name])
            x_values,y_values,yticks = _channel_arrays(data[channel_name])#np.arange(y_values.size)
            self.window.set_data(channel_index, x_values, y_values, yticks)
        

    def _rebuild_plot(self, data: dict) -> None:
        previous_window = self.window
        self.window = self._create_window()
        self.channel_names = list(data.keys())

        for channel_index, channel_name in enumerate(self.channel_names):
            x_values,y_values, yticks= _channel_arrays(data[channel_name])#np.arange(y_values.size)
            color = CHANNEL_COLORS[channel_index % len(CHANNEL_COLORS)]
            self.window.add_channel(
                channel_name,
                color,
                x_values,
                y_values,
                yticks
            )
        previous_window.close()
        previous_window.deleteLater()


def MultiAxisPlotGuiProcess(data_queue: Queue) -> None:
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    controller = MultiAxisPlotController(data_queue)
    controller.check_updates()
    sys.exit(application.exec())


def runMultiAxisProcess(data_queue: Queue) -> Process:
    process = Process(
        target=MultiAxisPlotGuiProcess,
        args=(data_queue,),
    )
    process.start()
    return process
