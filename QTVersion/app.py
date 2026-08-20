from __future__ import annotations

import os
import sys
import threading
import traceback
import zipfile
from collections import Counter
from multiprocessing import Queue, freeze_support
from numbers import Number
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


# This file is one directory below the original application and its modules.
if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(sys.executable).resolve().parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from main import runProcess
from MultiAxisPlotProcess import runMultiAxisProcess
from modules.File_parser import ONE_FILE
from modules.LRU import LRU_CASH, Cash_Object
from modules.Rules import RULES
from modules.convert_to_canlog import convert

ROLE_KIND = int(Qt.ItemDataRole.UserRole)
ROLE_PROTOCOL = ROLE_KIND + 1
ROLE_PARAMETER = ROLE_KIND + 2
ROLE_PARAMETER_INDEX = ROLE_KIND + 3


class AppSignals(QObject):
    decode_ready = Signal(int, int, object, object)
    decode_failed = Signal(int, int, str)
    output_ready = Signal(int, str, str, object)
    output_failed = Signal(int, str, str)
    append_text = Signal(str)


class ProtocolDecoderApp(QMainWindow):
    """PySide6 version of the protocol decoder GUI."""

    TREE_BATCH_SIZE = 40

    def __init__(self) -> None:
        super().__init__()

        self.ParametersDetailsDATA: dict[str, list] = {}
        self.id: list = []
        self.appending = True
        self.Lock = threading.Lock()
        self.showThread: list[threading.Thread] = []
        self.parser: list[ONE_FILE] = []
        self.parser_thread: list[threading.Thread] = []
        self.OpenGL_Q = Queue()
        self.MultiPlot_Q = Queue()
        self.CASH = LRU_CASH(5)
        self.root = self

        self.display_buffer: list[str] = []
        self.export_dict: dict[str, list] = {
            "date": [],
            "parameter": [],
            "value": [],
        }
        self.to_excel = pd.DataFrame(columns=["date", "parameter", "value"])
        self.to_excel_list: list[tuple] = []
        self.protocol_path = ""
        self.binary_path = ""
        self.frames: list[list | None] = []
        self.frames_headers: list[QTreeWidgetItem] = []
        self.export_par_names = False
        self.THREADING = False
        self.collisions = True
        self.numProtocols = 0
        self.curSelection: list[str] = []

        self.process = None
        self.multi_plot_process = None
        self._protocol_windows: list[QDialog] = []
        self._parameter_details: dict[tuple[int, str], list] = {}
        self._current_parameter_requests: list[tuple[int, str]] = []
        self._cache_lock = threading.Lock()

        self._decode_generation = 0
        self._decode_disable_collisions = True
        self._decode_ready_indices: set[int] = set()
        self._decode_errors: dict[int, str] = {}
        self._next_protocol_to_populate = 0
        self._population_context: dict | None = None
        self._decoding_notice: QMessageBox | None = None
        
        self._output_generation = 0
        self._output_cancel: threading.Event | None = None

        self.die_text_box_thread = threading.Event()
        self.die_text_box_thread_complex_reject = threading.Event()
        self.thread_display_details = threading.Thread(daemon=True)
        self.thread_parse_parameters_info = threading.Thread(daemon=True)

        self.signals = AppSignals()
        self.signals.decode_ready.connect(self._on_decode_ready)
        self.signals.decode_failed.connect(self._on_decode_failed)
        self.signals.output_ready.connect(self._apply_output)
        self.signals.output_failed.connect(self._on_output_failed)
        self.signals.append_text.connect(self.append_to_textbox)

        self.create_widgets()

    def create_widgets(self) -> None:
        self.setWindowTitle("Protocol Decoder")
        self.resize(900, 800)
        self.setMinimumSize(720, 620)

        central = QWidget(self)
        central.setObjectName("centralPanel")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 18, 20, 16)
        main_layout.setSpacing(12)

        files_layout = QGridLayout()
        files_layout.setHorizontalSpacing(12)
        files_layout.setVerticalSpacing(8)

        self.protocol_button = QPushButton("Выбрать протокол шифрования")
        self.protocol_button.setObjectName("fileButton")
        self.protocol_button.clicked.connect(self.load_protocol)
        self.protocol_label = QLabel("Протокол не выбран")
        self.protocol_label.setObjectName("fileLabel")
        self.protocol_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        files_layout.addWidget(self.protocol_button, 0, 0)
        files_layout.addWidget(self.protocol_label, 0, 1)

        self.binary_button = QPushButton("Выбрать файл для расшифровки")
        self.binary_button.setObjectName("fileButton")
        self.binary_button.clicked.connect(self.load_binary)
        self.binary_label = QLabel("Файл не выбран")
        self.binary_label.setObjectName("fileLabel")
        self.binary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        files_layout.addWidget(self.binary_button, 1, 0)
        files_layout.addWidget(self.binary_label, 1, 1)
        files_layout.setColumnStretch(1, 1)
        main_layout.addLayout(files_layout)

        action_layout = QHBoxLayout()
        self.decode_button = QPushButton("Декодировать")
        self.decode_button.setObjectName("primaryButton")
        self.decode_button.clicked.connect(self.initiate_parallel_decode)
        self.disable_collisions = QCheckBox("Разрешить коллизии")
        self.disable_collisions.setObjectName("collisionCheckBox")
        self.Plot_bt = QPushButton("В редактор графика")
        self.Plot_bt.setObjectName("plotButton")
        self.Plot_bt.setProperty("active", False)
        self.Plot_bt.clicked.connect(self._toggle_plot_editor)
        self.MultiPlot_bt = QPushButton("В мультиграфик")
        self.MultiPlot_bt.setObjectName("multiPlotButton")
        self.MultiPlot_bt.setProperty("active", False)
        self.MultiPlot_bt.clicked.connect(self._toggle_multi_axis_plot)
        action_layout.addWidget(self.decode_button)
        action_layout.addWidget(self.disable_collisions)
        action_layout.addStretch(1)
        action_layout.addWidget(self.Plot_bt)
        action_layout.addWidget(self.MultiPlot_bt)
        main_layout.addLayout(action_layout)

        self.refresh_btn = QPushButton("Обновить данные в редакторе")
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.clicked.connect(self.refreshOpenGl)
        self.refresh_btn.hide()

        self.multi_plot_refresh_btn = QPushButton("Обновить данные в мультиграфике")
        self.multi_plot_refresh_btn.setObjectName("refreshButton")
        self.multi_plot_refresh_btn.clicked.connect(self.refreshMultiAxisPlot)
        self.multi_plot_refresh_btn.hide()

        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch(1)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addWidget(self.multi_plot_refresh_btn)
        main_layout.addLayout(refresh_layout)

        self.tree_of_frames = QTreeWidget()
        self.tree_of_frames.setObjectName("frameTree")
        self.tree_of_frames.setHeaderHidden(True)
        self.tree_of_frames.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        self.tree_of_frames.setUniformRowHeights(True)
        self.tree_of_frames.setAlternatingRowColors(True)
        self.tree_of_frames.itemSelectionChanged.connect(self.showAllthread)
        self.frames_branch = QTreeWidgetItem(["Фреймы"])
        self.frames_branch.setData(0, ROLE_KIND, "root")
        self.tree_of_frames.addTopLevelItem(self.frames_branch)
        self.frames_branch.setExpanded(True)

        self.text_box = QPlainTextEdit()
        self.text_box.setObjectName("outputBox")
        self.text_box.setReadOnly(True)
        self.text_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("contentSplitter")
        splitter.addWidget(self.tree_of_frames)
        splitter.addWidget(self.text_box)
        splitter.setSizes([300, 340])
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(splitter, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        self.show_all_button = QPushButton("Показать всё")
        self.show_all_button.setObjectName("showAllButton")
        self.show_all_button.clicked.connect(self.thread_display)
        self.export_button = QPushButton("Экспорт в Excel")
        self.export_button.setObjectName("exportButton")
        self.export_button.clicked.connect(self.export_to_excel)
        bottom_layout.addWidget(self.show_all_button)
        bottom_layout.addWidget(self.export_button)
        bottom_layout.addStretch(1)
        main_layout.addLayout(bottom_layout)

        self.statusBar().showMessage("Готово")
        self.setStyleSheet(
            """
            QMainWindow,
            QWidget#centralPanel {
                background-color: #f3f5f7;
            }

            QWidget {
                color: #18212b;
                font-family: "Segoe UI";
                font-size: 10pt;
                letter-spacing: 0px;
            }

            QPushButton {
                min-height: 34px;
                padding: 2px 14px;
                background-color: #ffffff;
                border: 1px solid #c6ced7;
                border-radius: 6px;
                color: #25313d;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #edf4f3;
                border-color: #6eaaa3;
                color: #0b5f58;
            }

            QPushButton:pressed {
                background-color: #dceae8;
                border-color: #438d85;
                padding-top: 3px;
            }

            QPushButton:focus {
                border: 2px solid #348f86;
            }

            QPushButton:disabled {
                background-color: #e7eaed;
                border-color: #d7dce1;
                color: #8c969f;
            }

            QPushButton#fileButton {
                min-width: 238px;
                text-align: left;
            }

            QPushButton#primaryButton {
                min-width: 142px;
                background-color: #0f766e;
                border-color: #0f766e;
                color: #ffffff;
            }

            QPushButton#primaryButton:hover {
                background-color: #0b655e;
                border-color: #084f4a;
                color: #ffffff;
            }

            QPushButton#primaryButton:pressed {
                background-color: #084f4a;
            }

            QPushButton#plotButton {
                background-color: #283746;
                border-color: #283746;
                color: #ffffff;
            }

            QPushButton#plotButton:hover {
                background-color: #35495b;
                border-color: #496379;
                color: #ffffff;
            }

            QPushButton#plotButton[active="true"] {
                background-color: #a44336;
                border-color: #a44336;
                color: #ffffff;
            }

            QPushButton#plotButton[active="true"]:hover {
                background-color: #8f352b;
                border-color: #762c24;
            }

            QPushButton#multiPlotButton {
                background-color: #3e6078;
                border-color: #3e6078;
                color: #ffffff;
            }

            QPushButton#multiPlotButton:hover {
                background-color: #4b748f;
                border-color: #5b88a5;
                color: #ffffff;
            }

            QPushButton#multiPlotButton[active="true"] {
                background-color: #a44336;
                border-color: #a44336;
                color: #ffffff;
            }

            QPushButton#multiPlotButton[active="true"]:hover {
                background-color: #8f352b;
                border-color: #762c24;
            }

            QPushButton#refreshButton {
                background-color: #fff8e7;
                border-color: #d3a642;
                color: #76540d;
            }

            QPushButton#refreshButton:hover {
                background-color: #f9edcc;
                border-color: #bd8b24;
                color: #5d4108;
            }

            QPushButton#showAllButton {
                min-width: 130px;
            }

            QPushButton#exportButton {
                min-width: 150px;
                background-color: #28764c;
                border-color: #28764c;
                color: #ffffff;
            }

            QPushButton#exportButton:hover {
                background-color: #1f633d;
                border-color: #194f31;
                color: #ffffff;
            }

            QLabel#fileLabel {
                min-height: 34px;
                padding: 0 12px;
                background-color: #ffffff;
                border: 1px solid #d4dae0;
                border-left: 3px solid #4b8f88;
                border-radius: 5px;
                color: #56616c;
            }

            QCheckBox#collisionCheckBox {
                spacing: 8px;
                padding: 6px 8px;
                color: #35414d;
                font-weight: 600;
            }

            QCheckBox#collisionCheckBox:hover {
                color: #0f6d65;
            }

            QCheckBox#collisionCheckBox::indicator {
                width: 17px;
                height: 17px;
            }

            QTreeWidget#frameTree {
                background-color: #ffffff;
                alternate-background-color: #f7f9fa;
                border: 1px solid #cbd2d9;
                border-radius: 6px;
                outline: 0;
                padding: 4px;
                selection-background-color: #cfe8e4;
                selection-color: #123b37;
            }

            QTreeWidget#frameTree::item {
                min-height: 24px;
                border: 0;
                padding: 1px 4px;
            }

            QTreeWidget#frameTree::item:hover {
                background-color: #e7f1ef;
                color: #174f49;
            }

            QTreeWidget#frameTree::item:selected {
                background-color: #cfe8e4;
                color: #123b37;
            }

            QPlainTextEdit#outputBox {
                background-color: #172129;
                border: 1px solid #263743;
                border-radius: 6px;
                padding: 8px;
                color: #dbe7e5;
                selection-background-color: #2c7c73;
                selection-color: #ffffff;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 10pt;
            }

            QSplitter#contentSplitter::handle {
                height: 8px;
                background-color: #f3f5f7;
                border-top: 1px solid #d6dce1;
                border-bottom: 1px solid #d6dce1;
            }

            QSplitter#contentSplitter::handle:hover {
                background-color: #bcd8d4;
                border-color: #78aaa4;
            }

            QScrollBar:vertical {
                width: 12px;
                margin: 2px;
                background-color: transparent;
            }

            QScrollBar::handle:vertical {
                min-height: 28px;
                background-color: #9ba8b2;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #69827f;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                height: 0;
                background: transparent;
            }
            QMessageBox{
            background-color: #e7f1ef;
                            color: #174f49;
            }
            QScrollBar:horizontal {
                height: 12px;
                margin: 2px;
                background-color: transparent;
            }

            QScrollBar::handle:horizontal {
                min-width: 28px;
                background-color: #9ba8b2;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #69827f;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                width: 0;
                background: transparent;
            }

            QStatusBar {
                background-color: #000000;
                border-top: 1px solid #d4dae0;
                color: #56616c;
            }

            QStatusBar::item {
                border: 0;
            }

            QToolTip {
                padding: 5px 8px;
                background-color: #25313d;
                border: 1px solid #4b5d6d;
                color: #ffffff;
            }
            """
        )

    def show_protocol(self) -> None:
        protocol_window = QDialog(self)
        protocol_window.setWindowTitle("Протокол")
        protocol_window.resize(520, 420)
        protocol_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        protocol_window.destroyed.connect(
            lambda: self._forget_protocol_window(protocol_window)
        )
        self._protocol_windows.append(protocol_window)
        protocol_window.show()

    def _forget_protocol_window(self, window: QDialog) -> None:
        if window in self._protocol_windows:
            self._protocol_windows.remove(window)

    def _toggle_plot_editor(self) -> None:
        if self.process is not None and self.process.is_alive():
            self.killOpenGl()
        else:
            self.openOpenGlProcess()

    def _toggle_multi_axis_plot(self) -> None:
        if (
            self.multi_plot_process is not None
            and self.multi_plot_process.is_alive()
        ):
            self.killMultiAxisPlot()
        else:
            self.openMultiAxisPlotProcess()

    def _selected_plot_dataframe(self) -> pd.DataFrame:
        selected_parameters_details: list[tuple] = []
        for protocol_index, parameter_name in self._current_parameter_requests:
            details = self._parameter_details.get((protocol_index, parameter_name), [])
            for detail in details:
                normalized = self._normalize_parameter_detail(detail, parameter_name)
                if normalized is not None:
                    selected_parameters_details.append(normalized)
        return pd.DataFrame(
            selected_parameters_details,
            columns=["date", "parameter", "value", "raw", "to_plot"],
        )

    def _plot_payload(self) -> dict | None:
        selected_data = self._selected_plot_dataframe()
        if selected_data.empty:
            return None

        self.to_excel = selected_data
        parameter_names = list(dict.fromkeys(self.curSelection))
        data_to_opengl = {}

        for parameter_name in parameter_names:
            rows = selected_data.loc[
                selected_data["parameter"] == parameter_name
            ]
            if rows["to_plot"][rows.index.start] == "raw":
                all = list(zip(rows["value"],rows["raw"]))
                unq = {int(b):a for a,b in all}
                yticks =unq
            else:
                yticks = None
            data_to_opengl[parameter_name] = {
                "dates": rows["date"].tolist(),
                "values": rows[rows["to_plot"][rows.index.start]].tolist(),
                "yticks" : yticks
            }



                                    # data_to_opengl = {
                                    #     parameter_name: selected_data.loc[
                                    #         selected_data["parameter"] == parameter_name, "value"
                                    #     ].tolist()
                                    #     for parameter_name in parameter_names
                                    # }
        return {"data": data_to_opengl}

    def openOpenGlProcess(self) -> None:
        payload = self._plot_payload()
        if payload is None:
            QMessageBox.critical(self, "Нечего экспортировать", "Данные не выбраны")
            return

        try:
            self.OpenGL_Q = Queue()
            self.process = runProcess(self.OpenGL_Q)
            self.OpenGL_Q.put(payload)
            self.Plot_bt.setText("Закрыть редактор")
            self._set_plot_button_active(True)
            self.refresh_btn.show()
        except Exception as exc:
            self.process = None
            QMessageBox.critical(self, "Ошибка редактора графика", str(exc))

    def refreshOpenGl(self) -> None:
        if self.process is None or not self.process.is_alive():
            self.killOpenGl()
            QMessageBox.warning(self, "Редактор графика", "Редактор уже закрыт")
            return

        payload = self._plot_payload()
        if payload is None:
            QMessageBox.critical(self, "Нечего экспортировать", "Данные не выбраны")
            return
        self.OpenGL_Q.put(payload)

    def killOpenGl(self) -> None:
        process = self.process
        self.process = None
        if process is not None:
            try:
                if process.is_alive():
                    process.kill()
                process.join(timeout=1)
            except (AssertionError, OSError, ValueError):
                pass
        self.Plot_bt.setText("В редактор графика")
        self._set_plot_button_active(False)
        self.refresh_btn.hide()

    def _set_plot_button_active(self, active: bool) -> None:
        self.Plot_bt.setProperty("active", active)
        self.Plot_bt.style().unpolish(self.Plot_bt)
        self.Plot_bt.style().polish(self.Plot_bt)
        self.Plot_bt.update()

    def openMultiAxisPlotProcess(self) -> None:
        payload = self._plot_payload()
        if payload is None:
            QMessageBox.critical(self, "Нечего отображать", "Данные не выбраны")
            return

        try:
            if self.multi_plot_process is not None:
                self.killMultiAxisPlot()
            self.MultiPlot_Q = Queue()
            self.multi_plot_process = runMultiAxisProcess(self.MultiPlot_Q)
            self.MultiPlot_Q.put(payload)
            self.MultiPlot_bt.setText("Закрыть мультиграфик")
            self._set_multi_plot_button_active(True)
            self.multi_plot_refresh_btn.show()
        except Exception as exc:
            self.killMultiAxisPlot()
            QMessageBox.critical(self, "Ошибка мультиграфика", str(exc))

    def refreshMultiAxisPlot(self) -> None:
        if (
            self.multi_plot_process is None
            or not self.multi_plot_process.is_alive()
        ):
            self.killMultiAxisPlot()
            QMessageBox.warning(self, "Мультиграфик", "Окно уже закрыто")
            return

        payload = self._plot_payload()
        if payload is None:
            QMessageBox.critical(self, "Нечего отображать", "Данные не выбраны")
            return
        self.MultiPlot_Q.put(payload)

    def killMultiAxisPlot(self) -> None:
        process = self.multi_plot_process
        self.multi_plot_process = None
        if process is not None:
            try:
                if process.is_alive():
                    process.kill()
                process.join(timeout=1)
            except (AssertionError, OSError, ValueError):
                pass
        self.MultiPlot_bt.setText("В мультиграфик")
        self._set_multi_plot_button_active(False)
        self.multi_plot_refresh_btn.hide()

    def _set_multi_plot_button_active(self, active: bool) -> None:
        self.MultiPlot_bt.setProperty("active", active)
        self.MultiPlot_bt.style().unpolish(self.MultiPlot_bt)
        self.MultiPlot_bt.style().polish(self.MultiPlot_bt)
        self.MultiPlot_bt.update()

    @Slot(str)
    def append_to_textbox(self, text: str) -> None:
        cursor = self.text_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.text_box.setTextCursor(cursor)

    def clearoutp(self) -> None:
        self.text_box.clear()

    def load_protocol(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите протокол шифрования",
            self.protocol_path or str(PROJECT_DIR),
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return

        try:
            RULES(path).read_protocol()
        except Exception:
            QMessageBox.critical(
                self,
                "Ошибка",
                "Проверьте формат файла протокола",
            )
            return

        if path != self.protocol_path:
            self._cancel_output_jobs()
            self.CASH.clear()
        self.protocol_path = path
        self.protocol_label.setText(f"Протокол: {os.path.basename(path)}")

    def load_binary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для расшифровки",
            self.binary_path or str(PROJECT_DIR),
            "Text files (*.txt);;All files (*);;Fin Files(*.bin)"
        )
        if not path:
            return

        if path != self.binary_path:
            self._cancel_output_jobs()
            self.CASH.clear()
        if path.split(".")[-1]=="bin":
            thread = threading.Thread(target = convert,args = (Path(path),Path(path.split(".")[0]+".txt")),)
            thread.start()
            # convert(Path(path),Path(path.split(".")[0]+".txt"),)
            path = path.split(".")[0]+".txt"
        self.binary_path = path
        self.binary_label.setText(f"Файл: {os.path.basename(path)}")

    def initiate_parallel_decode(self) -> None:
        if not self.protocol_path or not self.binary_path:
            QMessageBox.critical(self, "Ошибка", "Укажите оба файла")
            return

        self._cancel_output_jobs()
        self._decode_generation += 1
        generation = self._decode_generation
        self._decode_ready_indices.clear()
        self._decode_errors.clear()
        self._next_protocol_to_populate = 0
        self._population_context = None
        self.ParametersDetailsDATA.clear()
        self._parameter_details.clear()
        self._current_parameter_requests.clear()
        self.curSelection.clear()
        self.CASH.clear()
        self.clearoutp()
        self.to_excel = pd.DataFrame(columns=["date", "parameter", "value"])
        self.to_excel_list = []
        self.export_par_names = False

        self.tree_of_frames.blockSignals(True)
        while self.frames_branch.childCount():
            self.frames_branch.takeChild(0)
        self.tree_of_frames.blockSignals(False)

        try:
            first_parser = ONE_FILE(self.binary_path)
            first_parser.read_parameters(self.protocol_path)
            self.numProtocols = first_parser.CountProtocols()
            if self.numProtocols < 1:
                raise ValueError("В файле протокола не найдено ни одного протокола")

            self.parser = [first_parser]
            for protocol_index in range(1, self.numProtocols):
                parser = ONE_FILE(self.binary_path, protocol_index)
                parser.read_parameters(self.protocol_path)
                self.parser.append(parser)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка при декодировании",
                str(exc),
            )
            return

        self.frames = [None] * self.numProtocols
        self.parser_thread.clear()
        self._decode_disable_collisions = not self.disable_collisions.isChecked()
        self.collisions = self._decode_disable_collisions
        self.THREADING = False
        self._set_decode_controls_enabled(False)
        self.statusBar().showMessage("Идет расшифровка...")
        self._show_decoding_notice()

        for protocol_index in range(self.numProtocols):
            thread = threading.Thread(
                target=self.read_file,
                args=(protocol_index, generation),
                daemon=True,
                name=f"decode protocol {protocol_index + 1}",
            )
            self.parser_thread.append(thread)
            thread.start()

    def _show_decoding_notice(self) -> None:
        if self._decoding_notice is not None:
            self._decoding_notice.close()
        notice = QMessageBox(self)
        notice.setIcon(QMessageBox.Icon.Information)
        notice.setWindowTitle("Подождите")
        notice.setText("Идет расшифровка.")
        notice.setStandardButtons(QMessageBox.StandardButton.Ok)
        notice.setModal(False)
        notice.show()
        self._decoding_notice = notice

    def _close_decoding_notice(self) -> None:
        if self._decoding_notice is not None:
            self._decoding_notice.close()
            self._decoding_notice.deleteLater()
            self._decoding_notice = None

    def _set_decode_controls_enabled(self, enabled: bool) -> None:
        self.decode_button.setEnabled(enabled)
        self.protocol_button.setEnabled(enabled)
        self.binary_button.setEnabled(enabled)
        self.disable_collisions.setEnabled(enabled)

    def read_file(self, i: int = 0, generation: int | None = None) -> None:
        generation = self._decode_generation if generation is None else generation
        try:
            frames = self.parser[i].read_file(
                disable_collisions=self._decode_disable_collisions
            )
            details = self._collect_parameter_details(self.parser[i], frames)
            self.signals.decode_ready.emit(generation, i, frames, details)
        except Exception:
            self.signals.decode_failed.emit(
                generation,
                i,
                traceback.format_exc(),
            )

    @staticmethod
    def _collect_parameter_details(parser: ONE_FILE, frames: list) -> dict[str, list]:
        parameter_names = list(dict.fromkeys(parser.FRAME_TEMPLATE.names))
        details = {parameter_name: [] for parameter_name in parameter_names}
        for frame in frames:
            frame.structurize()
            for parameter_name in parameter_names:
                details[parameter_name].append(frame.named_frame_dict[parameter_name])
        return details

    @Slot(int, int, object, object)
    def _on_decode_ready(
        self,
        generation: int,
        protocol_index: int,
        frames: list,
        details: dict,
    ) -> None:
        if generation != self._decode_generation:
            return

        self.frames[protocol_index] = frames
        self._decode_ready_indices.add(protocol_index)
        self.ParametersDetailsDATA.update(details)
        for parameter_name, parameter_details in details.items():
            self._parameter_details[(protocol_index, parameter_name)] = parameter_details
        if len(frames) > 500:
            self.THREADING = True
        self.process_decoded(protocol_index)
        self._update_decode_notice_state()

    @Slot(int, int, str)
    def _on_decode_failed(
        self,
        generation: int,
        protocol_index: int,
        error: str,
    ) -> None:
        if generation != self._decode_generation:
            return

        self.frames[protocol_index] = []
        self._decode_ready_indices.add(protocol_index)
        self._decode_errors[protocol_index] = error
        QMessageBox.critical(
            self,
            "Ошибка при декодировании",
            f"Протокол {protocol_index + 1}:\n{error}",
        )
        self.process_decoded(protocol_index)
        self._update_decode_notice_state()

    def _update_decode_notice_state(self) -> None:
        if len(self._decode_ready_indices) == self.numProtocols:
            self._close_decoding_notice()

    def process_decoded(self, kk: int) -> None:
        del kk
        self._try_start_tree_population()

    def _try_start_tree_population(self) -> None:
        if self._population_context is not None:
            return

        while self._next_protocol_to_populate < self.numProtocols:
            protocol_index = self._next_protocol_to_populate
            if protocol_index not in self._decode_ready_indices:
                return
            if protocol_index in self._decode_errors:
                self._next_protocol_to_populate += 1
                continue

            self._population_context = {
                "generation": self._decode_generation,
                "protocol": protocol_index,
                "frame_index": 0,
            }
            QTimer.singleShot(0, self._populate_tree_batch)
            return

        self._finish_decoding_view()

    @Slot()
    def _populate_tree_batch(self) -> None:
        context = self._population_context
        if context is None:
            return
        if context["generation"] != self._decode_generation:
            self._population_context = None
            return

        protocol_index = context["protocol"]
        frames = self.frames[protocol_index] or []
        start = context["frame_index"]
        end = min(start + self.TREE_BATCH_SIZE, len(frames))

        self.tree_of_frames.setUpdatesEnabled(False)
        try:
            for frame_index in range(start, end):
                frame = frames[frame_index]
                frame_text = f"Фрейм {frame_index + 1}"
                if self.numProtocols > 1:
                    frame_text += f" по протоколу {protocol_index + 1}"
                frame_item = QTreeWidgetItem([frame_text + ":"])
                frame_item.setData(0, ROLE_KIND, "frame")
                frame_item.setData(0, ROLE_PROTOCOL, protocol_index)
                self.frames_branch.addChild(frame_item)

                decoded_lines = frame.display_decoded().splitlines()
                for parameter_index, line in enumerate(decoded_lines):
                    if not line:
                        continue
                    parameter_name = (
                        frame.names[parameter_index]
                        if parameter_index < len(frame.names)
                        else ""
                    )
                    parameter_item = QTreeWidgetItem([line])
                    parameter_item.setData(0, ROLE_KIND, "parameter")
                    parameter_item.setData(0, ROLE_PROTOCOL, protocol_index)
                    parameter_item.setData(0, ROLE_PARAMETER, parameter_name)
                    parameter_item.setData(0, ROLE_PARAMETER_INDEX, parameter_index)
                    frame_item.addChild(parameter_item)
        finally:
            self.tree_of_frames.setUpdatesEnabled(True)

        context["frame_index"] = end
        if end < len(frames):
            QTimer.singleShot(0, self._populate_tree_batch)
            return

        self._show_decode_summary(protocol_index)
        self._next_protocol_to_populate += 1
        self._population_context = None
        QTimer.singleShot(0, self._try_start_tree_population)

    def _show_decode_summary(self, protocol_index: int) -> None:
        errors = list(self.parser[protocol_index].ERRORS_dict.values())
        counts = Counter(errors)
        error_text = "\n".join(
            f"     ошибка {error} встречена {amount} раз"
            for error, amount in counts.items()
        )
        message = (
            f"Декодировано {self.parser[protocol_index].n_frames} фреймов. "
            f"В файле {len(errors)} ошибок :\n{error_text}"
        )
        QMessageBox.information(self, "Готово", message)

    def _finish_decoding_view(self) -> None:
        if len(self._decode_ready_indices) != self.numProtocols:
            return
        self.frames_branch.setExpanded(True)
        self._set_decode_controls_enabled(True)
        successful = self.numProtocols - len(self._decode_errors)
        self.statusBar().showMessage(
            f"Декодирование завершено: {successful} из {self.numProtocols} протоколов"
        )

    def _cancel_output_jobs(self) -> None:
        self._output_generation += 1
        if self._output_cancel is not None:
            self._output_cancel.set()
        self._output_cancel = None
        self.die_text_box_thread.set()

    def _begin_output_job(self) -> tuple[int, threading.Event]:
        self._cancel_output_jobs()
        self.die_text_box_thread.clear()
        cancel_event = threading.Event()
        self._output_cancel = cancel_event
        return self._output_generation, cancel_event

    @Slot()
    def showAllthread(self, event=None) -> None:
        del event
        selected_items = self.tree_of_frames.selectedItems()
        generation, cancel_event = self._begin_output_job()
        self.clearoutp()
        self.to_excel_list = []
        self.to_excel = pd.DataFrame(columns=["date", "parameter", "value"])
        self.export_par_names = False
        self._current_parameter_requests = []
        self.curSelection = []

        if not selected_items:
            return
        if any(item.data(0, ROLE_KIND) != "parameter" for item in selected_items):
            return

        requests: list[tuple[int, str]] = []
        for item in selected_items:
            protocol_index = int(item.data(0, ROLE_PROTOCOL))
            parameter_name = str(item.data(0, ROLE_PARAMETER))
            if parameter_name:
                requests.append((protocol_index, parameter_name))

        if not requests:
            return

        self._current_parameter_requests = requests
        self.curSelection = [parameter_name for _, parameter_name in requests]
        self.statusBar().showMessage("Подготовка выбранных параметров...")
        thread = threading.Thread(
            target=self._build_parameter_output,
            args=(generation, cancel_event, requests),
            daemon=True,
            name="displaying selected parameters",
        )
        self.thread_parse_parameters_info = thread
        self.showThread.append(thread)
        thread.start()

    def show_frame_details(
        self,
        i: int,
        name: str | None = None,
        num: int = 0,
        selection_=None,
    ) -> None:
        del num, selection_
        if name is None:
            return
        generation, cancel_event = self._begin_output_job()
        self._current_parameter_requests = [(i, name)]
        self.curSelection = [name]
        thread = threading.Thread(
            target=self._build_parameter_output,
            args=(generation, cancel_event, [(i, name)]),
            daemon=True,
            name=f"displaying selected parameter {name}",
        )
        self.thread_parse_parameters_info = thread
        thread.start()

    @staticmethod
    def _normalize_parameter_detail(
        detail,
        parameter_name: str,
    ) -> tuple | None:
        if not isinstance(detail, (tuple, list)):
            return None
        if len(detail) >= 3:
            return detail[0], detail[1], detail[2], detail[3], detail[4]
        if len(detail) == 2:
            return detail[0], parameter_name, detail[1]
        return None

    def _build_parameter_output(
        self,
        generation: int,
        cancel_event: threading.Event,
        requests: list[tuple[int, str]],
    ) -> None:
        try:
            text_parts: list[str] = []
            rows: list[tuple] = []
            with self._cache_lock:
                for protocol_index, parameter_name in requests:
                    if cancel_event.is_set():
                        return

                    cache_key = f"{protocol_index}:{parameter_name}"
                    cash_obj = self.CASH.get(cache_key)
                    if cash_obj.value and cash_obj.complete:
                        text_parts.append(cash_obj.text or "")
                        rows.extend(
                            (date, parameter_name, value)
                            for date, value in cash_obj.value
                        )
                        continue

                    cash_obj.value = []
                    cash_obj.text = ""
                    parameter_text = [f"Параметр:  {parameter_name}\n"]
                    details = self._parameter_details.get(
                        (protocol_index, parameter_name),
                        [],
                    )
                    for detail in details:
                        if cancel_event.is_set():
                            cash_obj.complete = False
                            return
                        normalized = self._normalize_parameter_detail(
                            detail,
                            parameter_name,
                        )
                        if normalized is None:
                            continue
                        date, _, value, raw, to_plot= normalized
                        cash_obj.value.append((date, value))
                        rows.append((date, parameter_name, value))
                        parameter_text.append(f"{date} {value}\n")

                    cash_obj.text = "".join(parameter_text)
                    cash_obj.complete = True
                    text_parts.append(cash_obj.text)

            if cancel_event.is_set():
                return
            self.signals.output_ready.emit(
                generation,
                "parameters",
                "".join(text_parts),
                rows,
            )
        except Exception:
            self.signals.output_failed.emit(
                generation,
                "Ошибка вывода параметров",
                traceback.format_exc(),
            )

    def display_details_thread(
        self,
        data: list,
        text: str,
        threads=None,
        num: int = 0,
    ) -> None:
        del data, threads, num
        self.signals.append_text.emit(text)

    def parse_parameters_thread(
        self,
        idx: int,
        cash_obj: Cash_Object,
        name: str,
        threads,
        i: int,
        num: int,
    ) -> None:
        del idx, cash_obj, threads, num
        generation, cancel_event = self._begin_output_job()
        self._build_parameter_output(generation, cancel_event, [(i, name)])

    def thread_display(self) -> None:
        if not self.frames or not any(self.frames):
            QMessageBox.critical(self, "Ошибка", "Нет фреймов для вывода.")
            return
        if len(self._decode_ready_indices) != self.numProtocols:
            QMessageBox.information(self, "Подождите", "Декодирование еще выполняется.")
            return

        generation, cancel_event = self._begin_output_job()
        self.clearoutp()
        self.statusBar().showMessage("Подготовка полного вывода...")
        thread = threading.Thread(
            target=self._build_all_output,
            args=(generation, cancel_event, list(range(self.numProtocols))),
            daemon=True,
            name="displaying all frames",
        )
        self.disp_thread = thread
        thread.start()

    def display_all_after(self, i: int) -> None:
        generation, cancel_event = self._begin_output_job()
        self._build_all_output(generation, cancel_event, [i])

    def display_all(self) -> None:
        self.thread_display()

    def _build_all_output(
        self,
        generation: int,
        cancel_event: threading.Event,
        protocol_indices: list[int],
    ) -> None:
        try:
            text_parts: list[str] = []
            export_dict = {"date": [], "parameter": [], "value": []}
            for protocol_index in protocol_indices:
                frames = self.frames[protocol_index] or []
                for frame_index, frame in enumerate(frames):
                    if cancel_event.is_set():
                        return
                    text_parts.append(f"Фрейм {frame_index + 1}\n")
                    for line in frame.display_decoded().split("\n"):
                        if cancel_event.is_set():
                            return
                        text_parts.append(f"{line}\n")
                        try:
                            parts = line.split(" ")
                            export_dict["date"].append(" ".join(parts[:2]))
                            export_dict["parameter"].append(parts[-3])
                            export_dict["value"].append(parts[-2])
                        except (IndexError, ValueError):
                            if export_dict["date"]:
                                export_dict["date"].pop()

            if cancel_event.is_set():
                return
            self.signals.output_ready.emit(
                generation,
                "all",
                "".join(text_parts),
                export_dict,
            )
        except Exception:
            self.signals.output_failed.emit(
                generation,
                "Ошибка полного вывода",
                traceback.format_exc(),
            )

    @Slot(int, str, str, object)
    def _apply_output(
        self,
        generation: int,
        mode: str,
        text: str,
        payload,
    ) -> None:
        if generation != self._output_generation:
            return

        self.text_box.setPlainText(text)
        if mode == "all":
            self.export_dict = payload
            self.to_excel = pd.DataFrame(payload)
            self.export_par_names = True
        else:
            self.to_excel_list = list(payload)
            self.to_excel = pd.DataFrame(
                self.to_excel_list,
                columns=["date", "parameter", "value"],
            )
            self.export_par_names = False
        self.statusBar().showMessage("Данные готовы")

    @Slot(int, str, str)
    def _on_output_failed(
        self,
        generation: int,
        title: str,
        error: str,
    ) -> None:
        if generation != self._output_generation:
            return
        QMessageBox.critical(self, title, error)
        self.statusBar().showMessage("Ошибка")

    def jointhread(self, threads: list[threading.Thread]) -> None:
        for thread in threads:
            if thread is threading.current_thread() or not thread.is_alive():
                continue
            if "displaying" in thread.name:
                thread.join()
        self.die_text_box_thread.clear()

    def _abort_any_textadditions_and_threads(self, aliveThreads=None) -> None:
        del aliveThreads
        self._cancel_output_jobs()
        if self.CASH.all_objects and self.CASH.head and not self.CASH.head.complete:
            try:
                self.CASH.abort()
            except (AttributeError, KeyError):
                pass

    def export_to_excel(self, par_name: bool = False) -> None:
        del par_name
        if not self.frames or not any(self.frames):
            QMessageBox.critical(self, "Ошибка", "Нет фреймов для экспорта.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт в Excel",
            str(PROJECT_DIR / "export.xlsx"),
            "Excel files (*.xlsx)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".xlsx"):
            save_path += ".xlsx"

        try:
            if self.export_par_names:
                self.to_excel = pd.DataFrame(self.export_dict)
            keys = ["date", "parameter", "value"] if self.export_par_names else [
                "date",
                "value",
            ]
            export_frame = self.to_excel[keys]
            try:
                export_frame.to_excel(save_path, index=False)
            except (ImportError, ModuleNotFoundError):
                self._write_basic_xlsx(export_frame, save_path)
            QMessageBox.information(
                self,
                "Успех",
                f"Экспортировано в {save_path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка экспорта", str(exc))

    @staticmethod
    def _xlsx_column_name(column_number: int) -> str:
        name = ""
        while column_number:
            column_number, remainder = divmod(column_number - 1, 26)
            name = chr(65 + remainder) + name
        return name

    @staticmethod
    def _xlsx_text(value) -> str:
        text = str(value)
        text = "".join(
            character
            for character in text
            if character in "\t\n\r" or ord(character) >= 32
        )
        return escape(text)

    @classmethod
    def _xlsx_cell(cls, reference: str, value) -> str:
        try:
            is_missing = bool(pd.isna(value))
        except (TypeError, ValueError):
            is_missing = False
        if is_missing:
            return f'<c r="{reference}"/>'
        if isinstance(value, bool):
            return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
        if isinstance(value, Number):
            return f'<c r="{reference}" t="n"><v>{value}</v></c>'

        text = cls._xlsx_text(value)
        return (
            f'<c r="{reference}" t="inlineStr">'
            f'<is><t xml:space="preserve">{text}</t></is></c>'
        )

    @classmethod
    def _write_basic_xlsx(cls, data: pd.DataFrame, save_path: str) -> None:
        """Write a simple workbook when pandas has no optional Excel engine."""
        rows: list[str] = []
        values = [tuple(data.columns)]
        values.extend(data.itertuples(index=False, name=None))
        for row_number, row_values in enumerate(values, start=1):
            cells = "".join(
                cls._xlsx_cell(
                    f"{cls._xlsx_column_name(column_number)}{row_number}",
                    value,
                )
                for column_number, value in enumerate(row_values, start=1)
            )
            rows.append(f'<row r="{row_number}">{cells}</row>')

        last_column = cls._xlsx_column_name(max(1, len(data.columns)))
        last_row = max(1, len(values))
        worksheet = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main">'
            f'<dimension ref="A1:{last_column}{last_row}"/>'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            f'<sheetData>{"".join(rows)}</sheetData>'
            '</worksheet>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
            'package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )
        package_relationships = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        workbook = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Данные" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        )
        workbook_relationships = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        )

        with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as workbook_file:
            workbook_file.writestr("[Content_Types].xml", content_types)
            workbook_file.writestr("_rels/.rels", package_relationships)
            workbook_file.writestr("xl/workbook.xml", workbook)
            workbook_file.writestr(
                "xl/_rels/workbook.xml.rels",
                workbook_relationships,
            )
            workbook_file.writestr("xl/worksheets/sheet1.xml", worksheet)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._decode_generation += 1
        self._cancel_output_jobs()
        self._close_decoding_notice()
        self.killOpenGl()
        self.killMultiAxisPlot()
        event.accept()


def main() -> int:
    freeze_support()
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    window = ProtocolDecoderApp()
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
