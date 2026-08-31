from __future__ import annotations

from krita import DockWidget, Krita

from .controller import GapFillController
from .engine.colors import rgb_to_hex
from .engine.types import ModelBoundaryMode
from .krita_adapter import iter_nodes, node_label
from .qt_compat import (
    USER_ROLE,
    QAbstractItemView,
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from .settings import GapFillSettings


class GapFillDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("gapfill_krita_docker")
        self.setWindowTitle("GapFill")
        self.settings = GapFillSettings.load()
        self.controller = GapFillController(self)
        self._build_ui()
        self.refresh_layers()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        intro = QLabel(
            "Detect enclosed transparent gaps, preview model suggestions, then correct or apply them."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.coloring_combo = QComboBox()
        self.line_combo = QComboBox()
        self.guides_combo = QComboBox()
        self.model_mode_combo = QComboBox()
        self.model_mode_combo.addItem(
            "Line only", ModelBoundaryMode.LINE_ONLY.value
        )
        self.model_mode_combo.addItem(
            "Line + Guides", ModelBoundaryMode.LINE_OR_GUIDES.value
        )
        mode_index = self.model_mode_combo.findData(
            self.settings.model_boundary_mode.value
        )
        self.model_mode_combo.setCurrentIndex(max(0, mode_index))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10_000_000)
        self.threshold_spin.setValue(self.settings.threshold)
        self.threshold_spin.setSuffix(" px")
        self.greedy_check = QCheckBox("Fallback only when an individual prediction fails")
        self.greedy_check.setChecked(self.settings.allow_per_gap_greedy_fallback)
        form.addRow("Coloring:", self.coloring_combo)
        form.addRow("Line Art:", self.line_combo)
        form.addRow("Guides:", self.guides_combo)
        form.addRow("Model input:", self.model_mode_combo)
        form.addRow("Maximum gap size:", self.threshold_spin)
        layout.addLayout(form)
        model_help = QLabel(
            "Line Art and Guides always define detection topology. "
            "Line + Guides also supplies Guides to prediction; the model's "
            "canonical training input is Line-only."
        )
        model_help.setWordWrap(True)
        layout.addWidget(model_help)
        layout.addWidget(self.greedy_check)

        scan_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Layers")
        self.scan_button = QPushButton("Scan / Activate")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        scan_row.addWidget(self.refresh_button)
        scan_row.addWidget(self.scan_button)
        scan_row.addWidget(self.stop_button)
        layout.addLayout(scan_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("GapFill is inactive.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.region_list = QListWidget()
        selection_mode = (
            QAbstractItemView.SelectionMode.ExtendedSelection
            if hasattr(QAbstractItemView, "SelectionMode")
            else QAbstractItemView.ExtendedSelection
        )
        self.region_list.setSelectionMode(selection_mode)
        self.region_list.setMinimumHeight(140)
        layout.addWidget(self.region_list)

        apply_row = QHBoxLayout()
        self.color_button = QPushButton("Correct Color…")
        self.apply_selected_button = QPushButton("Apply Selected")
        self.apply_all_button = QPushButton("Apply All")
        apply_row.addWidget(self.color_button)
        apply_row.addWidget(self.apply_selected_button)
        apply_row.addWidget(self.apply_all_button)
        layout.addLayout(apply_row)

        self.deactivate_button = QPushButton("Deactivate GapFill")
        layout.addWidget(self.deactivate_button)
        layout.addStretch(1)
        self.setWidget(root)

        self.refresh_button.clicked.connect(self.refresh_layers)
        self.scan_button.clicked.connect(self._scan)
        self.stop_button.clicked.connect(self.controller.cancel)
        self.color_button.clicked.connect(self._correct_selected)
        self.apply_selected_button.clicked.connect(self._apply_selected)
        self.apply_all_button.clicked.connect(self.controller.apply_all)
        self.deactivate_button.clicked.connect(self.controller.deactivate)
        self.region_list.itemDoubleClicked.connect(lambda _item: self._correct_selected())
        self.model_mode_combo.currentIndexChanged.connect(
            self._model_boundary_mode_changed
        )
        self._update_action_state()

    def canvasChanged(self, _canvas) -> None:
        self.controller.canvas_changed()
        self.refresh_layers()

    def closeEvent(self, event) -> None:
        self.controller.shutdown()
        self._save_settings()
        super().closeEvent(event)

    def current_settings(self) -> GapFillSettings:
        self.settings.threshold = self.threshold_spin.value()
        self.settings.allow_per_gap_greedy_fallback = self.greedy_check.isChecked()
        self.settings.model_boundary_mode = self.selected_model_boundary_mode()
        return self.settings

    def selected_model_boundary_mode(self) -> ModelBoundaryMode:
        value = str(self.model_mode_combo.currentData())
        try:
            return ModelBoundaryMode(value)
        except ValueError:
            return ModelBoundaryMode.LINE_ONLY

    def _model_boundary_mode_changed(self, _index: int) -> None:
        mode = self.selected_model_boundary_mode()
        self.settings.model_boundary_mode = mode
        self.settings.save()
        self.controller.model_boundary_mode_changed(mode)

    def _save_settings(self) -> None:
        self.current_settings().save()

    def refresh_layers(self) -> None:
        document = Krita.instance().activeDocument()
        combos = (self.coloring_combo, self.line_combo, self.guides_combo)
        previous = [combo.currentData() for combo in combos]
        for combo in combos:
            combo.clear()
        self.guides_combo.addItem("(None)", None)
        if document is None:
            self.set_status("Open a document to select GapFill layers.")
            return

        nodes = list(iter_nodes(document.rootNode()))
        for node in nodes:
            label = node_label(node)
            if node.type() == "paintlayer":
                self.coloring_combo.addItem(label, node)
            if node.colorModel() == "RGBA" and node.colorDepth() == "U8":
                self.line_combo.addItem(label, node)
                self.guides_combo.addItem(label, node)
        self._restore_or_guess(
            self.coloring_combo, previous[0], ("coloring", "color"), document.activeNode()
        )
        self._restore_or_guess(self.line_combo, previous[1], ("line art", "lineart", "lines"))
        self._restore_or_guess(self.guides_combo, previous[2], ("guides", "guide"), allow_none=True)

    @staticmethod
    def _restore_or_guess(combo, previous, names, fallback=None, allow_none=False) -> None:
        if previous is not None:
            for index in range(combo.count()):
                if combo.itemData(index) == previous:
                    combo.setCurrentIndex(index)
                    return
        for index in range(combo.count()):
            node = combo.itemData(index)
            if node is not None and node.name().strip().lower() in names:
                combo.setCurrentIndex(index)
                return
        if fallback is not None:
            for index in range(combo.count()):
                if combo.itemData(index) == fallback:
                    combo.setCurrentIndex(index)
                    return
        if allow_none:
            combo.setCurrentIndex(0)

    def _scan(self) -> None:
        self._save_settings()
        self.controller.deactivate()
        self.controller.scan(
            self.coloring_combo.currentData(),
            self.line_combo.currentData(),
            self.guides_combo.currentData(),
            self.threshold_spin.value(),
            self.greedy_check.isChecked(),
            self.selected_model_boundary_mode(),
        )

    def selected_ids(self) -> list[str]:
        return [str(item.data(USER_ROLE)) for item in self.region_list.selectedItems()]

    def _correct_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            self.set_status("Select one or more gaps to correct their color.")
            return
        current = QColor("#FF00FF")
        selected = set(ids)
        first = next((gap for gap in self.controller.gaps if gap.id in selected), None)
        if first and first.color:
            current = QColor(*first.color)
        color = QColorDialog.getColor(current, self, "Correct Gap Color")
        if color.isValid():
            self.controller.set_preview_color(ids, (color.red(), color.green(), color.blue()))

    def _apply_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            self.set_status("Select one or more gaps to apply.")
            return
        self.controller.apply_ids(ids)

    def set_regions(self, gaps) -> None:
        selected = set(self.selected_ids())
        self.region_list.clear()
        for gap in gaps:
            color = rgb_to_hex(gap.color) if gap.color else "unavailable"
            item = QListWidgetItem(
                f"{gap.id}  ·  {gap.kind.value}  ·  {gap.pixel_count} px  ·  {color}"
            )
            item.setData(USER_ROLE, gap.id)
            self.region_list.addItem(item)
            item.setSelected(gap.id in selected)
        self._update_action_state()

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.scan_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
        if message:
            self.set_status(message)

    def update_progress(self, stage: str, done: int, total: int) -> None:
        self.progress.setVisible(True)
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.set_status(f"{stage}: {done}/{total}")

    def set_status(self, message: str) -> None:
        self.status.setStyleSheet("")
        self.status.setText(message)

    def show_error(self, message: str) -> None:
        self.status.setStyleSheet("color: #d32f2f; font-weight: 600;")
        self.status.setText(message)

    def _update_action_state(self) -> None:
        has_regions = self.region_list.count() > 0
        self.color_button.setEnabled(has_regions)
        self.apply_selected_button.setEnabled(has_regions)
        self.apply_all_button.setEnabled(has_regions)
        self.deactivate_button.setEnabled(has_regions or self.controller.busy)
