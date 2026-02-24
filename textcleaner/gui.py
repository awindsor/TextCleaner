from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class RunWorker(QThread):
    finished_ok = Signal(int, str)
    failed = Signal(str)

    def __init__(self, argv: list[str]):
        super().__init__()
        self.argv = argv

    def run(self) -> None:
        try:
            from .__main__ import main as cli_main

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                code = cli_main(self.argv)
            self.finished_ok.emit(code, output.getvalue())
        except BaseException as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextCleaner")
        self.resize(980, 720)
        self._worker: RunWorker | None = None
        self._row_widgets: dict[QWidget, list[QWidget]] = {}

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        grid = QGridLayout()
        layout.addLayout(grid)

        row = 0
        self.action_combo = QComboBox()
        self.action_combo.addItems(["clean", "validate", "reproduce"])
        self.action_combo.currentTextChanged.connect(self._refresh_visibility)
        grid.addWidget(QLabel("Action"), row, 0)
        grid.addWidget(self.action_combo, row, 1)
        row += 1

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["csv", "dir"])
        self.mode_combo.currentTextChanged.connect(self._refresh_visibility)
        grid.addWidget(QLabel("Mode"), row, 0)
        grid.addWidget(self.mode_combo, row, 1)
        row += 1

        self.input_csv = QLineEdit()
        input_csv_browse = self._browse_button(self.input_csv, "file")
        grid.addWidget(QLabel("Input CSV"), row, 0)
        grid.addWidget(self.input_csv, row, 1)
        grid.addWidget(input_csv_browse, row, 2)
        self._register_row(self.input_csv, row, [input_csv_browse], grid)
        row += 1

        self.text_column = QLineEdit("body")
        grid.addWidget(QLabel("Text Column"), row, 0)
        grid.addWidget(self.text_column, row, 1)
        self._register_row(self.text_column, row, [], grid)
        row += 1

        self.input_dir = QLineEdit()
        input_dir_browse = self._browse_button(self.input_dir, "dir")
        grid.addWidget(QLabel("Input Dir"), row, 0)
        grid.addWidget(self.input_dir, row, 1)
        grid.addWidget(input_dir_browse, row, 2)
        self._register_row(self.input_dir, row, [input_dir_browse], grid)
        row += 1

        self.output_csv = QLineEdit()
        output_csv_browse = self._browse_button(self.output_csv, "save_csv")
        grid.addWidget(QLabel("Output CSV"), row, 0)
        grid.addWidget(self.output_csv, row, 1)
        grid.addWidget(output_csv_browse, row, 2)
        self._register_row(self.output_csv, row, [output_csv_browse], grid)
        row += 1

        self.output_dir = QLineEdit()
        output_dir_browse = self._browse_button(self.output_dir, "dir")
        grid.addWidget(QLabel("Output Dir"), row, 0)
        grid.addWidget(self.output_dir, row, 1)
        grid.addWidget(output_dir_browse, row, 2)
        self._register_row(self.output_dir, row, [output_dir_browse], grid)
        row += 1

        self.cleaned_column = QLineEdit("cleaned_text")
        grid.addWidget(QLabel("Cleaned Column"), row, 0)
        grid.addWidget(self.cleaned_column, row, 1)
        self._register_row(self.cleaned_column, row, [], grid)
        row += 1

        self.extensions = QLineEdit(".txt")
        grid.addWidget(QLabel("Extensions"), row, 0)
        grid.addWidget(self.extensions, row, 1)
        self._register_row(self.extensions, row, [], grid)
        row += 1

        self.changelog_json = QLineEdit()
        changelog_json_browse = self._browse_button(self.changelog_json, "save_json")
        grid.addWidget(QLabel("Changelog JSON"), row, 0)
        grid.addWidget(self.changelog_json, row, 1)
        grid.addWidget(changelog_json_browse, row, 2)
        self._register_row(self.changelog_json, row, [changelog_json_browse], grid)
        row += 1

        self.changelog_md = QLineEdit()
        changelog_md_browse = self._browse_button(self.changelog_md, "save_md")
        grid.addWidget(QLabel("Changelog MD"), row, 0)
        grid.addWidget(self.changelog_md, row, 1)
        grid.addWidget(changelog_md_browse, row, 2)
        self._register_row(self.changelog_md, row, [changelog_md_browse], grid)
        row += 1

        self.target_charset = QComboBox()
        self.target_charset.addItems(["utf-8", "latin-1", "ascii"])
        grid.addWidget(QLabel("Target Charset"), row, 0)
        grid.addWidget(self.target_charset, row, 1)
        self._register_row(self.target_charset, row, [], grid)
        row += 1

        self.input_encoding = QLineEdit("auto")
        grid.addWidget(QLabel("Input Encoding"), row, 0)
        grid.addWidget(self.input_encoding, row, 1)
        self._register_row(self.input_encoding, row, [], grid)
        row += 1

        self.strict_md5 = QCheckBox("Strict MD5 (reproduce)")
        self.strict_md5.setChecked(True)
        grid.addWidget(self.strict_md5, row, 1)
        row += 1

        self.spellcheck = QCheckBox("Enable pyenchant spellcheck")
        self.spellcheck.setChecked(True)
        grid.addWidget(self.spellcheck, row, 1)
        row += 1

        self.language = QLineEdit("en_US")
        grid.addWidget(QLabel("Spellcheck Language"), row, 0)
        grid.addWidget(self.language, row, 1)
        self._register_row(self.language, row, [], grid)
        row += 1

        self.max_distance = QSpinBox()
        self.max_distance.setRange(0, 10)
        self.max_distance.setValue(2)
        grid.addWidget(QLabel("Max Suggest Distance"), row, 0)
        grid.addWidget(self.max_distance, row, 1)
        self._register_row(self.max_distance, row, [], grid)

        button_row = QHBoxLayout()
        layout.addLayout(button_row)
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._on_run)
        button_row.addWidget(self.run_button)
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self._clear_log)
        button_row.addWidget(self.clear_log_button)
        button_row.addStretch(1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self._refresh_visibility()

    def _browse_button(self, field: QLineEdit, kind: str) -> QPushButton:
        button = QPushButton("Browse")

        def pick() -> None:
            if kind == "file":
                selected, _ = QFileDialog.getOpenFileName(self, "Select File")
            elif kind == "save_csv":
                selected, _ = QFileDialog.getSaveFileName(self, "Save CSV", filter="CSV Files (*.csv)")
            elif kind == "save_json":
                selected, _ = QFileDialog.getSaveFileName(self, "Save JSON", filter="JSON Files (*.json)")
            elif kind == "save_md":
                selected, _ = QFileDialog.getSaveFileName(self, "Save Markdown", filter="Markdown Files (*.md)")
            else:
                selected = QFileDialog.getExistingDirectory(self, "Select Directory")
            if selected:
                field.setText(selected)

        button.clicked.connect(pick)
        return button

    def _register_row(self, field: QWidget, row: int, extra_widgets: list[QWidget], grid: QGridLayout) -> None:
        label_item = grid.itemAtPosition(row, 0)
        widgets = [field]
        if label_item and label_item.widget() is not None:
            widgets.append(label_item.widget())
        widgets.extend(extra_widgets)
        self._row_widgets[field] = widgets

    def _set_row_visible(self, field: QWidget, visible: bool) -> None:
        widgets = self._row_widgets.get(field, [field])
        for widget in widgets:
            widget.setVisible(visible)

    def _refresh_visibility(self) -> None:
        action = self.action_combo.currentText()
        mode = self.mode_combo.currentText()

        is_csv = mode == "csv"
        is_clean = action == "clean"
        is_reproduce = action == "reproduce"
        needs_output = action in {"clean", "reproduce"}

        self._set_row_visible(self.input_csv, is_csv)
        self._set_row_visible(self.text_column, is_csv)
        self._set_row_visible(self.input_dir, not is_csv)

        self._set_row_visible(self.output_csv, is_csv and needs_output)
        self._set_row_visible(self.output_dir, (not is_csv) and needs_output)
        self._set_row_visible(self.cleaned_column, is_csv and needs_output)

        self._set_row_visible(self.changelog_json, True)
        self._set_row_visible(self.changelog_md, is_clean)
        self._set_row_visible(self.target_charset, is_clean)
        self._set_row_visible(self.input_encoding, True)
        self._set_row_visible(self.extensions, not is_csv)

        self.spellcheck.setVisible(is_clean)
        self._set_row_visible(self.language, is_clean)
        self._set_row_visible(self.max_distance, is_clean)

        self.strict_md5.setVisible(is_reproduce)

    def _append_log(self, text: str) -> None:
        if text:
            self.log.appendPlainText(text.rstrip())

    def _clear_log(self) -> None:
        self.log.clear()

    def _build_argv(self) -> list[str]:
        action = self.action_combo.currentText()
        mode = self.mode_combo.currentText()

        args = [action, "--mode", mode]
        if mode == "csv":
            args.extend(["--input-csv", self.input_csv.text().strip(), "--text-column", self.text_column.text().strip()])
        else:
            args.extend(["--input-dir", self.input_dir.text().strip(), "--extensions", self.extensions.text().strip()])

        if action in {"clean", "reproduce"}:
            if mode == "csv":
                args.extend(["--output-csv", self.output_csv.text().strip(), "--cleaned-column", self.cleaned_column.text().strip()])
            else:
                args.extend(["--output-dir", self.output_dir.text().strip()])

        args.extend(["--changelog-json", self.changelog_json.text().strip()])
        if action == "clean":
            args.extend(["--changelog-md", self.changelog_md.text().strip()])
            args.extend(["--target-charset", self.target_charset.currentText()])
            if not self.spellcheck.isChecked():
                args.append("--no-spellcheck")
            args.extend(["--language", self.language.text().strip()])
            args.extend(["--max-suggestion-distance", str(self.max_distance.value())])
        if action == "reproduce" and not self.strict_md5.isChecked():
            args.append("--no-strict-md5")

        args.extend(["--input-encoding", self.input_encoding.text().strip()])
        return args

    def _on_run(self) -> None:
        argv = self._build_argv()
        if "" in argv:
            QMessageBox.critical(self, "Missing Input", "Some required fields are empty.")
            return
        self.run_button.setEnabled(False)
        self._append_log("$ textcleaner " + " ".join(argv))
        self._worker = RunWorker(argv)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, code: int, output: str) -> None:
        self._append_log(output)
        self._append_log(f"[exit code: {code}]")
        self.run_button.setEnabled(True)

    def _on_fail(self, error: str) -> None:
        self._append_log(f"ERROR: {error}")
        self.run_button.setEnabled(True)
        QMessageBox.critical(self, "Run Failed", error)


def run_gui() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
