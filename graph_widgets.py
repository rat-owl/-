"""공통 그래프 UI 헬퍼.

육상동물/육수생물/식물 탭에서 공통으로 쓰는 그래프 프레임, 설정 패널,
프로그램 기본값 적용 연결을 한 곳에서 관리한다. 실제 데이터 계산과
그래프 그리기(draw)는 각 탭 파일에 남기고, 여기서는 UI 뼈대만 담당한다.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox, QSplitter, QScrollArea,
    QFrame, QSizePolicy, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QTableWidget, QLabel, QPushButton,
)

from config import GRAPH_H, SETTINGS
from ui_shared import (
    CanvasGroupBox, ResizableCanvasFrame, GraphValueSlider,
    make_copy_graph_btn, apply_button_feedback,
)


class _CompactSettingsForm(QGridLayout):
    def __init__(self, pairs_per_row=3):
        super().__init__()
        self._pairs_per_row = max(1, int(pairs_per_row))
        self._row_count = 0
        self._column_counts = []
        self.setHorizontalSpacing(10)
        self.setVerticalSpacing(6)
        self.setContentsMargins(0, 0, 0, 0)
        for col in range(self._pairs_per_row * 2):
            self.setColumnStretch(col, 1 if col % 2 else 0)

    def addRow(self, label, widget, column=None):
        if column is not None:
            col = max(0, min(self._pairs_per_row - 1, int(column)))
            while len(self._column_counts) <= col:
                self._column_counts.append(0)
            row = self._column_counts[col]
            self._column_counts[col] += 1
            label_w = QLabel(str(label))
            label_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.addWidget(label_w, row, col * 2)
            self.addWidget(widget, row, col * 2 + 1)
            return
        row = self._row_count // self._pairs_per_row
        pair = self._row_count % self._pairs_per_row
        label_w = QLabel(str(label))
        label_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(label_w, row, pair * 2)
        self.addWidget(widget, row, pair * 2 + 1)
        self._row_count += 1


def apply_graph_default(parent_window, canvas, kind: str):
    """그래프 생성 직후, 최초 draw 전에 프로그램 기본값을 주입한다."""
    if parent_window and hasattr(parent_window, "apply_graph_default_before_draw"):
        parent_window.apply_graph_default_before_draw(canvas, kind)


def _center_scroll_area(sc):
    def _do_center():
        widget = sc.widget()
        if widget is None:
            return
        viewport = sc.viewport().size()
        hbar = sc.horizontalScrollBar()
        vbar = sc.verticalScrollBar()

        # 스크롤 범위의 정중앙이 아니라, 실제 뷰포트 중앙이
        # 캔버스 중앙을 보도록 오프셋을 계산한다.
        target_x = max(0, (widget.width() - viewport.width()) // 2)
        target_y = max(0, (widget.height() - viewport.height()) // 2)
        hbar.setValue(max(hbar.minimum(), min(hbar.maximum(), target_x)))
        vbar.setValue(max(vbar.minimum(), min(vbar.maximum(), target_y)))
    QTimer.singleShot(0, _do_center)


def make_title_controls(canvas, *, include_title=False, include_y_title=False, refresh_fn=None, parent=None):
    if not include_title and not include_y_title:
        return None
    w = QWidget(parent)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)

    def _add_line(placeholder, text, attr):
        ed = QLineEdit(text)
        ed.setFixedWidth(80)
        ed.setPlaceholderText(placeholder)
        ed.setStyleSheet("font-size:11px;")
        def _on_change(value):
            setattr(SETTINGS, attr, value)
            if callable(refresh_fn):
                refresh_fn()
            else:
                _refresh_or_draw(canvas)
        ed.textChanged.connect(_on_change)
        lay.addWidget(ed)
        return ed

    ed_title = _add_line("차트 제목", SETTINGS.chart_title, "chart_title") if include_title else None
    ed_y = _add_line("Y축 제목", SETTINGS.y_axis_title, "y_axis_title") if include_y_title else None
    w._title_edit = ed_title
    w._y_edit = ed_y
    return w


def attach_title_controls_to_table_group(tbl_grp, controls):
    if controls is None or tbl_grp is None or tbl_grp.layout() is None:
        return
    controls._attached_to_table = True
    lay = tbl_grp.layout()
    for i in range(lay.count()):
        item = lay.itemAt(i)
        row = item.layout() if item is not None else None
        if isinstance(row, QHBoxLayout):
            row.insertWidget(max(0, row.count() - 1), controls)
            return
    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(controls)
    lay.insertLayout(0, row)


def attach_title_controls_to_canvas_group(cv_grp, controls):
    """차트/Y축 제목 컨트롤을 캔버스 그룹 헤더(복사버튼 오른쪽)에 삽입한다."""
    if controls is None:
        return
    head = getattr(cv_grp, "_head_layout", None)
    if head is None:
        return
    controls._attached_to_canvas = True
    head.insertWidget(1, controls)


def make_save_graph_default_btn(canvas, group_title: str) -> "QPushButton":
    """Save the current canvas settings as the program default for this graph kind."""
    btn = QPushButton("💾  현재 설정 저장")
    btn.setFixedHeight(28)
    btn.setStyleSheet(
        "QPushButton{background:#FFF7ED;color:#EA580C;border:1px solid #FED7AA;"
        "border-radius:5px;font-size:12px;padding:2px 10px;}"
        "QPushButton:hover{background:#FFEDD5;}"
    )

    def _on_click():
        window = btn.window()
        save_fn = getattr(window, "_save_current_graph_default", None)
        if not callable(save_fn):
            return
        if save_fn(canvas, group_title):
            apply_button_feedback(btn, "저장 완료")

    btn.clicked.connect(_on_click)
    return btn


def auto_pie_side(radius, cfg):
    """파이 반지름과 라벨 거리 설정을 기준으로 필요한 정사각 프레임 크기를 계산한다."""
    offset = float((cfg or {}).get("pie_label_offset", getattr(SETTINGS, "pie_label_offset", 0.15)))
    side = int(360 + float(radius) * 170 + offset * 70)
    return max(300, min(900, side))


def set_pie_frame_to_radius(pie):
    """현재 파이 반지름 값에 맞춰 캔버스 프레임을 자동 조정한다."""
    frame = getattr(pie, "_frame", None)
    if frame is not None:
        frame.setFixedSize(auto_pie_side(getattr(pie, "_radius", SETTINGS.pie_radius), getattr(pie, "_cfg", {})),
                           auto_pie_side(getattr(pie, "_radius", SETTINGS.pie_radius), getattr(pie, "_cfg", {})))
        sc = getattr(pie, "_scroll_area", None)
        if sc is not None:
            _center_scroll_area(sc)


def wrap_canvas(
    title,
    canvas,
    *,
    alignment=Qt.AlignCenter,
    size_policy_ignored=True,
    default_size=None,
    min_w=300,
    min_h=200,
):
    """그래프 캔버스를 크기 조절 가능한 프레임과 스크롤 영역으로 감싼다."""
    grp = CanvasGroupBox(title)
    lay = QVBoxLayout(grp)
    lay.setContentsMargins(6, 14, 6, 6)
    lay.setSpacing(6)

    head = QHBoxLayout()
    head.setContentsMargins(0, 0, 0, 0)
    head.setAlignment(Qt.AlignVCenter)
    head.addWidget(make_copy_graph_btn(canvas))
    head.addStretch()
    head.addWidget(make_save_graph_default_btn(canvas, title))
    lay.addLayout(head)
    grp._head_layout = head

    frame = ResizableCanvasFrame(canvas, min_w=min_w, min_h=min_h)
    fallback_w = 720 if SETTINGS.graph_width_auto else SETTINGS.graph_width
    fallback_h = max(GRAPH_H, SETTINGS.graph_height)
    if default_size and len(default_size) == 2:
        fallback_w, fallback_h = int(default_size[0]), int(default_size[1])
    init_w = canvas._cfg.get("initial_graph_width", fallback_w)
    init_h = canvas._cfg.get("initial_graph_height", fallback_h)
    frame.setFixedSize(init_w, init_h)

    sc = QScrollArea()
    if size_policy_ignored:
        sc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
    sc.setWidgetResizable(False)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setStyleSheet("QScrollArea { border: none; background: transparent; }")
    sc.setWidget(frame)
    sc.setAlignment(alignment)
    lay.addWidget(sc, 1)

    grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    canvas._frame = frame
    canvas._scroll_area = sc
    frame.resized_sig.connect(lambda *_: _center_scroll_area(sc))
    sc.horizontalScrollBar().rangeChanged.connect(lambda *_: _center_scroll_area(sc))
    sc.verticalScrollBar().rangeChanged.connect(lambda *_: _center_scroll_area(sc))
    _center_scroll_area(sc)
    return grp


def make_settings_graph(panel_w, cv_grp, *, min_width=None, max_width=280, initial=(260, 720)):
    """설정 패널과 그래프 영역을 좌우 2분할 레이아웃으로 만든다."""
    spl = QSplitter(Qt.Horizontal)
    spl.setChildrenCollapsible(False)
    set_grp = QGroupBox("그래프 설정")
    if min_width is not None:
        set_grp.setMinimumWidth(int(min_width))
    if max_width is not None:
        set_grp.setMaximumWidth(int(max_width))
    set_lay = QVBoxLayout(set_grp)
    set_lay.setContentsMargins(6, 20, 6, 6)
    set_lay.addWidget(panel_w)
    set_grp.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    cv_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    spl.addWidget(set_grp)
    spl.addWidget(cv_grp)
    spl.setStretchFactor(0, 0)
    spl.setStretchFactor(1, 1)
    spl.setSizes(list(initial))
    return spl


def make_settings_below_graph(panel_w, cv_grp):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    controls = getattr(panel_w, "_title_controls", None)
    if (controls is not None
            and not getattr(controls, "_attached_to_canvas", False)
            and controls.parent() is not None
            and not getattr(controls, "_attached_to_table", False)):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()
        row.addWidget(controls)
        lay.addLayout(row)
    cv_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    lay.addWidget(cv_grp, 1)

    set_grp = QGroupBox("그래프 설정")
    set_lay = QVBoxLayout(set_grp)
    set_lay.setContentsMargins(8, 14, 8, 8)
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    sc.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    sc.setStyleSheet("QScrollArea { border: none; background: transparent; }")
    sc.setWidget(panel_w)
    set_lay.addWidget(sc)
    set_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    set_grp.setFixedHeight(190)
    lay.addWidget(set_grp, 0)
    return w


def _table_content_width(tbl_grp, *, extra=88, min_width=220, max_width=620):
    """표 컬럼 내용 기준으로 표 그룹이 필요한 최소 폭만 계산한다."""
    tables = tbl_grp.findChildren(QTableWidget)
    if not tables:
        return min_width
    tbl = tables[0]
    try:
        tbl.resizeColumnsToContents()
        width = tbl.verticalHeader().width() if tbl.verticalHeader() and tbl.verticalHeader().isVisible() else 0
        width += tbl.horizontalHeader().length()
        col_sum = 0
        for c in range(tbl.columnCount()):
            col_sum += max(tbl.columnWidth(c), tbl.sizeHintForColumn(c))
        width = max(width, col_sum)
        if tbl.verticalScrollBar() and tbl.verticalScrollBar().isVisible():
            width += tbl.verticalScrollBar().sizeHint().width()
        width += tbl.frameWidth() * 2
    except Exception:
        width = tbl.sizeHint().width()
    return max(int(min_width), min(int(max_width), int(width + extra)))


def _fix_table_group_width(tbl_grp, spl=None, *, panel_width=280, graph_width=860):
    tbl_w = _table_content_width(tbl_grp)
    tbl_grp.setFixedWidth(tbl_w)
    tbl_grp.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    if spl is not None:
        if spl.count() == 2:
            spl.setSizes([tbl_w, int(graph_width)])
        else:
            spl.setSizes([tbl_w, int(panel_width), int(graph_width)])
    return tbl_w


def make_triplet(
    tbl_grp,
    panel_w,
    cv_grp,
    *,
    panel_min=220,
    panel_max=280,
    sizes=(500, 240, 860),
    table_content_width=False,
    settings_position="side",
):
    """표, 그래프 설정, 그래프 영역을 좌우 3분할 레이아웃으로 만든다."""
    spl = QSplitter(Qt.Horizontal)
    spl.setChildrenCollapsible(False)
    set_grp = QGroupBox("그래프 설정")
    if settings_position == "bottom":
        if table_content_width:
            tbl_w = _fix_table_group_width(tbl_grp, panel_width=panel_max, graph_width=max(860, int(sizes[-1])))
        else:
            tbl_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 차트/Y축 제목 입력은 설정 패널에만 배치 (표 그룹 버튼 행에 추가하지 않음)
        graph_area = make_settings_below_graph(panel_w, cv_grp)
        graph_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        spl.addWidget(tbl_grp)
        spl.addWidget(graph_area)
        spl.setStretchFactor(0, 0)
        spl.setStretchFactor(1, 1)
        graph_w = max(860, int(sizes[-1]))
        if table_content_width:
            spl.setSizes([tbl_w, graph_w])
            QTimer.singleShot(0, lambda: _fix_table_group_width(tbl_grp, spl, panel_width=panel_max, graph_width=graph_w))
        else:
            spl.setSizes([int(sizes[0]), graph_w])
        return spl

    set_grp.setMinimumWidth(int(panel_min))
    set_grp.setMaximumWidth(int(panel_max))
    set_lay = QVBoxLayout(set_grp)
    set_lay.setContentsMargins(6, 20, 6, 6)
    set_lay.addWidget(panel_w)
    if table_content_width:
        tbl_w = _fix_table_group_width(tbl_grp, panel_width=panel_max, graph_width=max(860, int(sizes[-1])))
    else:
        tbl_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    set_grp.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    cv_grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    spl.addWidget(tbl_grp)
    spl.addWidget(set_grp)
    spl.addWidget(cv_grp)
    spl.setStretchFactor(0, 0)
    spl.setStretchFactor(1, 0)
    spl.setStretchFactor(2, 1)
    if table_content_width:
        graph_w = max(860, int(sizes[-1]))
        spl.setSizes([tbl_w, int(panel_max), graph_w])
        QTimer.singleShot(0, lambda: _fix_table_group_width(tbl_grp, spl, panel_width=panel_max, graph_width=graph_w))
    else:
        spl.setSizes(list(sizes))
    return spl


def _refresh_or_draw(canvas):
    """캔버스별 refresh 콜백이 있으면 우선 사용하고, 없으면 직접 다시 그린다."""
    cb = getattr(canvas, "_refresh_cb", None)
    if callable(cb):
        cb()
    elif hasattr(canvas, "_redraw"):
        canvas._redraw()
    else:
        canvas.draw()


def _silent_set(widget, value):
    blockers = []
    for obj in (widget, getattr(widget, "_sld", None)):
        if obj is None:
            continue
        try:
            blockers.append((obj, obj.blockSignals(True)))
        except Exception:
            pass
    try:
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            idx = widget.findData(value)
            widget.setCurrentIndex(idx if idx >= 0 else 0)
        elif isinstance(widget, QLineEdit):
            widget.setText("" if value is None else str(value))
        else:
            widget.setValue(value)
    finally:
        for obj, old in reversed(blockers):
            try:
                obj.blockSignals(old)
            except Exception:
                pass


def _register_settings_sync(canvas, callback):
    callbacks = getattr(canvas, "_settings_panel_sync_callbacks", None)
    if callbacks is None:
        callbacks = []
        canvas._settings_panel_sync_callbacks = callbacks
    callbacks.append(callback)

    def _sync_all():
        for cb in list(getattr(canvas, "_settings_panel_sync_callbacks", []) or []):
            if callable(cb):
                cb()

    canvas._sync_settings_panel = _sync_all


def make_pie_settings_panel(
    pie,
    *,
    include_title=False,
    title_text=None,
    radius_label="그래프 크기",
    refresh_fn=None,
    parent=None,
):
    """파이 그래프 공통 설정 패널을 만든다.

    저장 대상은 반지름, 글씨 크기, 지시선 표시 여부이며 수동 라벨 위치는
    작업 저장(taxa_settings.json)에서만 다루므로 여기서는 건드리지 않는다.
    """
    panel = QWidget(parent)
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(8, 12, 8, 8)
    lay.setSpacing(6)
    form = _CompactSettingsForm()

    ed_title = None
    if False and include_title:
        ed_title = QLineEdit(SETTINGS.chart_title if title_text is None else title_text)
        ed_title.setPlaceholderText("차트 제목")
        form.addRow("차트 제목:", ed_title)

    spin_fs = QSpinBox()
    spin_fs.setRange(4, 24)
    spin_fs.setValue(pie._cfg.get("pie_fontsize", SETTINGS.pie_fontsize))
    spin_fs.setSuffix(" pt")
    spin_r = GraphValueSlider(0.35, 1.5, getattr(pie, "_radius", SETTINGS.pie_radius), 0.05, 2)
    chk_leader = QCheckBox("지시선")
    chk_leader.setChecked(pie._cfg.get("pie_show_leaders", getattr(SETTINGS, "pie_show_leaders", True)))

    form.addRow("글씨 크기:", spin_fs)
    form.addRow(f"{radius_label}:", spin_r)
    form.addRow("지시선:", chk_leader)
    lay.addLayout(form)

    def _refresh():
        if ed_title is not None:
            SETTINGS.chart_title = ed_title.text()
        pie._radius = spin_r.value()
        pie._cfg["pie_fontsize"] = spin_fs.value()
        pie._cfg["pie_show_leaders"] = chk_leader.isChecked()
        set_pie_frame_to_radius(pie)
        if callable(refresh_fn):
            refresh_fn()
        else:
            _refresh_or_draw(pie)

    if ed_title is not None:
        ed_title.textChanged.connect(_refresh)
    spin_r.valueChanged.connect(_refresh)
    spin_fs.valueChanged.connect(_refresh)
    chk_leader.stateChanged.connect(_refresh)
    pie._radius_changed_cb = lambda r: spin_r.setValue(float(r))
    set_pie_frame_to_radius(pie)
    panel._title_controls = make_title_controls(
        pie,
        include_title=include_title,
        include_y_title=False,
        refresh_fn=refresh_fn if callable(refresh_fn) else None,
        parent=panel,
    )

    def _sync_from_canvas():
        cfg = getattr(pie, "_cfg", {}) or {}
        if ed_title is not None:
            _silent_set(ed_title, SETTINGS.chart_title if title_text is None else title_text)
        _silent_set(spin_fs, int(cfg.get("pie_fontsize", SETTINGS.pie_fontsize)))
        _silent_set(spin_r, float(getattr(pie, "_radius", SETTINGS.pie_radius)))
        _silent_set(chk_leader, bool(cfg.get("pie_show_leaders", getattr(SETTINGS, "pie_show_leaders", True))))

    _register_settings_sync(pie, _sync_from_canvas)
    _sync_from_canvas()

    lay.addStretch()
    return panel


def make_bar_settings_panel(
    canvas,
    *,
    mode="bar",
    include_title=False,
    include_y_title=False,
    show_direction=False,
    show_legend=False,
    show_sort=False,
    show_dom_pct=False,
    on_change=None,
    on_pct_change=None,
    use_vertical_width_scale=False,
    parent=None,
):
    """막대/우점도/다양도 그래프 공통 설정 패널을 만든다.

    mode와 show_* 옵션으로 탭별 차이를 켜고 끈다. 예를 들어 식물 그래프는
    show_margins=False로 호출해 여백 설정을 화면과 저장 흐름에서 제외한다.
    """
    panel = QWidget(parent)
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(8, 12, 8, 8)
    lay.setSpacing(6)
    form = _CompactSettingsForm()

    ed_title = QLineEdit(SETTINGS.chart_title) if include_title else None
    ed_y = QLineEdit(SETTINGS.y_axis_title) if include_y_title else None
    spin_pct = None
    if show_dom_pct:
        spin_pct = QDoubleSpinBox()
        spin_pct.setRange(0.1, 50.0)
        spin_pct.setDecimals(1)
        spin_pct.setSingleStep(0.5)
        spin_pct.setValue(float(canvas._cfg.get("dom_pct", SETTINGS.dom_pct)))
        spin_pct.setSuffix(" %")

    spin_fs = QSpinBox()
    spin_fs.setRange(6, 24)
    spin_fs.setValue(canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize))
    spin_fs.setSuffix(" pt")

    spin_bar_h = GraphValueSlider(0.20, 1.00, canvas._cfg.get("bar_h_height", SETTINGS.bar_h_height), 0.05, 2)
    spin_bar_w = GraphValueSlider(0.20, 0.95, canvas._cfg.get("bar_v_width", SETTINGS.bar_v_width), 0.05, 2)
    spin_div_w = GraphValueSlider(0.20, 0.90, canvas._cfg.get("div_bar_width", SETTINGS.div_bar_width), 0.05, 2)
    spin_div_gap = GraphValueSlider(0.50, 3.00, canvas._cfg.get("div_bar_gap", SETTINGS.div_bar_gap), 0.05, 2)
    spin_gw = GraphValueSlider(0.30, 1.10, canvas._cfg.get("graph_width_scale", 1.0), 0.05, 2)
    spin_gh = GraphValueSlider(0.30, 1.25, canvas._cfg.get("graph_height_scale", 1.0), 0.05, 2)

    cmb_horiz = QComboBox()
    cmb_horiz.addItem("가로", True)
    cmb_horiz.addItem("세로", False)
    cur_horiz = bool(canvas._cfg.get("bar_horiz", canvas._cfg.get("orientation", "horizontal") == "horizontal"))
    cmb_horiz.setCurrentIndex(0 if cur_horiz else 1)
    chk_legend = QCheckBox("")
    chk_legend.setChecked(canvas._cfg.get("show_legend", getattr(SETTINGS, "show_legend", True)))
    chk_legend.setToolTip("체크: 표시 / 해제: 숨김")
    chk_count_label = QCheckBox("")
    chk_count_label.setChecked(canvas._cfg.get("bar_count_label_inside", getattr(SETTINGS, "bar_count_label_inside", False)))
    chk_count_label.setToolTip("체크: 표시 / 해제: 숨김")
    cmb_sort = QComboBox()
    cmb_sort.addItem("내림차순", "desc")
    cmb_sort.addItem("오름차순", "asc")
    cur_sort = canvas._cfg.get("bar_sort", getattr(SETTINGS, "bar_sort", "desc"))
    cmb_sort.setCurrentIndex({"desc": 0, "asc": 1}.get(cur_sort, 0))

    left_rows = []
    mid_rows = []
    right_rows = []

    if ed_title is not None:
        ed_title.setPlaceholderText("차트 제목")
        left_rows.append(("차트 제목:", ed_title))
    if ed_y is not None:
        ed_y.setPlaceholderText("Y축 제목")
        left_rows.append(("Y축 제목:", ed_y))
    if spin_pct is not None:
        left_rows.append(("우점도:", spin_pct))
    left_rows.append(("글씨 크기:", spin_fs))

    if mode == "diversity":
        mid_rows.append(("막대 너비:", spin_div_w))
        mid_rows.append(("막대 간격:", spin_div_gap))
    else:
        if show_direction:
            mid_rows.append(("막대(가로):", spin_bar_h))
        mid_rows.append(("막대(세로):", spin_bar_w))
    mid_rows.append(("그래프 너비:", spin_gw))
    mid_rows.append(("그래프 높이:", spin_gh))

    if show_sort:
        right_rows.append(("정렬:", cmb_sort))
    if show_direction:
        right_rows.append(("방향:", cmb_horiz))
    if show_legend:
        right_rows.append(("범례:", chk_legend))
    if mode == "dominance":
        right_rows.append(("개체수:", chk_count_label))

    for label, widget in left_rows:
        form.addRow(label, widget, column=0)
    for label, widget in mid_rows:
        form.addRow(label, widget, column=1)
    for label, widget in right_rows:
        form.addRow(label, widget, column=2)

    lay.addLayout(form)

    def _refresh():
        if ed_title is not None:
            SETTINGS.chart_title = ed_title.text()
        if ed_y is not None:
            SETTINGS.y_axis_title = ed_y.text()
        if spin_pct is not None:
            SETTINGS.dom_pct = spin_pct.value()
            canvas._cfg["dom_pct"] = spin_pct.value()
        canvas._cfg["bar_fontsize"] = spin_fs.value()
        if mode == "diversity":
            canvas._cfg["div_bar_width"] = spin_div_w.value()
            canvas._cfg["div_bar_gap"] = spin_div_gap.value()
        else:
            canvas._cfg["bar_h_height"] = spin_bar_h.value()
            canvas._cfg["bar_v_width"] = spin_bar_w.value()
        if show_direction:
            horiz = bool(cmb_horiz.currentData())
            canvas._cfg["bar_horiz"] = horiz
            canvas._cfg["orientation"] = "horizontal" if horiz else "vertical"
        if show_legend:
            canvas._cfg["show_legend"] = chk_legend.isChecked()
        if mode == "dominance":
            canvas._cfg["bar_count_label_inside"] = chk_count_label.isChecked()
        if show_sort:
            canvas._cfg["bar_sort"] = cmb_sort.currentData()

        canvas._cfg["graph_width_scale"] = spin_gw.value()
        canvas._cfg["graph_height_scale"] = spin_gh.value()
        if spin_pct is not None and callable(on_pct_change):
            on_pct_change(spin_pct.value())
        if callable(on_change):
            on_change()
        else:
            _refresh_or_draw(canvas)

    for w in (ed_title, ed_y, spin_pct, spin_fs, spin_bar_h, spin_bar_w, spin_div_w, spin_div_gap, spin_gw, spin_gh):
        if w is None:
            continue
        if isinstance(w, QLineEdit):
            w.textChanged.connect(_refresh)
        else:
            w.valueChanged.connect(_refresh)
    cmb_horiz.currentIndexChanged.connect(_refresh)
    chk_legend.stateChanged.connect(_refresh)
    chk_count_label.stateChanged.connect(_refresh)
    cmb_sort.currentIndexChanged.connect(_refresh)

    panel._title_controls = None

    if mode == "diversity":
        canvas._bar_changed_cb = lambda: (
            spin_div_w.setValue(canvas._cfg.get("div_bar_width", SETTINGS.div_bar_width)),
            spin_div_gap.setValue(canvas._cfg.get("div_bar_gap", SETTINGS.div_bar_gap)),
        )
    else:
        canvas._bar_changed_cb = lambda: (
            spin_bar_h.setValue(canvas._cfg.get("bar_h_height", SETTINGS.bar_h_height)),
            spin_bar_w.setValue(canvas._cfg.get("bar_v_width", SETTINGS.bar_v_width)),
        )

    def _sync_from_canvas():
        cfg = getattr(canvas, "_cfg", {}) or {}
        if ed_title is not None:
            _silent_set(ed_title, SETTINGS.chart_title)
        if ed_y is not None:
            _silent_set(ed_y, SETTINGS.y_axis_title)
        if spin_pct is not None:
            _silent_set(spin_pct, float(cfg.get("dom_pct", SETTINGS.dom_pct)))
        _silent_set(spin_fs, int(cfg.get("bar_fontsize", SETTINGS.bar_fontsize)))
        _silent_set(spin_bar_h, float(cfg.get("bar_h_height", SETTINGS.bar_h_height)))
        _silent_set(spin_bar_w, float(cfg.get("bar_v_width", SETTINGS.bar_v_width)))
        _silent_set(spin_div_w, float(cfg.get("div_bar_width", SETTINGS.div_bar_width)))
        _silent_set(spin_div_gap, float(cfg.get("div_bar_gap", SETTINGS.div_bar_gap)))
        _silent_set(spin_gw, float(cfg.get("graph_width_scale", 1.0)))
        _silent_set(spin_gh, float(cfg.get("graph_height_scale", 1.0)))
        horiz = bool(cfg.get("bar_horiz", cfg.get("orientation", "horizontal") == "horizontal"))
        _silent_set(cmb_horiz, horiz)
        _silent_set(chk_legend, bool(cfg.get("show_legend", getattr(SETTINGS, "show_legend", True))))
        _silent_set(chk_count_label, bool(cfg.get("bar_count_label_inside", getattr(SETTINGS, "bar_count_label_inside", False))))
        _silent_set(cmb_sort, cfg.get("bar_sort", getattr(SETTINGS, "bar_sort", "desc")))


    _register_settings_sync(canvas, _sync_from_canvas)
    _sync_from_canvas()

    lay.addStretch()
    return panel
