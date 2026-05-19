# taxa_window.py — 종목록 분석 뷰어 (bird_window / bug_window 스타일)
import sys, os, math, json, traceback
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import (
    QDialog,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QFrame, QSplitter, QSizePolicy, QApplication, QProgressBar,
    QLineEdit, QPlainTextEdit, QCheckBox, QDialogButtonBox,
    QListWidget, QListWidgetItem, QInputDialog, QToolButton, QColorDialog,
    QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox, QSlider,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMimeData, QObject, QEvent, QSettings
from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QCloseEvent

# ── 공통 설정 / UI 헬퍼 ───────────────────────────────────────────
from config import (
    _BG, _CARD, _BORDER, _TXT, _SUB, _PATH,
    _ACCENT, _ACCENT_D, _ACCENT_L, _SUCCESS, _WARN, _ERR,
    _FONT_EN, _FONT_KR, FF_KR, FF_EN, BD, BD1,
    SETTINGS, CHK_INDICATOR_QSS,
)
from ui_shared import (
    make_scroll_widget, make_copy_button,
    CopyableTableWidget,
    _item, _make_tbl, _auto_fit_table, SentenceSettingsDialog, _pct, _fmt, _int,
    install_global_no_focus_rect_style, normalize_tbl_pct_col, normalize_tbl_pct_row,
    CanvasGroupBox, CanvasSizeSlider, ResizableCanvasFrame, _Canvas, PieCanvas,
    lit_title_phrase_for_rounds,
)

from parser   import load_xlsx
from land_tab   import build_land_tab, _get_herp_group
from plant_tab  import build_plant_tab, make_vegetation_tab
from aqua_tab   import build_aqua_tab
from water_tab  import build_water_eval_tab
from shared import _has_present, _prot_list_graded, _prot_group_matches, _prot_grade_str, _ecosystem_disturber_list
from analyzer import (
    analyze_all, analyze_aquatic,
    TaxaStats, AquaticStats, PlantStats, PlantSpecialStats, ProtectedStats,
    DivStats, OrderStat, RoundStat,
)

def _round_survey_label(label: str) -> str:
    label = str(label or "").strip()
    if not label:
        return "조사"
    if "".join(label.split()).endswith("조사"):
        return label
    return f"{label} 조사"


def _parse_round_key_label(key: str) -> tuple[str, str, str, str]:
    parts = str(key or "").split("_", 2)
    sec = parts[0] if len(parts) > 0 else ""
    if len(parts) == 3:
        rnd, site = parts[1], parts[2]
    elif len(parts) == 2:
        rnd, site = parts[1], ""
    else:
        rnd, site = "", ""
    sec_label = "현지조사" if sec == "현지" else "문헌조사" if sec == "문헌" else sec or "기타"
    if site:
        detail = f"{rnd} / {site}"
    else:
        detail = rnd or key
    return sec, sec_label, detail, f"{sec_label} - {detail}"


def _infer_group_survey(rounds) -> str:
    for rn in rounds or []:
        sec = str(rn).split("_", 1)[0]
        if sec in ("현지", "문헌"):
            return sec
    return ""


class GroupSettingsDialog(QDialog):
    def __init__(self, groups: list, available_items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("그룹 설정")
        self.resize(760, 560)
        self._available_items = available_items
        self._groups = []
        for g in groups:
            if not g.get("name"):
                continue
            survey = g.get("survey") or _infer_group_survey(g.get("rounds", []))
            rounds = [r for r in list(g.get("rounds", [])) if not survey or str(r).startswith(f"{survey}_")]
            self._groups.append({"name": g["name"], "survey": survey, "rounds": rounds})
        self._current_index = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(10)

        left = QVBoxLayout()
        left.addWidget(QLabel("그룹"))
        self.lst_groups = QListWidget()
        self.lst_groups.currentRowChanged.connect(self._on_group_changed)
        left.addWidget(self.lst_groups, 1)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("추가")
        btn_del = QPushButton("삭제")
        btn_add.clicked.connect(self._add_group)
        btn_del.clicked.connect(self._delete_group)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        left.addLayout(btn_row)
        body.addLayout(left, 0)

        right = QVBoxLayout()
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("그룹명"))
        self.ed_name = QLineEdit()
        self.ed_name.textEdited.connect(self._sync_current)
        name_row.addWidget(self.ed_name, 1)
        right.addLayout(name_row)

        self._populating = False
        self.item_tabs = QTabWidget()
        self.item_tables = {}
        for sec, title in (("현지", "현지조사"), ("문헌", "문헌조사")):
            tbl = QTableWidget(0, 1)
            tbl.setHorizontalHeaderLabels(["조사항목"])
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            tbl.setSelectionMode(QTableWidget.NoSelection)
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.item_tables[sec] = tbl
            self.item_tabs.addTab(tbl, title)
        right.addWidget(self.item_tabs, 1)

        hint = QLabel("한 그룹에는 현지조사 또는 문헌조사 항목만 선택할 수 있습니다.")
        hint.setStyleSheet(f"{FF_KR};font-size:11px;color:{_SUB};")
        right.addWidget(hint)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._refresh_group_list()
        self._populate_items()
        if self._groups:
            self.lst_groups.setCurrentRow(0)

    def _refresh_group_list(self):
        self.lst_groups.blockSignals(True)
        self.lst_groups.clear()
        for g in self._groups:
            survey = g.get("survey") or _infer_group_survey(g.get("rounds", []))
            suffix = f" ({survey})" if survey else ""
            self.lst_groups.addItem(f"{g['name']}{suffix}")
        self.lst_groups.blockSignals(False)

    def _populate_items(self):
        self._populating = True
        try:
            for tbl in self.item_tables.values():
                tbl.setRowCount(0)
            selected = set(self._groups[self._current_index]["rounds"]) if 0 <= self._current_index < len(self._groups) else set()
            group_survey = self._groups[self._current_index].get("survey", "") if 0 <= self._current_index < len(self._groups) else ""
            row_by_sec = {"현지": 0, "문헌": 0}
            _c_on = "#4F6FD8"; _c_dark = "#3F5FBF"; _c_border = "#94A3B8"
            for item in self._available_items:
                sec = item.get("section", "")
                tbl = self.item_tables.get(sec)
                if tbl is None:
                    continue
                ri = row_by_sec[sec]
                row_by_sec[sec] += 1
                tbl.setRowCount(ri + 1)
                key = item["key"]
                is_checked = key in selected
                is_disabled = bool(group_survey and group_survey != sec and key not in selected)
                btn = QToolButton()
                btn.setText(item["detail"])
                btn.setCheckable(True)
                btn.setChecked(is_checked)
                btn.setEnabled(not is_disabled)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setFixedHeight(30)
                btn.setStyleSheet(
                    f"QToolButton{{border:1.5px solid {_c_border};border-radius:6px;padding:3px 10px;"
                    f"{FF_KR};font-size:12px;background:transparent;color:{_TXT};}}"
                    f"QToolButton:hover{{border-color:#64748B;background:#EFF6FF;color:#3B5BDB;}}"
                    f"QToolButton:checked{{background:{_c_on};color:white;border-color:{_c_on};font-weight:700;}}"
                    f"QToolButton:checked:hover{{background:{_c_dark};border-color:{_c_dark};color:white;}}"
                    f"QToolButton:disabled{{color:#9CA3AF;border-color:#D1D5DB;background:#F3F4F6;}}"
                )
                def _make_handler(k, s):
                    def _on_toggled(checked):
                        self._on_button_toggled(k, s, checked)
                    return _on_toggled
                btn.toggled.connect(_make_handler(key, sec))
                tbl.setCellWidget(ri, 0, btn)
                tbl.setRowHeight(ri, 36)
        finally:
            self._populating = False

    def _on_group_changed(self, row: int):
        self._current_index = row
        if 0 <= row < len(self._groups):
            self.ed_name.setEnabled(True)
            self.item_tabs.setEnabled(True)
            self.ed_name.blockSignals(True)
            self.ed_name.setText(self._groups[row]["name"])
            self.ed_name.blockSignals(False)
        else:
            self.ed_name.setText("")
            self.ed_name.setEnabled(False)
            self.item_tabs.setEnabled(False)
        self._populate_items()

    def _sync_current(self):
        if not (0 <= self._current_index < len(self._groups)):
            return
        name = self.ed_name.text().strip()
        self._groups[self._current_index]["name"] = name
        item = self.lst_groups.item(self._current_index)
        if item:
            survey = self._groups[self._current_index].get("survey", "")
            suffix = f" ({survey})" if survey else ""
            item.setText((name or "(이름 없음)") + suffix)

    def _on_button_toggled(self, key: str, sec: str, checked: bool):
        if self._populating or not (0 <= self._current_index < len(self._groups)):
            return
        group = self._groups[self._current_index]
        rounds = group.setdefault("rounds", [])
        if checked:
            survey = group.get("survey", "")
            if survey and survey != sec:
                self._populate_items()
                return
            group["survey"] = sec
            if key not in rounds:
                rounds.append(key)
        else:
            group["rounds"] = [x for x in rounds if x != key]
            if not group["rounds"]:
                group["survey"] = ""
        self._refresh_group_list()
        self.lst_groups.setCurrentRow(self._current_index)
        self._populate_items()

    def _add_group(self):
        base = "새 그룹"
        names = {g["name"] for g in self._groups}
        name = base
        idx = 1
        while name in names:
            idx += 1
            name = f"{base} {idx}"
        self._groups.append({"name": name, "survey": "", "rounds": []})
        self._refresh_group_list()
        self.lst_groups.setCurrentRow(len(self._groups) - 1)
        self.ed_name.setFocus()
        self.ed_name.selectAll()

    def _delete_group(self):
        row = self.lst_groups.currentRow()
        if 0 <= row < len(self._groups):
            del self._groups[row]
            self._refresh_group_list()
            self.lst_groups.setCurrentRow(min(row, len(self._groups) - 1))

    def _accept(self):
        cleaned = []
        seen = set()
        for g in self._groups:
            name = str(g.get("name", "")).strip()
            rounds = [x for x in g.get("rounds", []) if x]
            survey = g.get("survey") or _infer_group_survey(rounds)
            rounds = [x for x in rounds if str(x).startswith(f"{survey}_")] if survey else []
            if not name or not rounds or name in seen:
                continue
            seen.add(name)
            cleaned.append({"name": name, "survey": survey, "rounds": list(dict.fromkeys(rounds))})
        self._groups = cleaned
        self.accept()

    def groups(self) -> list:
        return self._groups

# ── 창 전용 QSS (config 토큰 활용) ──────────────────────────────
COMMON_QSS = f"""
QMainWindow, QWidget {{
    background: {_BG}; {FF_EN}; font-size: 13px; color: {_TXT};
}}
QGroupBox {{
    {FF_KR}; font-size: 12px; font-weight: 700; color: {_TXT};
    border: 1.5px solid {_BORDER}; border-radius: 12px;
    margin-top: 12px; background: {_CARD}; padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 14px; padding: 0 6px; color: {_TXT}; font-size: 12px;
}}
QPushButton {{
    height: 36px; padding: 6px 16px; border-radius: 8px; border: none;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {_ACCENT}, stop:1 {_ACCENT_D});
    color: white; {FF_KR}; font-size: 13px; font-weight: 700;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #3B82F6, stop:1 {_ACCENT});
}}
QPushButton:pressed  {{ background: {_ACCENT_D}; }}
QPushButton:disabled {{ background: #E9ECEF; color: #B0B8C4; border: none; }}
QTableWidget {{
    border-radius: 10px; border: 1.5px solid {_BORDER};
    background: {_CARD}; gridline-color: {_BORDER}; {FF_KR}; font-size: 12px;
}}
QTableWidget::item          {{ padding: 4px 8px; }}
QTableWidget::item:selected {{ background: {_ACCENT_L}; color: {_ACCENT}; }}
QHeaderView::section {{
    background: {_BG}; border: 0;
    border-bottom: 1.5px solid {_BORDER}; border-right: 1px solid {_BORDER};
    padding: 6px 8px; {FF_KR}; font-size: 11px; font-weight: 700; color: {_SUB};
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    min-height: 18px; padding: 7px 18px;
    border: 1px solid transparent; border-radius: 11px;
    background: #EEF2F7; {FF_KR}; font-size: 12px; font-weight: 600;
    color: {_SUB}; margin-right: 6px;
}}
QPushButton:focus, QCheckBox:focus, QRadioButton:focus, QTabBar::tab:focus {{ outline: none; }}
QTabBar::tab:selected {{ background: #FFFFFF; color: {_ACCENT}; font-weight: 700; border-color: #DCE5F0; }}
QTabBar::tab:hover    {{ background: #F8FBFF; color: {_ACCENT}; }}
QTabWidget::pane      {{ border: none; background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical         {{ background: {_BG}; width: 6px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: {_BORDER}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #B0B8C8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal          {{ background: {_BG}; height: 6px; border-radius: 3px; }}
QScrollBar::handle:horizontal  {{ background: {_BORDER}; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: #B0B8C8; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QPlainTextEdit {{ background: #FFFFFF; }}
""" + CHK_INDICATOR_QSS

ACCENT = _ACCENT
WARN   = _WARN
OK_CLR = _SUCCESS

RED_BG   = QColor(255, 199, 206)
WHITE_BG = QColor(255, 255, 255)

ORDER_COLORS = [
    "#4472C4","#ED7D31","#A5A5A5","#FFC000","#5B9BD5",
    "#70AD47","#264478","#9E480E","#843C0C","#255E91",
    "#7030A0","#C00000","#00B0F0","#92D050","#FF6600",
]
LIFE_LABEL = {
    "RES":"텃새(Res)", "SV":"여름철새(Sv)", "WV":"겨울철새(Wv)",
    "PM":"나그네새(Pm)", "VAG":"길잃은새(Vag)",
}

# ── 유틸 ──────────────────────────────────────────────────────────────────────
# CopyableTableWidget / _item / _make_tbl / _auto_fit_table → ui_shared 에서 import

def _rn(name: str) -> str:
    """회차명 표시용 축약"""
    n = name
    for p in ("현지_", "문헌_"):
        n = n.replace(p, ("현지" if "현지" in p else "문헌"))
    return n

def _sc(w):
    return make_scroll_widget(w)

def _autofit(tbl: QTableWidget):
    tbl.resizeColumnsToContents()
    tbl.horizontalHeader().setStretchLastSection(True)


# ── 도넛 차트 ─────────────────────────────────────────────────────────────────
class DonutChart(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data  = data   # [(label, value, color), ...]
        self.total = sum(v for _,v,_ in data)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, ev):
        from PySide6.QtCore import QRectF
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h = self.width(), self.height()
        sz  = min(w,h)-12; x,y = (w-sz)//2, (h-sz)//2
        rect = QRectF(x,y,sz,sz)
        hole = QRectF(x+sz*.28, y+sz*.28, sz*.44, sz*.44)
        if not self.total: return
        ang = 90*16
        for _,val,color in self.data:
            span = int(val/self.total*360*16)
            p.setBrush(QBrush(QColor(color)))
            p.setPen(QPen(QColor("#fff"),1.5))
            p.drawPie(rect,ang,span); ang -= span
        p.setBrush(QBrush(QColor(f"{_BG}"))); p.setPen(Qt.NoPen)
        p.drawEllipse(hole)
        p.setPen(QColor("#1a1a1a"))
        p.setFont(QFont("맑은 고딕",10,QFont.Bold))
        p.drawText(hole.toRect(), Qt.AlignCenter, f"{int(self.total)}종")


# ── 가로 바 차트 ──────────────────────────────────────────────────────────────
class HBarChart(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data   # [(label, value, pct, color), ...]
        self.setMinimumHeight(len(data)*30+16)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def paintEvent(self, ev):
        if not self.data: return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("맑은 고딕",9))
        w = self.width(); lw=185; bmax=max(w-lw-68,10)
        rh=24; yo=8
        mp = max(d[2] for d in self.data) or 1
        for i,(lbl,val,pct,color) in enumerate(self.data):
            y = yo+i*(rh+4)
            p.setPen(QColor("#1a1a1a"))
            p.drawText(0,y,lw-4,rh,Qt.AlignRight|Qt.AlignVCenter,lbl)
            bw = max(int(pct/mp*bmax),2)
            p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(lw,y+5,bw,rh-10,3,3)
            p.setPen(QColor("#555"))
            p.drawText(lw+bw+4,y,62,rh,Qt.AlignLeft|Qt.AlignVCenter,
                       f"{val}종 {pct:.1f}%")


def _get_ok_map(species_list):
    m = {}
    for sp in species_list:
        if getattr(sp, "order", ""):
            kor = getattr(sp, "order_kor", "")
            m[sp.order] = kor if kor else sp.order
    return m


# ── 목별 표 ───────────────────────────────────────────────────────────────────
def _make_order_table(stats, rnames: list, ok_map: dict = None) -> QTableWidget:
    if ok_map is None: ok_map = {}
    order_list = stats.order_stats if hasattr(stats,"order_stats") else []
    cols = ["Order", "목(한글)", "종수","과수","비율(%)"] + [_rn(r) for r in rnames]
    tbl  = _make_tbl(cols)
    tbl.setRowCount(len(order_list))
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    for c in range(1,len(cols)):
        tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)

    color_map = {o.order: ORDER_COLORS[i%len(ORDER_COLORS)]
                 for i,o in enumerate(getattr(stats,"order_stats_orig",order_list))}

    for row, os_ in enumerate(order_list):
        tbl.setItem(row,0,_item(os_.order, Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(row,1,_item(ok_map.get(os_.order, os_.order), Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(row,2,_item(os_.total))
        tbl.setItem(row,3,_item(os_.family_count))
        tbl.setItem(row,4,_item(_fmt(os_.ratio*100)))
        for ci,rs in enumerate(os_.round_stats):
            tbl.setItem(row,5+ci,_item(str(rs.count) if rs.count else "—"))
        if row==0:
            for c in range(len(cols)):
                it=tbl.item(row,c)
                if it:
                    it.setBackground(QColor("#fff3e0"))
                    it.setForeground(QColor(WARN))
    return tbl


# ── 동물류 탭 콘텐츠 ─────────────────────────────────────────────────────────
def _animal_tab(stats, sheet=None) -> QWidget:
    ok_map = _get_ok_map(sheet.species) if sheet and hasattr(sheet, "species") else {}
    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)

    total = stats.total_species
    div   = stats.div
    rnames = stats.round_names
    orig  = getattr(stats,"order_stats_orig", stats.order_stats)

    # 표를 먼저 생성하고, 여기서 데이터를 추출해 그래프를 그림
    tbl = _make_order_table(stats, rnames, ok_map)
    donut_data = []
    bar_data = []
    for r in range(tbl.rowCount()):
        lbl = tbl.item(r, 1).text()
        val = int(tbl.item(r, 2).text())
        pct = float(tbl.item(r, 4).text().replace('%',''))
        color = ORDER_COLORS[r % len(ORDER_COLORS)]
        donut_data.append((lbl, val, color))
        bar_data.append((lbl, val, pct, color))

    mid = QHBoxLayout()

    grp_d = QGroupBox("목별 종구성 비율")
    dl = QVBoxLayout(grp_d); dl.setContentsMargins(6,20,6,6)
    donut = DonutChart(donut_data)
    donut.setMinimumHeight(200)
    dl.addWidget(donut)
    mid.addWidget(grp_d)

    grp_b = QGroupBox("목별 종수 (내림차순)")
    bl = QVBoxLayout(grp_b); bl.setContentsMargins(6,20,6,6)
    bar = HBarChart(bar_data)
    sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(bar)
    bl.addWidget(sc)
    mid.addWidget(grp_b, stretch=2)
    lay.addLayout(mid)

    # 하단: 목별 표
    grp_t = QGroupBox("목별 상세")
    tl = QVBoxLayout(grp_t); tl.setContentsMargins(6,12,6,6)
    
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(make_copy_button(tbl))
    tl.addLayout(btn_row)
    
    tl.addWidget(tbl)
    lay.addWidget(grp_t, stretch=1)

    # 현지·문헌 요약
    if stats.field_only > 0 or stats.both > 0:
        grp_s = QGroupBox("현지·문헌 중복")
        sl = QHBoxLayout(grp_s); sl.setContentsMargins(14,20,14,12)
        for lbl,val in [("현지만",stats.field_only),("문헌만",stats.lit_only),("공통",stats.both)]:
            l=QLabel(f"{lbl}\n{val}종"); l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(f"{FF_KR};font-size:13px;font-weight:700;color:{ACCENT};")
            sl.addWidget(l)
        lay.addWidget(grp_s)

    # 조류 생활형
    if getattr(stats,"life_stats",None):
        grp_l = QGroupBox("생활형 (종수)")
        ll = QHBoxLayout(grp_l); ll.setContentsMargins(14,20,14,12); ll.setSpacing(16)
        for code,cnt in sorted(stats.life_stats.items(), key=lambda x:-x[1]):
            lbl = LIFE_LABEL.get(code, code)
            l = QLabel(f"{lbl}\n{cnt}종"); l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(f"{FF_KR};font-size:13px;color:{ACCENT};font-weight:700;")
            ll.addWidget(l)
        ll.addStretch()
        lay.addWidget(grp_l)

    return w


# ── 수생동물 탭 ───────────────────────────────────────────────────────────────
def _aquatic_tab(stats: AquaticStats, sheet=None) -> QWidget:
    ok_map = _get_ok_map(sheet.species) if sheet and hasattr(sheet, "species") else {}
    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)

    grp_t = QGroupBox("목별 상세")
    tl = QVBoxLayout(grp_t); tl.setContentsMargins(6,12,6,6)
    
    tbl = _make_order_table(stats, stats.round_names, ok_map)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(make_copy_button(tbl))
    tl.addLayout(btn_row)
    
    tl.addWidget(tbl)
    lay.addWidget(grp_t, stretch=1)
    return w


# ── 식물 탭 ───────────────────────────────────────────────────────────────────
def _plant_tab(stats: PlantStats) -> QWidget:
    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)

    # 요약 카드
    grp = QGroupBox("식물 요약")
    sl  = QHBoxLayout(grp); sl.setContentsMargins(14,20,14,12); sl.setSpacing(20)
    for lbl,val,color in [
        ("전체 종수",f"{stats.total_species}종",ACCENT),
        ("과 수",f"{stats.family_count}과",ACCENT),
        ("현지만",f"{stats.field_only}종","#333"),
        ("문헌만",f"{stats.lit_only}종","#333"),
        ("공통",f"{stats.both}종","#333"),
    ]:
        l=QLabel(f"{lbl}\n{val}"); l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(f"{FF_EN};font-size:14px;font-weight:700;color:{color};")
        sl.addWidget(l)
    sl.addStretch()
    lay.addWidget(grp)

    # 회차별 종수 표
    if stats.round_totals:
        grp2 = QGroupBox("조사별 출현 종수")
        rl   = QVBoxLayout(grp2); rl.setContentsMargins(8,12,8,8)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        tbl  = _make_tbl([_rn(r.name) for r in stats.round_totals])
        tbl.setRowCount(1); tbl.setFixedHeight(62)
        tbl.setVerticalHeaderLabels(["종수"])
        tbl.verticalHeader().setVisible(True)
        for ci,rs in enumerate(stats.round_totals):
            tbl.setItem(0,ci,_item(rs.count))
        btn_row.addWidget(make_copy_button(tbl))
        rl.addLayout(btn_row)
        rl.addWidget(tbl)
        lay.addWidget(grp2)

    lay.addStretch()
    return w


# ── 희귀특산 탭 ───────────────────────────────────────────────────────────────
def _special_tab(stats: PlantSpecialStats) -> QWidget:
    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)

    grp = QGroupBox("희귀·특산식물 요약")
    sl  = QHBoxLayout(grp); sl.setContentsMargins(14,20,14,12); sl.setSpacing(16)
    l=QLabel(f"전체\n{stats.total_species}종"); l.setAlignment(Qt.AlignCenter)
    l.setStyleSheet(f"{FF_EN};font-size:15px;font-weight:700;color:{ACCENT};")
    sl.addWidget(l)
    for cat,cnt in stats.by_category.items():
        l=QLabel(f"{cat}\n{cnt}종"); l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(f"{FF_KR};font-size:13px;font-weight:700;color:{_TXT};")
        sl.addWidget(l)
    sl.addStretch()
    lay.addWidget(grp)
    lay.addStretch()
    return w


# ── 법정보호종 탭 ─────────────────────────────────────────────────────────────
def _protected_tab(stats: ProtectedStats, prot_sheet=None, parent_window=None, aux_sheets=None) -> QWidget:
    from shared import _prot_grade_str, _apply_title, _has_present as _hp
    from shared import _s, _has as _base_has
    aux_sheets = aux_sheets or {}
    rare_sheet = aux_sheets.get("희귀·특산식물") or aux_sheets.get("희귀식물")
    endemic_sheet = aux_sheets.get("희귀·특산식물") or aux_sheets.get("특산식물")

    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

    # ── 희귀·특산 전체 종 목록 (any round present) ──────────────────
    rare_all:    list = []   # 희귀식물
    endemic_all: list = []   # 특산식물
    
    rare_sheet = aux_sheets.get("희귀식물") or aux_sheets.get("희귀·특산식물")
    endemic_sheet = aux_sheets.get("특산식물") or aux_sheets.get("희귀·특산식물")

    if rare_sheet:
        is_combined = rare_sheet.name != "희귀식물" and "특산" in rare_sheet.name
        for sp in rare_sheet.species:
            if not any(_base_has(v) for v in sp.rounds.values()):
                continue
            cat = _s(getattr(sp, "category", ""))
            if is_combined and "특산" in cat and "희귀" not in cat and not any(rg in cat.upper() for rg in ["CR","EN","VU","NT","LC","DD"]):
                continue
            rare_all.append(sp)

    if endemic_sheet:
        is_combined = endemic_sheet.name != "특산식물" and "희귀" in endemic_sheet.name
        for sp in endemic_sheet.species:
            if not any(_base_has(v) for v in sp.rounds.values()):
                continue
            cat = _s(getattr(sp, "category", ""))
            if is_combined and "특산" not in cat:
                continue
            endemic_all.append(sp)

    # ── 요약 GroupBox ────────────────────────────────────────────────
    grp_sum = QGroupBox("법정보호종 요약")
    sl = QHBoxLayout(grp_sum); sl.setContentsMargins(14, 20, 14, 12); sl.setSpacing(16)

    def _sum_lbl(text, style=""):
        l = QLabel(text); l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(style); return l

    sl.addWidget(_sum_lbl(f"전체\n{stats.total_species}종",
                          f"font-size:14px;font-weight:bold;color:{ACCENT};"))
    for grade, cnt in stats.by_grade.items():
        sl.addWidget(_sum_lbl(f"{grade}\n{cnt}종",
                              f"{FF_KR};font-size:12px;font-weight:700;color:{WARN};"))
    for grp_name, cnt in stats.by_group.items():
        sl.addWidget(_sum_lbl(f"{grp_name}\n{cnt}종",
                              f"{FF_KR};font-size:12px;color:{_SUB};"))
    if rare_all:
        sl.addWidget(_sum_lbl(f"희귀식물\n{len(rare_all)}분류군",
                              f"{FF_KR};font-size:12px;color:#059669;font-weight:700;"))
    if endemic_all:
        sl.addWidget(_sum_lbl(f"특산식물\n{len(endemic_all)}분류군",
                              f"{FF_KR};font-size:12px;color:#7C3AED;font-weight:700;"))
    sl.addStretch()
    lay.addWidget(grp_sum)
    QApplication.processEvents()

    # ── 조사별 출현 종수 ─────────────────────────────────────────────
    if stats.round_totals:
        grp2 = QGroupBox("조사별 출현 종수")
        rl   = QVBoxLayout(grp2); rl.setContentsMargins(8, 12, 8, 8)

        field_totals = [rs for rs in stats.round_totals if "현지_" in rs.name and "합계" not in rs.name]
        lit_totals   = [rs for rs in stats.round_totals if "문헌_" in rs.name and "합계" not in rs.name]
        field_rn_names = [rs.name for rs in field_totals]
        lit_rn_names   = [rs.name for rs in lit_totals]

        # 그룹 설정 적용
        all_rn_names = field_rn_names + lit_rn_names
        group_defs = (
            parent_window.get_active_groups(all_rn_names)
            if parent_window and hasattr(parent_window, "get_active_groups")
            else []
        )
        fld_group_defs = [(n, rns) for n, rns in group_defs if any(r in field_rn_names for r in rns)]
        lit_group_defs = [(n, rns) for n, rns in group_defs if any(r in lit_rn_names for r in rns)]

        # 컬럼 구성
        cols = []
        if fld_group_defs:
            for gname, _ in fld_group_defs: cols.append(gname)
            if len(fld_group_defs) > 1: cols.append("현지 합계")
        else:
            for rs in field_totals: cols.append(_rn(rs.name))
            if len(field_totals) > 1: cols.append("현지 합계")
        if lit_group_defs:
            for gname, _ in lit_group_defs: cols.append(gname)
            if len(lit_group_defs) > 1: cols.append("문헌 합계")
        else:
            for rs in lit_totals: cols.append(_rn(rs.name))
            if len(lit_totals) > 1: cols.append("문헌 합계")

        # 행 레이블 구성
        row_labels = ["법정보호종"]
        if rare_all:    row_labels.append("희귀식물")
        if endemic_all: row_labels.append("특산식물")

        def _cnt_prot(rns):
            if not prot_sheet: return 0
            seen = set()
            for sp in prot_sheet.species:
                if any(_hp(sp.rounds.get(rn)) for rn in rns): seen.add(sp.kor_name)
            return len(seen)

        def _prot_row():
            vals = []
            if fld_group_defs:
                for _, grns in fld_group_defs: vals.append(_cnt_prot([r for r in grns if r in field_rn_names]))
                if len(fld_group_defs) > 1: vals.append(_cnt_prot(field_rn_names))
            else:
                for rs in field_totals: vals.append(rs.count)
                if len(field_totals) > 1: vals.append(_cnt_prot(field_rn_names))
            if lit_group_defs:
                for _, grns in lit_group_defs: vals.append(_cnt_prot([r for r in grns if r in lit_rn_names]))
                if len(lit_group_defs) > 1: vals.append(_cnt_prot(lit_rn_names))
            else:
                for rs in lit_totals: vals.append(rs.count)
                if len(lit_totals) > 1: vals.append(_cnt_prot(lit_rn_names))
            return vals

        def _rare_row(is_endemic):
            target_sheet = endemic_sheet if is_endemic else rare_sheet
            if not target_sheet: return [0] * len(cols)
            is_combined = target_sheet.name != ("특산식물" if is_endemic else "희귀식물")
            def _cnt(rns):
                seen = set()
                for sp in target_sheet.species:
                    cat = _s(getattr(sp, "category", ""))
                    if is_endemic:
                        if is_combined and "특산" not in cat: continue
                    else:
                        if is_combined and "특산" in cat and "희귀" not in cat and not any(rg in cat.upper() for rg in ["CR","EN","VU","NT","LC","DD"]): continue
                    if sp.kor_name not in seen and any(_base_has(sp.rounds.get(r)) for r in rns):
                        seen.add(sp.kor_name)
                return len(seen)
            vals = []
            if fld_group_defs:
                for _, grns in fld_group_defs: vals.append(_cnt([r for r in grns if r in field_rn_names]))
                if len(fld_group_defs) > 1: vals.append(_cnt(field_rn_names))
            else:
                for rs in field_totals: vals.append(_cnt([rs.name]))
                if len(field_totals) > 1: vals.append(_cnt(field_rn_names))
            if lit_group_defs:
                for _, grns in lit_group_defs: vals.append(_cnt([r for r in grns if r in lit_rn_names]))
                if len(lit_group_defs) > 1: vals.append(_cnt(lit_rn_names))
            else:
                for rs in lit_totals: vals.append(_cnt([rs.name]))
                if len(lit_totals) > 1: vals.append(_cnt(lit_rn_names))
            return vals

        all_rows = [_prot_row()]
        if rare_all:    all_rows.append(_rare_row(False))
        if endemic_all: all_rows.append(_rare_row(True))

        tbl = _make_tbl(cols)
        n_rows = len(row_labels)
        tbl.setRowCount(n_rows)
        tbl.setFixedHeight(24 * n_rows + 38)
        tbl.setVerticalHeaderLabels(row_labels)
        tbl.verticalHeader().setVisible(True)
        for ri, row_vals in enumerate(all_rows):
            for ci, val in enumerate(row_vals):
                tbl.setItem(ri, ci, _item(val if val else "—"))
        rl.addWidget(tbl)
        lay.addWidget(grp2)
        QApplication.processEvents()

    # ── 차수별 출현 문장 ──────────────────────────────────────────────
    has_prot = bool(prot_sheet and prot_sheet.species)
    has_rare = bool(rare_all or endemic_all)
    if has_prot or has_rare:
        S = SETTINGS
        _TXT_QSS = (f"QPlainTextEdit{{background:#FFFFFF;border:1.5px solid {_BORDER};"
                    f"border-radius:7px;{FF_KR};font-size:12px;padding:6px;}}")
        _BTN_QSS = ("QPushButton { background: transparent; color: #2563EB; font-size: 11px;"
                    " font-weight: bold; border: 1px solid #2563EB; border-radius: 4px;"
                    " padding: 2px 8px; } QPushButton:hover { background: #EFF6FF; }")

        if prot_sheet and hasattr(prot_sheet, "round_names"):
            rn_src = prot_sheet.round_names
        elif rare_sheet and hasattr(rare_sheet, "round_names"):
            rn_src = rare_sheet.round_names
        else:
            rn_src = []
        _SUMMARY = {"합계", "종합"}
        def _is_summary_rn(rn):
            parts = rn.split("_", 2)
            return any(p in _SUMMARY for p in parts[1:])
        field_rns = [rn for rn in rn_src if rn.startswith("현지_") and not _is_summary_rn(rn)]
        lit_rns   = [rn for rn in rn_src if rn.startswith("문헌_") and not _is_summary_rn(rn)]

        # 그룹 설정 적용 (문장용)
        _sent_group_defs = (
            parent_window.get_active_groups(field_rns + lit_rns)
            if parent_window and hasattr(parent_window, "get_active_groups")
            else []
        )
        _fld_sent_groups = [(n, r) for n, r in _sent_group_defs if any(x in field_rns for x in r)]
        _lit_sent_groups = [(n, r) for n, r in _sent_group_defs if any(x in lit_rns for x in r)]

        def _present_prot_unique(rns):
            if not has_prot:
                return []
            seen = set()
            present = []
            for sp in prot_sheet.species:
                if sp.kor_name in seen:
                    continue
                if any(_hp(sp.rounds.get(rn)) for rn in rns):
                    seen.add(sp.kor_name)
                    present.append(sp)
            return present

        max_list_limit = 1
        for rns_group in ([field_rns] if field_rns else []) + ([lit_rns] if lit_rns else []):
            max_list_limit = max(max_list_limit, len(_present_prot_unique(rns_group)))
            for rn in rns_group:
                max_list_limit = max(max_list_limit, len(_present_prot_unique([rn])))
        SETTINGS.sent_species_limit = max_list_limit

        def _lim(lst):
            lim = getattr(SETTINGS, "sent_species_limit", 3)
            return ", ".join(lst[:lim]) + " 등" if len(lst) > lim else ", ".join(lst)

        def _prot_names_rn(rn):
            present = _present_prot_unique([rn])
            if not present: return 0, ""
            parts = [(f"{sp.kor_name}({g})" if (g := _prot_grade_str(sp)) else sp.kor_name) for sp in present]
            return len(present), _lim(parts)

        def _prot_names_all(rns):
            present = _present_prot_unique(rns)
            if not present: return 0, ""
            parts = [(f"{sp.kor_name}({g})" if (g := _prot_grade_str(sp)) else sp.kor_name) for sp in present]
            return len(present), _lim(parts)

        def _rare_names(rns, is_endemic):
            target_sheet = endemic_sheet if is_endemic else rare_sheet
            if not target_sheet: return []
            is_combined = target_sheet.name != ("특산식물" if is_endemic else "희귀식물")
            seen = set(); names = []
            for sp in target_sheet.species:
                cat = _s(getattr(sp, "category", ""))
                if is_endemic:
                    if is_combined and "특산" not in cat: continue
                else:
                    if is_combined and "특산" in cat and "희귀" not in cat and not any(rg in cat.upper() for rg in ["CR","EN","VU","NT","LC","DD"]): continue
                if sp.kor_name not in seen and any(_base_has(sp.rounds.get(rn)) for rn in rns):
                    seen.add(sp.kor_name); names.append(sp.kor_name or "?")
            return names

        def _build_sent(rns, is_field):
            lines = []
            s_end = S.field_s1_end if is_field else S.lit_s1_end
            조사 = "현지조사" if is_field else "문헌조사"
            prot_none = S.prot_none_field if is_field else S.prot_none_lit
            intro_mode = getattr(
                S,
                "field_intro_mode" if is_field else "lit_intro_mode",
                getattr(S, "field_intro_mode", "auto"),
            )

            def _append(prefix, rns_sub):
                n, names_str = _prot_names_all(rns_sub) if len(rns_sub) > 1 else _prot_names_rn(rns_sub[0])
                suffix = "" if str(prefix).endswith("에서") else "시"
                if has_prot:
                    if n: lines.append(f"{prefix}{suffix} 법정보호종은 {names_str} 총 {n}종{s_end}")
                    else: lines.append(f"{prefix}{suffix} 법정보호종은 {prot_none}")
                r_names = _rare_names(rns_sub, False)
                e_names = _rare_names(rns_sub, True)
                rare_parts = []
                if r_names: rare_parts.append(f"희귀식물은 {_lim(r_names)} 총 {len(r_names)}분류군")
                if e_names: rare_parts.append(f"특산식물은 {_lim(e_names)} 총 {len(e_names)}분류군")
                if rare_parts:
                    lines.append(f"{prefix}{suffix} 산림청지정 " + ", ".join(rare_parts) + f"{s_end}")

            if len(rns) > 1:
                prefix = 조사
                _append(prefix, rns)
            for rn in rns:
                lbl = rn.split("_", 1)[1]
                if intro_mode == "fixed":
                    prefix = 조사
                elif is_field:
                    prefix = _round_survey_label(lbl)
                else:
                    prefix = lit_title_phrase_for_rounds([rn]) or _round_survey_label(lbl)
                _append(prefix, [rn])
            return _apply_title("\n".join(lines), S.sentence_title) if lines else ""

        def _build_group_sent(group_defs, all_rns, is_field):
            """그룹 설정이 있을 때 그룹별 문장을 생성."""
            lines = []
            s_end = S.field_s1_end if is_field else S.lit_s1_end
            조사 = "현지조사" if is_field else "문헌조사"
            prot_none = S.prot_none_field if is_field else S.prot_none_lit

            # 전체 합계 문장
            if len(all_rns) > 1:
                pfx = 조사
                n_all, ns_all = _prot_names_all(all_rns)
                if has_prot:
                    if n_all:
                        lines.append(f"{pfx}시 법정보호종은 {ns_all} 총 {n_all}종{s_end}")
                    else:
                        lines.append(f"{pfx}시 법정보호종은 {prot_none}")
                r_names_all = _rare_names(all_rns, False)
                e_names_all = _rare_names(all_rns, True)
                rare_parts_all = []
                if r_names_all: rare_parts_all.append(f"희귀식물은 {_lim(r_names_all)} 총 {len(r_names_all)}분류군")
                if e_names_all: rare_parts_all.append(f"특산식물은 {_lim(e_names_all)} 총 {len(e_names_all)}분류군")
                if rare_parts_all:
                    lines.append(f"{pfx}시 산림청지정 " + ", ".join(rare_parts_all) + f"{s_end}")

            for gname, grns in group_defs:
                valid = [r for r in grns if r in all_rns]
                if not valid:
                    continue
                n, names_str = _prot_names_all(valid)
                if has_prot:
                    if n:
                        lines.append(f"{gname} 법정보호종은 {names_str} 총 {n}종{s_end}")
                    else:
                        lines.append(f"{gname} 법정보호종은 {S.prot_none_field if is_field else S.prot_none_lit}")
                r_names = _rare_names(valid, False)
                e_names = _rare_names(valid, True)
                rare_parts = []
                if r_names: rare_parts.append(f"희귀식물은 {_lim(r_names)} 총 {len(r_names)}분류군")
                if e_names: rare_parts.append(f"특산식물은 {_lim(e_names)} 총 {len(e_names)}분류군")
                if rare_parts:
                    lines.append(f"{gname} 산림청지정 " + ", ".join(rare_parts) + f"{s_end}")
            return _apply_title("\n".join(lines), S.sentence_title) if lines else ""

        def _build_field_sent():
            if _fld_sent_groups:
                return _build_group_sent(_fld_sent_groups, field_rns, True)
            return _build_sent(field_rns, True)

        def _build_lit_sent():
            if _lit_sent_groups:
                return _build_group_sent(_lit_sent_groups, lit_rns, False)
            return _build_sent(lit_rns, False)

        _LIM_QSS = (f"QLineEdit {{ background:#FFFFFF; border:1px solid {_BORDER}; border-radius:4px;"
                    f" font-family:'{_FONT_KR}'; font-size:12px; padding:2px 6px; max-width:40px; }}")
        _lim_edits: list = []

        def _make_sent_grp(title, build_fn):
            text = build_fn()
            if not text: return None
            grp = QGroupBox(title)
            gl = QVBoxLayout(grp); gl.setContentsMargins(8, 18, 8, 8); gl.setSpacing(6)

            btn = QPushButton("📋 복사"); btn.setFixedHeight(24); btn.setStyleSheet(_BTN_QSS)
            lbl_lim = QLabel("나열")
            edt_lim = QLineEdit(str(getattr(SETTINGS, "sent_species_limit", max_list_limit)))
            edt_lim.setStyleSheet(_LIM_QSS); edt_lim.setFixedWidth(40)
            _lim_edits.append(edt_lim)

            def _refresh(t_ref=None, fn=build_fn):
                txt.setPlainText(fn())

            def _on_lim_changed(text_val, edits=_lim_edits):
                try:
                    val = max(1, int(text_val))
                except ValueError:
                    return
                SETTINGS.sent_species_limit = val
                for e in edits:
                    if e.text() != str(val):
                        e.blockSignals(True); e.setText(str(val)); e.blockSignals(False)
                txt.setPlainText(build_fn())
                if parent_window and hasattr(parent_window, "sig_sent_settings"):
                    parent_window.sig_sent_settings.emit()
            edt_lim.textChanged.connect(_on_lim_changed)

            btn_r = QHBoxLayout()
            btn_r.addWidget(btn)
            btn_r.addWidget(lbl_lim)
            btn_r.addWidget(edt_lim)
            btn_r.addStretch()
            gl.addLayout(btn_r)

            n_lines = len([l for l in text.split("\n") if l.strip()])
            txt = QPlainTextEdit(); txt.setReadOnly(True)
            txt.setStyleSheet(_TXT_QSS); txt.setPlainText(text)
            txt.setFixedHeight(min(n_lines * 44 + 20, 420))
            txt._sent_refresh_fn = lambda fn=build_fn: txt.setPlainText(fn())
            if parent_window and hasattr(parent_window, "sig_sent_settings"):
                parent_window.sig_sent_settings.connect(txt._sent_refresh_fn)
            def _do_copy(_=False, b=btn):
                QApplication.clipboard().setText(txt.toPlainText())
                from ui_shared import apply_button_feedback; apply_button_feedback(b)
            btn.clicked.connect(_do_copy)
            gl.addWidget(txt)
            return grp

        QApplication.processEvents()
        sent_lay = QHBoxLayout(); sent_lay.setContentsMargins(0, 0, 0, 0); sent_lay.setSpacing(8)
        for _title, _fn in [("현지조사 문장", _build_field_sent), ("문헌조사 문장", _build_lit_sent)]:
            g = _make_sent_grp(_title, _fn)
            if g: sent_lay.addWidget(g, stretch=1)
        if sent_lay.count() > 0:
            lay.addLayout(sent_lay)

    lay.addStretch()
    return w


# ── 탭 아이콘 매핑 ────────────────────────────────────────────────────────────
TAB_ICON = {
    "mammal":"🦌", "bird":"🦅", "herp":"🦎",
    "insect":"🦋", "fish":"🐟", "benthos":"🦐",
    "plant":"🌿", "plant_sub":"🌱", "plant_special":"🌸",
    "protected":"🛡",
}


def _build_land_overview_tab(parsed: dict, parent_window=None) -> QWidget | None:
    from parser import ParsedSheet, ParsedProtected

    taxon_order = ["mammal", "bird", "herp", "insect"]
    sheets = {
        obj.taxon: obj
        for obj in parsed.values()
        if isinstance(obj, ParsedSheet) and obj.taxon in taxon_order
    }
    if not sheets:
        return None

    prot_sheet = next((obj for obj in parsed.values() if isinstance(obj, ParsedProtected)), None)

    def _lit_rounds_for(sheet):
        return [r for r in sheet.meta.round_names
                if "문헌" in r and "합계" not in r and "종합" not in r]

    def _field_rounds_for(sheet):
        return [r for r in sheet.meta.round_names
                if "현지" in r and "합계" not in r and "종합" not in r]

    def _sp_for_round(sheet, rname):
        return [sp for sp in sheet.species if _has_present(sp.rounds.get(rname))]

    def _sp_for_rounds(sheet, rnames):
        return [sp for sp in sheet.species if any(_has_present(sp.rounds.get(r)) for r in rnames)]

    def _fam_count(species):
        return len({sp.family for sp in species if sp.family})

    def _summary_text(taxon, species, rns, show_indiv=False):
        if not species:
            return "-"
        if taxon == "herp":
            # 미분리 모드에서는 양서+파충을 합산하여 표기
            return f"{_fam_count(species)}과 {len(species)}종"
        total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in rns)
        base = f"{_fam_count(species)}과 {len(species)}종"
        if show_indiv and taxon in ("bird", "insect"):
            base += f" {total_ind:,}개체"
        return base

    def _herp_split_text(species, rns, show_indiv=False):
        amp = [sp for sp in species if _get_herp_group(sp) == "양서류"]
        rep = [sp for sp in species if _get_herp_group(sp) == "파충류"]

        def _fmt(group_species):
            if not group_species:
                return "-"
            total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in group_species for r in rns)
            s = f"{_fam_count(group_species)}과 {len(group_species)}종"
            if show_indiv:
                s += f" {total_ind:,}개체"
            return s

        return _fmt(amp), _fmt(rep)

    def _detail_cell_text(fam_count, sp_count, names_str):
        if not sp_count:
            return "-"
        return f"{fam_count}과 {sp_count}종\n{names_str}" if names_str else f"{fam_count}과 {sp_count}종"

    def _all_prot_for(per_taxon_species):
        """Returns (fam_count, sp_count, detail_str) across all taxa for a row."""
        if not prot_sheet:
            return 0, 0, ""
        by_name = {}
        families_seen = set()
        for taxon in taxon_order:
            sp_list = per_taxon_species.get(taxon, [])
            if not sp_list:
                continue
            names = {sp.kor_name for sp in sp_list if getattr(sp, "kor_name", "")}
            if not names:
                continue

            fam_by_name = {}
            sheet = sheets.get(taxon)
            if sheet:
                for sp in sheet.species:
                    kn = getattr(sp, "kor_name", "")
                    if kn and kn in names and kn not in fam_by_name:
                        fam_by_name[kn] = getattr(sp, "family", "")

            for psp in prot_sheet.species:
                pname = getattr(psp, "kor_name", "")
                if not pname or pname not in names:
                    continue
                if not _prot_group_matches(taxon, getattr(psp, "group", ""), psp):
                    continue
                by_name.setdefault(pname, [])
                g = _prot_grade_str(psp)
                if g and g not in by_name[pname]:
                    by_name[pname].append(g)
                pf = fam_by_name.get(pname, "")
                if pf:
                    families_seen.add(pf)

        parts = []
        for name, grades in by_name.items():
            parts.append(f"{name}({', '.join(grades)})" if grades else name)
        names_str = ", ".join(parts)
        return len(families_seen), len(by_name), _detail_cell_text(len(families_seen), len(by_name), names_str)

    def _all_disturb_for(per_taxon_species):
        """Returns (fam_count, sp_count, detail_str) for ecosystem disturbance species."""
        species = []
        for taxon in taxon_order:
            species.extend(per_taxon_species.get(taxon, []) or [])
        n, names_str = _ecosystem_disturber_list(None, species)
        if not n:
            return 0, 0, ""
        names = {s.strip() for s in names_str.split(",") if s.strip()}
        families_seen = {
            getattr(sp, "family", "")
            for sp in species
            if (getattr(sp, "kor_name", "") in names or getattr(sp, "sci_name", "") in names)
            and getattr(sp, "family", "")
        }
        return len(families_seen), n, _detail_cell_text(len(families_seen), n, names_str)

    # Collect unique rounds in stable order across all taxa sheets
    all_lit_rounds, all_fld_rounds = [], []
    seen_lit, seen_fld = set(), set()
    for taxon in taxon_order:
        sheet = sheets.get(taxon)
        if not sheet:
            continue
        for r in _lit_rounds_for(sheet):
            if r not in seen_lit:
                all_lit_rounds.append(r); seen_lit.add(r)
        for r in _field_rounds_for(sheet):
            if r not in seen_fld:
                all_fld_rounds.append(r); seen_fld.add(r)

    all_overview_rounds = all_lit_rounds + all_fld_rounds
    overview_group_defs = (
        parent_window.get_active_groups(all_overview_rounds)
        if parent_window and hasattr(parent_window, "get_active_groups")
        else []
    )

    def _make_rows(show_indiv=False, split_herp=False):
        rows = []

        def _append_group_rows(group_survey, show_indiv_for_rows):
            added = False
            for group_name, group_rns in overview_group_defs:
                if _infer_group_survey(group_rns) != group_survey:
                    continue
                per_t, per_t_sp = {}, {}
                for taxon in taxon_order:
                    sheet = sheets.get(taxon)
                    valid_rns = [r for r in group_rns if sheet and r in sheet.meta.round_names]
                    sp = _sp_for_rounds(sheet, valid_rns) if valid_rns else []
                    per_t_sp[taxon] = sp
                    per_t[taxon] = _summary_text(taxon, sp, valid_rns, show_indiv=show_indiv_for_rows)
                if split_herp:
                    herp_rns = [r for r in group_rns if sheets.get("herp") and r in sheets["herp"].meta.round_names]
                    amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), herp_rns, show_indiv=False)
                    per_t["amphib"] = amp_txt
                    per_t["reptile"] = rep_txt
                _, sp_c, prot_text = _all_prot_for(per_t_sp)
                prot = prot_text if sp_c else "-"
                _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
                disturb = disturb_text if disturb_n else "-"
                group_label = "문헌조사" if group_survey == "문헌" else "현지조사"
                rows.append((group_label, group_name, per_t, prot, disturb, True))
                added = True
            return added

        has_lit_groups = bool(overview_group_defs) and _append_group_rows("문헌", False)

        # 문헌조사 개별 차수
        if not has_lit_groups:
            for r in all_lit_rounds:
                sub = r.replace("문헌_", "")
                per_t, per_t_sp = {}, {}
                for taxon in taxon_order:
                    sheet = sheets.get(taxon)
                    sp = _sp_for_round(sheet, r) if sheet else []
                    per_t_sp[taxon] = sp
                    # 문헌조사 표는 개체수를 표시하지 않는다.
                    per_t[taxon] = _summary_text(taxon, sp, [r], show_indiv=False)
                if split_herp:
                    amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), [r], show_indiv=False)
                    per_t["amphib"] = amp_txt
                    per_t["reptile"] = rep_txt
                _, sp_c, prot_text = _all_prot_for(per_t_sp)
                prot = prot_text if sp_c else "-"
                _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
                disturb = disturb_text if disturb_n else "-"
                rows.append(("문헌조사", sub, per_t, prot, disturb, False))

        # 문헌조사 합계
        if all_lit_rounds:
            per_t, per_t_sp = {}, {}
            for taxon in taxon_order:
                sheet = sheets.get(taxon)
                sp = _sp_for_rounds(sheet, all_lit_rounds) if sheet else []
                per_t_sp[taxon] = sp
                # 문헌조사 표는 개체수를 표시하지 않는다.
                per_t[taxon] = _summary_text(taxon, sp, all_lit_rounds, show_indiv=False)
            if split_herp:
                amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), all_lit_rounds, show_indiv=False)
                per_t["amphib"] = amp_txt
                per_t["reptile"] = rep_txt
            _, sp_c, prot_text = _all_prot_for(per_t_sp)
            prot = prot_text if sp_c else "-"
            _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
            disturb = disturb_text if disturb_n else "-"
            rows.append(("문헌조사", "합계", per_t, prot, disturb, True))

        has_field_groups = bool(overview_group_defs) and _append_group_rows("현지", show_indiv)

        # 현지조사 개별 차수
        if not has_field_groups:
            for r in all_fld_rounds:
                sub = r.replace("현지_", "")
                per_t, per_t_sp = {}, {}
                for taxon in taxon_order:
                    sheet = sheets.get(taxon)
                    sp = _sp_for_round(sheet, r) if sheet else []
                    per_t_sp[taxon] = sp
                    per_t[taxon] = _summary_text(taxon, sp, [r], show_indiv=show_indiv)
                if split_herp:
                    amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), [r], show_indiv=False)
                    per_t["amphib"] = amp_txt
                    per_t["reptile"] = rep_txt
                _, sp_c, prot_text = _all_prot_for(per_t_sp)
                prot = prot_text if sp_c else "-"
                _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
                disturb = disturb_text if disturb_n else "-"
                rows.append(("현지조사", sub, per_t, prot, disturb, False))

        # 현지조사 합계
        if all_fld_rounds:
            per_t, per_t_sp = {}, {}
            for taxon in taxon_order:
                sheet = sheets.get(taxon)
                sp = _sp_for_rounds(sheet, all_fld_rounds) if sheet else []
                per_t_sp[taxon] = sp
                per_t[taxon] = _summary_text(taxon, sp, all_fld_rounds, show_indiv=show_indiv)
            if split_herp:
                amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), all_fld_rounds, show_indiv=False)
                per_t["amphib"] = amp_txt
                per_t["reptile"] = rep_txt
            _, sp_c, prot_text = _all_prot_for(per_t_sp)
            prot = prot_text if sp_c else "-"
            _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
            disturb = disturb_text if disturb_n else "-"
            rows.append(("현지조사", "합계", per_t, prot, disturb, True))

        # 전체 합계
        all_rounds = all_lit_rounds + all_fld_rounds
        per_t, per_t_sp = {}, {}
        for taxon in taxon_order:
            sheet = sheets.get(taxon)
            sp = _sp_for_rounds(sheet, all_rounds) if sheet else []
            per_t_sp[taxon] = sp
            per_t[taxon] = _summary_text(taxon, sp, all_rounds, show_indiv=show_indiv)
        if split_herp:
            amp_txt, rep_txt = _herp_split_text(per_t_sp.get("herp", []), all_rounds, show_indiv=False)
            per_t["amphib"] = amp_txt
            per_t["reptile"] = rep_txt
        _, sp_c, prot_text = _all_prot_for(per_t_sp)
        prot = prot_text if sp_c else "-"
        _, disturb_n, disturb_text = _all_disturb_for(per_t_sp)
        disturb = disturb_text if disturb_n else "-"
        rows.append(("합계", "", per_t, prot, disturb, True))
        return rows

    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 8)
    grp = QGroupBox("전분류군 현황")
    gl = QVBoxLayout(grp)
    gl.setContentsMargins(8, 20, 8, 8)

    split_herp_state = [False]
    show_indiv_state = [False]

    def _cols():
        if split_herp_state[0]:
            return ["구분", "", "포유류", "조류", "양서류", "파충류", "육상곤충류", "법정보호종", "생태계교란 생물"]
        return ["구분", "", "포유류", "조류", "양서·파충류", "육상곤충류", "법정보호종", "생태계교란 생물"]

    tbl = _make_tbl(_cols())
    tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    tbl.setWordWrap(True)
    tbl.setTextElideMode(Qt.ElideNone)

    def _bold_row(row):
        font = QFont(); font.setBold(True)
        for c in range(tbl.columnCount()):
            it = tbl.item(row, c)
            if it:
                it.setFont(font)
                it.setBackground(QColor(_BG))

    def _fit_tbl_overview():
        """긴 텍스트 열 줄바꿈 + 전체 너비 꽉 채우기 전용 레이아웃."""
        h = tbl.horizontalHeader()
        n = tbl.columnCount()
        text_cols = [n - 2, n - 1]
        fixed_cols = [c for c in range(n) if c not in text_cols]
        for c in fixed_cols:
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        for c in text_cols:
            h.setSectionResizeMode(c, QHeaderView.Interactive)
        h.setStretchLastSection(False)
        tbl.setMinimumWidth(0)
        tbl.setMaximumWidth(16777215)

        def _split_outside_brackets(text):
            parts = []
            buf = []
            stack = []
            pairs = {"(": ")", "[": "]", "{": "}"}
            closers = set(pairs.values())
            for ch in str(text or ""):
                if ch in pairs:
                    stack.append(pairs[ch])
                    buf.append(ch)
                    continue
                if ch in closers:
                    if stack and stack[-1] == ch:
                        stack.pop()
                    buf.append(ch)
                    continue
                if ch == "," and not stack:
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    continue
                buf.append(ch)
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            return parts

        def _wrap_detail_text(raw, text_w, fm):
            lines = str(raw or "").splitlines()
            if len(lines) < 2:
                return str(raw or "")
            out = [lines[0]]
            species_text = " ".join(line.strip() for line in lines[1:] if line.strip())
            if not species_text:
                return "\n".join(out)
            cur = ""
            max_line_w = max(60, int(text_w * 0.92))
            for part in _split_outside_brackets(species_text):
                candidate = part if not cur else f"{cur}, {part}"
                if cur and fm.horizontalAdvance(candidate) > max_line_w:
                    out.append(cur)
                    cur = part
                else:
                    cur = candidate
            if cur:
                out.append(cur)
            return "\n".join(out)

        def _apply_manual_row_heights():
            # setSpan + resizeRowsToContents 조합에서 과도한 행높이 버그가 있어 수동 계산으로 고정
            tbl.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
            tbl.doItemsLayout()

            fm = tbl.fontMetrics()

            viewport_w = tbl.viewport().width()
            if viewport_w <= 0:
                viewport_w = max(tbl.width() - tbl.verticalHeader().width() - tbl.frameWidth() * 2, 0)

            fixed_w = sum(tbl.columnWidth(c) for c in fixed_cols)
            available_w = max(viewport_w - fixed_w, 180 * len(text_cols))
            prot_w = max(180, int(available_w * 0.58))
            disturb_w = max(160, available_w - prot_w)
            tbl.setColumnWidth(n - 2, prot_w)
            tbl.setColumnWidth(n - 1, disturb_w)
            text_widths = {
                n - 2: max(prot_w - 18, 80),
                n - 1: max(disturb_w - 18, 80),
            }

            min_h = 32
            pad_h = 14

            for r in range(tbl.rowCount()):
                h_px = min_h
                for col in text_cols:
                    item = tbl.item(r, col)
                    raw = item.data(Qt.UserRole) if item else ""
                    txt = _wrap_detail_text(raw, text_widths[col], fm)
                    if item and item.text() != txt:
                        item.setText(txt)
                    line_count = max(1, len(str(txt or "").splitlines()))
                    h_px = max(h_px, line_count * fm.lineSpacing() + pad_h)
                tbl.setRowHeight(r, h_px)

        def _schedule_row_heights():
            QTimer.singleShot(0, _apply_manual_row_heights)

        tbl._overview_schedule_row_heights = _schedule_row_heights
        if not hasattr(tbl, "_overview_height_filter"):
            class _OverviewHeightFilter(QObject):
                def eventFilter(self, obj, event):
                    if event.type() in (QEvent.Resize, QEvent.Show):
                        schedule = getattr(tbl, "_overview_schedule_row_heights", None)
                        if callable(schedule):
                            schedule()
                    return False

            tbl._overview_height_filter = _OverviewHeightFilter(tbl)
            tbl.viewport().installEventFilter(tbl._overview_height_filter)
            tbl.installEventFilter(tbl._overview_height_filter)

        # 초기 진입 시점은 폭이 덜 안정적일 수 있어 표시 직후까지 재계산
        _apply_manual_row_heights()
        QTimer.singleShot(0, _apply_manual_row_heights)
        QTimer.singleShot(80, _apply_manual_row_heights)
        QTimer.singleShot(250, _apply_manual_row_heights)

    def _set_headers():
        cols = _cols()
        tbl.setColumnCount(len(cols))
        tbl.setHorizontalHeaderLabels(cols)

    ctrl = QHBoxLayout()
    ctrl.setContentsMargins(0, 0, 0, 0)
    ctrl.setSpacing(10)
    chk_split_herp = QCheckBox("양서/파충 분리")
    chk_show_indiv = QCheckBox("개체수 표시(조류·육상곤충)")
    chk_split_herp.setChecked(split_herp_state[0])
    chk_show_indiv.setChecked(show_indiv_state[0])
    ctrl.addWidget(chk_split_herp)
    ctrl.addWidget(chk_show_indiv)
    ctrl.addStretch(1)

    def _fill_tbl():
        _set_headers()
        rows = _make_rows(show_indiv=show_indiv_state[0], split_herp=split_herp_state[0])
        tbl.clearSpans()
        tbl.setRowCount(len(rows))

        # Apply row spans for group label column
        i = 0
        while i < len(rows):
            group = rows[i][0]
            span = 1
            while i + span < len(rows) and rows[i + span][0] == group:
                span += 1
            if group in ("문헌조사", "현지조사") and span > 1:
                tbl.setSpan(i, 0, span, 1)
            elif group == "합계":
                tbl.setSpan(i, 0, 1, 2)  # 합계 행: 구분(대)+구분(소) 병합
            i += span

        # Fill cells
        for ri, (group, sub, per_t, prot_text, disturb_text, is_total) in enumerate(rows):
            if ri == 0 or rows[ri - 1][0] != group:
                group_label = group
                if group == "문헌조사":
                    group_label = "문\n헌\n조\n사"
                elif group == "현지조사":
                    group_label = "현\n지\n조\n사"
                tbl.setItem(ri, 0, _item(group_label, Qt.AlignCenter | Qt.AlignVCenter))
            tbl.setItem(ri, 1, _item(sub, Qt.AlignCenter | Qt.AlignVCenter))

            if split_herp_state[0]:
                val_cols = [
                    per_t.get("mammal", "-"),
                    per_t.get("bird", "-"),
                    per_t.get("amphib", "-"),
                    per_t.get("reptile", "-"),
                    per_t.get("insect", "-"),
                ]
            else:
                val_cols = [
                    per_t.get("mammal", "-"),
                    per_t.get("bird", "-"),
                    per_t.get("herp", "-"),
                    per_t.get("insect", "-"),
                ]

            ci = 2
            for txt in val_cols:
                tbl.setItem(ri, ci, _item(txt, Qt.AlignCenter | Qt.AlignVCenter))
                ci += 1

            prot_item = _item(prot_text, Qt.AlignLeft | Qt.AlignTop)
            prot_item.setData(Qt.UserRole, prot_text)
            tbl.setItem(ri, ci, prot_item)
            tbl.setCellWidget(ri, ci, None)
            disturb_item = _item(disturb_text, Qt.AlignLeft | Qt.AlignTop)
            disturb_item.setData(Qt.UserRole, disturb_text)
            tbl.setItem(ri, ci + 1, disturb_item)
            tbl.setCellWidget(ri, ci + 1, None)
            if is_total:
                _bold_row(ri)

        _fit_tbl_overview()

    _fill_tbl()

    def _on_split_herp(v):
        split_herp_state[0] = bool(v)
        _fill_tbl()

    def _on_show_indiv(v):
        show_indiv_state[0] = bool(v)
        _fill_tbl()

    chk_split_herp.toggled.connect(_on_split_herp)
    chk_show_indiv.toggled.connect(_on_show_indiv)

    if parent_window and hasattr(parent_window, "sig_sent_settings"):
        parent_window.sig_sent_settings.connect(_fill_tbl)
    gl.addLayout(ctrl)
    gl.addWidget(make_copy_button(tbl))
    gl.addWidget(tbl, stretch=1)
    lay.addWidget(grp, stretch=1)
    return w


def _build_aqua_overview_tab(parsed: dict, parent_window=None) -> QWidget | None:
    from parser import ParsedAquatic, ParsedProtected

    taxon_items = [
        (label, taxon, obj)
        for label, taxon in (("어류상", "fish"), ("저서상", "benthos"))
        for obj in parsed.values()
        if isinstance(obj, ParsedAquatic) and obj.taxon == taxon and obj.species
    ]
    if not taxon_items:
        return None

    prot_sheet = next((obj for obj in parsed.values() if isinstance(obj, ParsedProtected)), None)

    def _prn(rn: str):
        parts = str(rn or "").split("_", 2)
        sec = parts[0] if len(parts) > 0 else ""
        if len(parts) == 3:
            return sec, parts[1], parts[2]
        if len(parts) == 2:
            return sec, "1차", parts[1]
        return sec, "", ""

    def _detail_rounds(sheet):
        out = []
        for rn in sheet.meta.round_names:
            sec, rnd, site = _prn(rn)
            last = site or rnd
            if sec == "현지" and last not in ("", "합계", "종합"):
                out.append(rn)
        return out

    def _present_for(sp, rns):
        return any(_has_present(sp.rounds.get(rn)) for rn in rns)

    def _indiv_count_for(sp, rns):
        total = 0
        for rn in rns:
            val = sp.rounds.get(rn)
            n = _int(val)
            if n > 0:
                total += n
        return total

    def _unique_count(rows, attr):
        return len({
            str(getattr(sp, attr, "") or "").strip()
            for sp, _, _ in rows
            if str(getattr(sp, attr, "") or "").strip()
        })

    def _taxa_count_text(rows, taxon):
        if not rows:
            return "-"
        indiv_n = sum(cnt for _, _, cnt in rows)
        if taxon == "fish":
            return f"{_unique_count(rows, 'family')}과 {len(rows)}종 {indiv_n:,}개체"
        return (
            f"{_unique_count(rows, 'phylum')}문 "
            f"{_unique_count(rows, 'class_name')}강 "
            f"{_unique_count(rows, 'order')}목 "
            f"{_unique_count(rows, 'family')}과 "
            f"{len(rows)}종 {indiv_n:,}개체"
        )

    def _dominants(rows):
        if not rows:
            return "-", "-"
        count_rows = [row for row in rows if row[2] > 0]
        if not count_rows:
            return "-", "-"
        ordered = sorted(count_rows, key=lambda x: (-x[2], getattr(x[0], "kor_name", "") or getattr(x[0], "sci_name", "")))
        names = [getattr(sp, "kor_name", "") or getattr(sp, "sci_name", "") or "-" for sp, _, _ in ordered]
        return names[0], names[1] if len(names) > 1 else "-"

    def _metrics(rows):
        counts = [cnt for _, _, cnt in rows if cnt > 0]
        total = sum(counts)
        s = len(counts)
        if total <= 0 or s <= 0:
            return "-", "-", "-", "-"
        h = sum(-(cnt / total) * math.log(cnt / total) for cnt in counts)
        e = h / math.log(s) if s > 1 else 0.0
        ri = (s - 1) / math.log(total) if total > 1 else 0.0
        top = sorted(counts, reverse=True)
        di = (top[0] + (top[1] if len(top) > 1 else 0)) / total
        return f"{di:.2f}", f"{h:.2f}", f"{ri:.2f}", f"{e:.2f}"

    def _prot_text(rows, taxon):
        if not prot_sheet or not rows:
            return "-"
        row_names = set()
        for sp, _, _ in rows:
            name = getattr(sp, "kor_name", "")
            if name:
                row_names.add(name)
        by_name = {}
        for psp in prot_sheet.species:
            pname = getattr(psp, "kor_name", "")
            if pname not in row_names:
                continue
            if not _prot_group_matches(taxon, getattr(psp, "group", ""), psp):
                continue
            by_name.setdefault(pname, [])
            grade = _prot_grade_str(psp)
            if grade and grade not in by_name[pname]:
                by_name[pname].append(grade)
        if not by_name:
            return "-"
        return ", ".join(f"{name}({', '.join(grades)})" if grades else name for name, grades in by_name.items())

    def _disturb_text(rows):
        species = [sp for sp, _, _ in rows]
        n, clause = _ecosystem_disturber_list(prot_sheet, species)
        return clause if n else "-"

    def _make_table(sheet, taxon):
        round_order, station_order = [], []
        round_to_rns, station_to_rns = {}, {}
        entries = [(sp, taxon) for sp in sheet.species]
        for rn in _detail_rounds(sheet):
            _, rnd, site = _prn(rn)
            if rnd and rnd not in round_order:
                round_order.append(rnd)
            if site and site not in station_order:
                station_order.append(site)
            round_to_rns.setdefault(rnd, [])
            if rn not in round_to_rns[rnd]:
                round_to_rns[rnd].append(rn)
            station_to_rns.setdefault(site, [])
            if rn not in station_to_rns[site]:
                station_to_rns[site].append(rn)

        all_rns = []
        for rns in round_to_rns.values():
            for rn in rns:
                if rn not in all_rns:
                    all_rns.append(rn)
        if not all_rns:
            return None

        def _species_for(rns):
            return [(sp, taxon, _indiv_count_for(sp, rns)) for sp, taxon in entries if _present_for(sp, rns)]

        def _row(group, sub, station, rns, is_total=False):
            rows = _species_for(rns)
            dom, subdom = _dominants(rows)
            di, h, ri, e = _metrics(rows)
            return [
                group, sub, station, _taxa_count_text(rows, taxon),
                dom, subdom, di, h, ri, e,
                _prot_text(rows, taxon), _disturb_text(rows),
                is_total,
            ]

        data_rows = []
        group_defs = parent_window.get_active_groups(all_rns) if parent_window and hasattr(parent_window, "get_active_groups") else []
        if group_defs:
            for group_name, group_rns in group_defs:
                data_rows.append(_row("그룹", "", group_name, group_rns, True))
            data_rows.append(_row("종합", "", "종합", all_rns, True))
        else:
            for rnd in round_order:
                for station in station_order:
                    rns = [rn for rn in round_to_rns.get(rnd, []) if _prn(rn)[2] == station]
                    if rns:
                        data_rows.append(_row("현지조사", rnd, station, rns))
                data_rows.append(_row("현지조사", rnd, "종합", round_to_rns.get(rnd, []), True))

            for station in station_order:
                data_rows.append(_row("종합", "", station, station_to_rns.get(station, [])))
            data_rows.append(_row("종합", "", "종합", all_rns, True))

        headers = [
            "", "", "구분", "종수",
            "우점종", "아우점종", "우점도(DI)", "종다양도(H)", "종풍부도(RI)", "균등도(J)",
            "법정보호종", "생태계교란 생물",
        ]
        tbl = _make_tbl(headers)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tbl.setWordWrap(True)
        tbl.setRowCount(len(data_rows))

        def _bold_row(row):
            font = QFont(); font.setBold(True)
            for c in range(tbl.columnCount()):
                it = tbl.item(row, c)
                if it:
                    it.setFont(font)
                    it.setBackground(QColor(_BG))

        for ri, row in enumerate(data_rows):
            for ci, txt in enumerate(row[:-1]):
                if ci == 0 and txt == "현지조사":
                    txt = "현\n지\n조\n사"
                align = Qt.AlignLeft | Qt.AlignVCenter if ci >= len(headers) - 2 else Qt.AlignCenter | Qt.AlignVCenter
                tbl.setItem(ri, ci, _item(txt, align))
            if row[-1]:
                _bold_row(ri)

        if group_defs:
            n_groups = len(data_rows) - 1  # exclude total row
            if n_groups > 0:
                tbl.setSpan(0, 0, n_groups, 2)
            tbl.setSpan(len(data_rows) - 1, 0, 1, 2)  # total row spans cols 0-1
        else:
            first_field = next((i for i, r in enumerate(data_rows) if r[0] == "현지조사"), len(data_rows))
            first_summary = next((i for i, r in enumerate(data_rows) if r[0] == "종합"), len(data_rows))
            if first_field > 0:
                tbl.setSpan(0, 0, first_field, 2)
            if first_summary > first_field + 1:
                tbl.setSpan(first_field, 0, first_summary - first_field, 1)
            if first_summary < len(data_rows):
                tbl.setSpan(first_summary, 0, len(data_rows) - first_summary, 2)

            i = first_field
            while i < first_summary:
                rnd = data_rows[i][1]
                span = 1
                while i + span < first_summary and data_rows[i + span][1] == rnd:
                    span += 1
                if span > 1:
                    tbl.setSpan(i, 1, span, 1)
                i += span

        h = tbl.horizontalHeader()
        for c in range(tbl.columnCount()):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(tbl.columnCount() - 1, QHeaderView.Stretch)
        tbl.verticalHeader().setDefaultSectionSize(34)
        _auto_fit_table(tbl)
        # 종합 섹션의 지점별 행만 토글 대상 (현지조사 지점 행은 항상 표시)
        detail_row_indices = [i for i, row in enumerate(data_rows)
                              if row[0] == "종합" and not row[-1]]
        return tbl, detail_row_indices

    def _make_page(sheet, taxon):
        result = _make_table(sheet, taxon)
        if result is None:
            return None
        tbl, detail_rows = result
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        grp = QGroupBox("전분류군 현황")
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(8, 20, 8, 8)

        chk = QCheckBox("지점별 종합 보기")
        chk.setChecked(False)

        def _toggle(checked):
            for i in detail_rows:
                tbl.setRowHidden(i, not checked)

        chk.toggled.connect(_toggle)
        _toggle(False)  # 초기 상태 적용

        top_bar = QHBoxLayout()
        top_bar.addWidget(make_copy_button(tbl))
        top_bar.addStretch()
        top_bar.addWidget(chk)

        gl.addLayout(top_bar)
        gl.addWidget(tbl, stretch=1)
        lay.addWidget(grp, stretch=1)
        return page

    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    for label, taxon, sheet in taxon_items:
        page = _make_page(sheet, taxon)
        if page is not None:
            tabs.addTab(page, label)

    if tabs.count() == 0:
        return None
    return tabs


# ── 워커 스레드 ───────────────────────────────────────────────────────────────
class LoadWorker(QThread):
    done  = Signal(dict, dict)
    error = Signal(str)

    def __init__(self, path):
        super().__init__(); self.path = path

    def run(self):
        try:
            parsed = load_xlsx(self.path)
            stats  = analyze_all(parsed)
            self.done.emit(parsed, stats)
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


def _auto_pie_frame_size(radius, cfg):
    try:
        r = float(radius)
    except Exception:
        r = SETTINGS.pie_radius
    try:
        offset = float((cfg or {}).get("pie_label_offset", SETTINGS.pie_label_offset))
    except Exception:
        offset = SETTINGS.pie_label_offset
    side = int(360 + (r * 170) + (offset * 70))
    side = max(420, min(900, side))
    return [side, side]


class RadiusSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, value, parent=None):
        super().__init__(parent)
        self._lo = 0.35
        self._hi = 1.5
        self._step = 0.01
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._sld = QSlider(Qt.Horizontal)
        self._sld.setRange(0, int(round((self._hi - self._lo) / self._step)))
        self._lbl = QLabel()
        self._lbl.setFixedWidth(45)
        self._lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._sld, 1)
        lay.addWidget(self._lbl)
        self._sld.valueChanged.connect(self._on_change)
        self.setValue(value)

    def _on_change(self, tick):
        v = self.value()
        self._lbl.setText(f"{v:.2f}")
        self.valueChanged.emit(v)

    def value(self):
        return round(self._lo + self._sld.value() * self._step, 2)

    def setValue(self, value):
        try:
            v = float(value)
        except Exception:
            v = SETTINGS.pie_radius
        tick = int(round((max(self._lo, min(self._hi, v)) - self._lo) / self._step))
        self._sld.setValue(max(0, min(self._sld.maximum(), tick)))
        self._lbl.setText(f"{self.value():.2f}")


class FloatValueSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, lo, hi, step, value, decimals=2, parent=None):
        super().__init__(parent)
        self._lo = float(lo)
        self._hi = float(hi)
        self._step = float(step)
        self._decimals = int(decimals)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._sld = QSlider(Qt.Horizontal)
        self._sld.setRange(0, int(round((self._hi - self._lo) / self._step)))
        self._lbl = QLabel()
        self._lbl.setFixedWidth(45)
        self._lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._sld, 1)
        lay.addWidget(self._lbl)
        self._sld.valueChanged.connect(self._on_change)
        self.setValue(value)

    def _on_change(self, tick):
        v = self.value()
        self._lbl.setText(f"{v:.{self._decimals}f}")
        self.valueChanged.emit(v)

    def value(self):
        return round(self._lo + self._sld.value() * self._step, self._decimals)

    def setValue(self, value):
        try:
            v = float(value)
        except Exception:
            v = self._lo
        tick = int(round((max(self._lo, min(self._hi, v)) - self._lo) / self._step))
        self._sld.setValue(max(0, min(self._sld.maximum(), tick)))
        self._lbl.setText(f"{self.value():.{self._decimals}f}")


class GraphDefaultSettingsDialog(QDialog):
    def __init__(self, kinds: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("그래프 세부 설정")
        self.resize(1240, 720)
        self.setMinimumSize(1100, 640)
        self.setStyleSheet(COMMON_QSS)
        self._kinds = kinds
        self._defaults = {k: dict(v.get("default", {}) or {}) for k, v in kinds.items()}
        self._color_keys = ["color_mode"]
        self._color_settings = SETTINGS.to_dict(self._color_keys)
        self._current = ""
        self._widgets = {}

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        body.setSpacing(10)
        self.lst = QListWidget()
        self.lst.setFixedWidth(190)
        lw = QListWidgetItem("색상 설정")
        lw.setData(Qt.UserRole, "__colors__")
        self.lst.addItem(lw)
        for kind, item in kinds.items():
            lw = QListWidgetItem(item.get("label", kind))
            lw.setData(Qt.UserRole, kind)
            self.lst.addItem(lw)
        self.lst.currentRowChanged.connect(self._on_select)
        body.addWidget(self.lst, 0)

        self.form_box = QGroupBox("설정")
        self.form_box.setFixedWidth(320)
        self.form = QFormLayout(self.form_box)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        body.addWidget(self.form_box, 0)

        self.preview_box = QGroupBox("예시 미리보기")
        self.preview_lay = QVBoxLayout(self.preview_box)
        self.preview_lay.setContentsMargins(8, 14, 8, 8)
        self.preview_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_canvas = None
        self.preview_frame = None
        self._preview_kind = ""
        self._syncing_preview_size = False
        body.addWidget(self.preview_box, 1)
        root.addLayout(body, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        if self.lst.count():
            self.lst.setCurrentRow(0)

    def defaults(self):
        self._sync_current()
        SETTINGS.from_dict(self._color_settings, keys=self._color_keys)
        return self._defaults

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._widgets = {}
        self._preview_kind = ""

    def _add_spin(self, key, label, value, min_v, max_v, step=1, decimals=0):
        if decimals:
            w = QDoubleSpinBox()
            w.setDecimals(decimals)
            w.setSingleStep(step)
        else:
            w = QSpinBox()
            w.setSingleStep(int(step))
        w.setRange(min_v, max_v)
        w.setValue(value)
        self.form.addRow(label, w)
        self._widgets[key] = w

    def _add_bool(self, key, label, value):
        w = QCheckBox()
        w.setChecked(bool(value))
        self.form.addRow(label, w)
        self._widgets[key] = w

    def _add_combo(self, key, label, value, items):
        w = QComboBox()
        for text, data in items:
            w.addItem(text, data)
        idx = w.findData(value)
        w.setCurrentIndex(idx if idx >= 0 else 0)
        self.form.addRow(label, w)
        self._widgets[key] = w

    def _add_color(self, key, label, value):
        btn = QPushButton(str(value or "#4472C4"))
        btn.setFixedHeight(26)
        def _paint(color):
            btn.setText(color)
            btn.setStyleSheet(f"QPushButton{{background:{color};border:1px solid #94A3B8;border-radius:4px;}}")
        _paint(str(value or "#4472C4"))
        def _pick():
            c = QColorDialog.getColor(QColor(btn.text()), self, label)
            if c.isValid():
                _paint(c.name().upper())
                self._refresh_preview_from_widgets()
        btn.clicked.connect(_pick)
        self.form.addRow(label, btn)
        self._widgets[key] = btn

    def _add_size_slider(self, key, label, value, min_v, max_v):
        w = CanvasSizeSlider(min_v, max_v, int(value))
        self.form.addRow(label, w)
        self._widgets[key] = w
        w.valueChanged.connect(lambda _=None: self._refresh_preview_from_widgets())

    def _add_radius_slider(self, key, label, value):
        w = RadiusSlider(value)
        self.form.addRow(label, w)
        self._widgets[key] = w
        w.valueChanged.connect(lambda _=None: self._refresh_preview_from_widgets())

    def _add_float_slider(self, key, label, value, min_v, max_v, step=0.05, decimals=2):
        w = FloatValueSlider(min_v, max_v, step, value, decimals)
        self.form.addRow(label, w)
        self._widgets[key] = w
        w.valueChanged.connect(lambda _=None: self._refresh_preview_from_widgets())

    def _auto_pie_frame_size(self, radius, cfg):
        return _auto_pie_frame_size(radius, cfg)

    def _example_table(self, rows):
        tbl = QTableWidget(len(rows), 4)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                tbl.setItem(r, c, QTableWidgetItem(str(value)))
        return tbl

    def _on_select(self, row):
        self._sync_current()
        item = self.lst.item(row)
        if not item:
            return
        self._current = item.data(Qt.UserRole)
        self._build_form(self._current)
        self._refresh_preview_from_widgets()

    def _build_form(self, kind):
        self._clear_form()
        if kind == "__colors__":
            self._add_combo("settings.color_mode", "색상 모드", self._color_settings.get("color_mode", "auto"), [
                ("자동", "auto"), ("회색조", "gray"), ("단색", "solid")
            ])
            for widget in self._widgets.values():
                if isinstance(widget, QComboBox):
                    widget.currentIndexChanged.connect(lambda _=None: self._refresh_preview_from_widgets())
            return
        default = self._defaults.get(kind, {})
        cfg = dict(default.get("cfg", {}) or {})
        is_pie = kind.startswith("pie")
        is_dom = kind == "bar_dominance"
        is_div = kind == "bar_diversity"
        is_plant_bar = kind.startswith("plant_")

        if is_pie:
            self._add_radius_slider("radius", "그래프 크기", float(default.get("radius", SETTINGS.pie_radius)))
            self._add_spin("cfg.pie_fontsize", "글씨 크기", int(cfg.get("pie_fontsize", SETTINGS.pie_fontsize)), 4, 24)
            self._add_bool("cfg.pie_show_leaders", "지시선 표시", bool(cfg.get("pie_show_leaders", SETTINGS.pie_show_leaders)))
            self._add_spin("cfg.pie_start_angle", "시작 각도", float(cfg.get("pie_start_angle", SETTINGS.pie_start_angle)), 0, 360, 5, 1)
            self._add_spin("cfg.pie_label_offset", "라벨 거리", float(cfg.get("pie_label_offset", SETTINGS.pie_label_offset)), 0.0, 2.0, 0.05, 2)
            self._add_spin("cfg.pie_edge_width", "테두리 두께", float(cfg.get("pie_edge_width", SETTINGS.pie_edge_width)), 0.0, 5.0, 0.1, 1)
            self._add_spin("cfg.pie_leader_width", "리더선 두께", float(cfg.get("pie_leader_width", SETTINGS.pie_leader_width)), 0.0, 5.0, 0.1, 1)
            self._add_spin("cfg.pie_leader_gap", "지시선 숨김 범위", float(cfg.get("pie_leader_gap", SETTINGS.pie_leader_gap)), 0.0, 2.0, 0.05, 2)
        else:
            # left 순서: 우점도 → 글씨 크기
            if is_dom:
                self._add_spin("cfg.dom_pct", "우점도 기준", float(cfg.get("dom_pct", SETTINGS.dom_pct)), 0.0, 100.0, 0.5, 1)
            self._add_spin("cfg.bar_fontsize", "글씨 크기", int(cfg.get("bar_fontsize", SETTINGS.bar_fontsize)), 4, 24)
            # mid 순서: 막대 두께 → 그래프 너비/높이
            if is_div:
                self._add_float_slider("cfg.div_bar_width", "막대 너비", float(cfg.get("div_bar_width", SETTINGS.div_bar_width)), 0.2, 0.9, 0.05, 2)
                self._add_float_slider("cfg.div_bar_gap", "막대 간격", float(cfg.get("div_bar_gap", SETTINGS.div_bar_gap)), 0.5, 3.0, 0.05, 2)
            else:
                if is_dom:
                    self._add_float_slider("cfg.bar_h_height", "막대(가로) 두께", float(cfg.get("bar_h_height", SETTINGS.bar_h_height)), 0.2, 1.0, 0.05, 2)
                self._add_float_slider("cfg.bar_v_width", "막대(세로) 두께", float(cfg.get("bar_v_width", SETTINGS.bar_v_width)), 0.2, 0.95, 0.05, 2)
            self._add_float_slider("cfg.graph_width_scale", "그래프 너비", float(cfg.get("graph_width_scale", 1.0)), 0.3, 1.1, 0.05, 2)
            self._add_float_slider("cfg.graph_height_scale", "그래프 높이", float(cfg.get("graph_height_scale", 1.0)), 0.3, 1.25, 0.05, 2)
            self._add_spin("cfg.axis_min", "축 최소값", float(cfg.get("axis_min", SETTINGS.axis_min)), -10000.0, 10000.0, 0.5, 2)
            self._add_spin("cfg.axis_max", "축 최대값", float(cfg.get("axis_max", SETTINGS.axis_max)), 0.0, 10000.0, 0.5, 2)
            self._add_spin("cfg.axis_step", "축 단위", float(cfg.get("axis_step", SETTINGS.axis_step)), 0.0, 10000.0, 0.5, 2)
            # right 순서: 방향 → 정렬 → 범례 → 개체수
            if is_dom:
                self._add_combo("cfg.bar_horiz", "방향", cfg.get("bar_horiz", SETTINGS.bar_horiz), [("가로", True), ("세로", False)])
                self._add_combo("cfg.bar_sort", "정렬", cfg.get("bar_sort", SETTINGS.bar_sort), [("내림차순", "desc"), ("오름차순", "asc"), ("정렬 안 함", "none")])
                self._add_bool("cfg.show_legend", "범례 표시", bool(cfg.get("show_legend", SETTINGS.show_legend)))
                self._add_bool("cfg.bar_count_label_inside", "개체수 라벨", bool(cfg.get("bar_count_label_inside", SETTINGS.bar_count_label_inside)))
        for key, widget in self._widgets.items():
            if key in ("frame_width", "frame_height"):
                continue
            if isinstance(widget, (RadiusSlider, FloatValueSlider)):
                continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(lambda _=None: self._refresh_preview_from_widgets())
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(lambda _=None: self._refresh_preview_from_widgets())
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(lambda _=None: self._refresh_preview_from_widgets())

    def _current_default_from_widgets(self) -> dict:
        if self._current == "__colors__":
            for key, w in self._widgets.items():
                name = key.split(".", 1)[1]
                if isinstance(w, QComboBox):
                    self._color_settings[name] = w.currentData()
                elif isinstance(w, QPushButton):
                    self._color_settings[name] = w.text()
            return {}
        cur = {}
        cfg = {}
        for key, w in self._widgets.items():
            if isinstance(w, QComboBox):
                val = w.currentData()
            elif isinstance(w, QCheckBox):
                val = w.isChecked()
            else:
                val = w.value()
            if key == "radius":
                cur["radius"] = float(val)
            elif key.startswith("cfg."):
                cfg[key.split(".", 1)[1]] = val
        cur["cfg"] = cfg
        return cur

    def _clear_preview(self):
        while self.preview_lay.count():
            item = self.preview_lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.preview_canvas = None
        self.preview_frame = None
        self._preview_kind = ""
        self._syncing_radius = False

    def _make_preview_canvas(self, kind):
        is_pie = kind.startswith("pie")
        if is_pie:
            cv = PieCanvas()
            cv._setting_mode = "pie"
        else:
            cv = _Canvas(6, 4)
            cv._setting_mode = "bird_combo" if kind == "bar_dominance" else ("diversity" if kind == "bar_diversity" else "bar")

        if is_pie:
            frame = QFrame()
            frame.setFrameShape(QFrame.NoFrame)
            frame.setStyleSheet("QFrame { border: none; background: transparent; }")
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.addWidget(cv)
        else:
            frame = ResizableCanvasFrame(cv, min_w=300, min_h=200)
            frame.resized_sig.connect(self._on_preview_frame_resized)

        title = (self._kinds.get(kind, {}) or {}).get("label", kind)
        graph_box = CanvasGroupBox(f"{title} - 예시")
        graph_lay = QVBoxLayout(graph_box)
        graph_lay.setContentsMargins(6, 20, 6, 6)

        sc = QScrollArea()
        sc.setMinimumSize(620, 460)
        sc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        sc.setWidget(frame)
        sc.setAlignment(Qt.AlignCenter)
        graph_lay.addWidget(sc)
        graph_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.preview_lay.addWidget(graph_box)
        self.preview_canvas = cv
        self.preview_frame = frame
        self._preview_kind = kind
        if is_pie:
            cv._radius_changed_cb = self._on_preview_radius_changed

    def _on_preview_radius_changed(self, radius):
        if self._syncing_radius:
            return
        slider = self._widgets.get("radius")
        if slider is None:
            return
        try:
            self._syncing_radius = True
            slider.setValue(float(radius))
        finally:
            self._syncing_radius = False
        self._refresh_preview_from_widgets()

    def _on_preview_frame_resized(self, w, h):
        if self._syncing_preview_size:
            return
        ww = self._widgets.get("frame_width")
        hh = self._widgets.get("frame_height")
        try:
            self._syncing_preview_size = True
            if ww is not None:
                ww.setValue(int(w))
            if hh is not None:
                hh.setValue(int(h))
        finally:
            self._syncing_preview_size = False
        self._refresh_preview_from_widgets()

    def _refresh_preview_from_widgets(self):
        if not self._current or not self._widgets:
            return
        default = self._current_default_from_widgets()
        is_pie = self._current.startswith("pie")
        if self._current == "__colors__":
            SETTINGS.from_dict(self._color_settings, keys=self._color_keys)
            self._clear_preview()
            return
        if self.preview_canvas is None or self._preview_kind != self._current:
            self._clear_preview()
            self._make_preview_canvas(self._current)
        cv = self.preview_canvas
        cfg = default.get("cfg", {})
        if isinstance(cfg, dict):
            cv._cfg.clear()
            cv._cfg.update(cfg)
        if "radius" in default and hasattr(cv, "_radius"):
            cv._radius = float(default["radius"])
        size = self._auto_pie_frame_size(getattr(cv, "_radius", SETTINGS.pie_radius), cfg) if is_pie else [720, SETTINGS.graph_height]
        if isinstance(size, list) and len(size) == 2:
            w = max(300, int(size[0]))
            h = max(200, int(size[1]))
            cv._cfg["initial_graph_width"] = w
            cv._cfg["initial_graph_height"] = h
            if self.preview_frame is not None:
                self.preview_frame.setFixedSize(w, h)
        if is_pie:
            cv._show_leader_gap_guide = True
            cv.draw_pie(self._pie_preview_data())
        else:
            self._draw_bar_preview(cv, self._current)

    def _pie_preview_data(self):
        item = (self._kinds.get(self._current, {}) or {})
        source = item.get("source_canvas")
        provider = getattr(source, "_preview_data_provider", None)
        if callable(provider):
            try:
                data = provider()
                if data:
                    return dict(data)
            except Exception:
                pass
        data = getattr(source, "_data", None)
        if data:
            return dict(data)
        if self._current == "pie_life":
            return {"교목": 22.2, "관목": 11.1, "초본": 55.6, "만경목": 11.1}
        return {"우제목": 22.2, "식육목": 55.6, "설치목": 11.1, "첨서목": 11.1}

    def _draw_bar_preview(self, cv, kind):
        item = (self._kinds.get(kind, {}) or {})
        source = item.get("source_canvas")
        draw = getattr(source, "_preview_draw", None)
        if callable(draw):
            try:
                draw(cv)
                return
            except Exception:
                pass
        if kind == "bar_diversity":
            try:
                from land_tab import _draw_diversity_bar
                tbl = self._example_table([
                    ["종다양도지수(H')", "3.13", "", ""],
                    ["종풍부도지수(RI)", "7.55", "", ""],
                    ["균등도지수(EI)", "0.77", "", ""],
                ])
                _draw_diversity_bar(cv, tbl)
                return
            except Exception:
                pass
        if kind == "bar_dominance":
            try:
                from land_tab import _draw_bird_combo
                tbl = self._example_table([
                    ["", "예시 A", "42", "42.0"],
                    ["", "예시 B", "28", "28.0"],
                    ["", "예시 C", "18", "18.0"],
                    ["", "예시 D", "12", "12.0"],
                    ["", "합계", "100", "100.0"],
                ])
                _draw_bird_combo(cv, tbl)
                return
            except Exception:
                pass
        fig = cv.figure
        fig.clf()
        ax = fig.add_subplot(111)
        fs = int(cv._cfg.get("bar_fontsize", SETTINGS.bar_fontsize))
        value_axis_is_x = False

        def _apply_preview_axis():
            axis_min = float(cv._cfg.get("axis_min", SETTINGS.axis_min) or 0)
            axis_max = float(cv._cfg.get("axis_max", SETTINGS.axis_max) or 0)
            axis_step = float(cv._cfg.get("axis_step", SETTINGS.axis_step) or 0)
            if axis_max > 0 and axis_min < axis_max:
                if value_axis_is_x:
                    ax.set_xlim(axis_min, axis_max)
                else:
                    ax.set_ylim(axis_min, axis_max)
            elif axis_min != 0:
                if value_axis_is_x:
                    ax.set_xlim(left=axis_min)
                else:
                    ax.set_ylim(bottom=axis_min)
            if axis_step > 0:
                import matplotlib.ticker as ticker
                if value_axis_is_x:
                    ax.xaxis.set_major_locator(ticker.MultipleLocator(axis_step))
                else:
                    ax.yaxis.set_major_locator(ticker.MultipleLocator(axis_step))

        if kind == "bar_dominance":
            labels = ["예시 A", "예시 B", "예시 C", "기타"]
            vals = [36, 24, 18, 8]
            if cv._cfg.get("bar_horiz", SETTINGS.bar_horiz):
                value_axis_is_x = True
                y = list(range(len(labels)))
                ax.barh(y, vals, height=float(cv._cfg.get("bar_h_height", SETTINGS.bar_h_height)), color="#4472C4")
                ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=fs); ax.invert_yaxis()
            else:
                ax.bar(labels, vals, width=float(cv._cfg.get("bar_v_width", SETTINGS.bar_v_width)), color="#4472C4")
                ax.tick_params(axis="x", labelsize=fs)
            ax.set_title("예시 우점도 그래프", fontsize=fs + 1)
        elif kind == "bar_diversity":
            labels = ["H'", "RI", "EI"]
            vals = [3.13, 7.55, 0.77]
            gap = float(cv._cfg.get("div_bar_gap", SETTINGS.div_bar_gap))
            width = float(cv._cfg.get("div_bar_width", SETTINGS.div_bar_width))
            _n = len(vals)
            _span = (_n - 1) * gap
            x = [i * gap - _span / 2 for i in range(_n)]
            ax.bar(x, vals, width=width, color="#70AD47")
            _fixed_half = (_n - 1) * 0.5 + 0.5
            _axis_half = max(_fixed_half, _span / 2 + width / 2 + 0.1)
            ax.set_xlim(-_axis_half, _axis_half)
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.set_title("예시 다양도 그래프", fontsize=fs + 1)
            ax.tick_params(axis="x", labelsize=fs)
        else:
            labels = ["예시 A", "예시 B", "예시 C", "예시 D"]
            vals = [18, 28, 12, 36]
            ax.bar(labels, vals, width=float(cv._cfg.get("bar_v_width", SETTINGS.bar_v_width)), color="#4472C4")
            ax.set_title("예시 그래프", fontsize=fs + 1)
            ax.tick_params(axis="x", labelsize=fs)
        _apply_preview_axis()
        ax.tick_params(axis="y", labelsize=fs)
        fig.tight_layout()
        cv.draw()

    def _sync_current(self):
        if not self._current or not self._widgets:
            return
        if self._current == "__colors__":
            self._current_default_from_widgets()
            return
        cur = self._defaults.setdefault(self._current, {})
        cfg = dict(cur.get("cfg", {}) or {})
        radius = cur.get("radius", SETTINGS.pie_radius)
        for key, w in self._widgets.items():
            if isinstance(w, QComboBox):
                val = w.currentData()
            elif isinstance(w, QCheckBox):
                val = w.isChecked()
            else:
                val = w.value()
            if key == "radius":
                radius = float(val)
                cur["radius"] = radius
            elif key.startswith("cfg."):
                cfg[key.split(".", 1)[1]] = val
        cur["cfg"] = cfg
        cur.pop("frame_size", None)


# ── 메인 윈도우 ───────────────────────────────────────────────────────────────
class TaxaWindow(QMainWindow):
    sig_chart_settings = Signal()   # 그래프/소수점 설정 완료
    sig_sent_settings  = Signal()   # 문장 설정 완료
    _PROGRAM_DEFAULTS_KEY = "program_defaults/v1"

    def __init__(self, excel_path: str = "", parent=None):
        super().__init__(parent)
        install_global_no_focus_rect_style(QApplication.instance())
        self._program_settings = QSettings("susippi", "taxa_analyzer")
        self._program_graph_defaults = {}
        self._load_program_defaults(reset_first=True)
        self.setWindowTitle("종목록 분석")
        self.resize(1100, 780)
        self.showMaximized()
        self.setStyleSheet(COMMON_QSS)
        self._worker   = None
        self._cur_path = ""
        self._groups = []
        self._pending_ratio_state = []
        self._pending_graph_state = []
        self._loaded_sentence_snapshots = []
        self._build_ui()

        if excel_path:
            QTimer.singleShot(0, lambda: self._load(excel_path))

    def set_excel_path(self, path: str):
        if path and path != self._cur_path:
            self._load(path)

    def _build_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(12,12,12,8); root.setSpacing(8)

        # ── 툴바 1행: 파일/설정 액션 + 문장/그룹 설정 ─────────────────────────
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        primary_btn_qss = (
            "QPushButton {"
            f" background:{_ACCENT}; color:#FFFFFF; border:none; border-radius:7px;"
            f" padding:7px 16px; {FF_KR}; font-size:13px; font-weight:700;"
            "}"
            "QPushButton:hover { background:#1D4ED8; }"
            "QPushButton:pressed { background:#1E40AF; }"
            "QPushButton:disabled { background:#CBD5E1; color:#F8FAFC; }"
        )
        dec_qss = (
            "QLineEdit {"
            " border:1px solid #CBD5E1; border-radius:6px;"
            f" padding:0 2px; background:white; {FF_EN}; font-size:13px;"
            "}"
        )

        self.btn_open = QPushButton("📁  xlsx 파일 열기")
        self.btn_open.setFixedHeight(36)
        self.btn_open.setStyleSheet(primary_btn_qss)
        self.btn_open.clicked.connect(self._on_open)
        top.addWidget(self.btn_open)

        btn_save_cfg = QPushButton("💾  작업 저장")
        btn_save_cfg.setFixedHeight(36)
        btn_save_cfg.setStyleSheet(primary_btn_qss)
        btn_save_cfg.clicked.connect(self._on_save_project_settings)
        top.addWidget(btn_save_cfg)

        top.addStretch()

        btn_sent = QPushButton("✏️  문장 설정")
        btn_sent.setFixedHeight(36)
        btn_sent.setStyleSheet(primary_btn_qss)
        btn_sent.clicked.connect(self._on_sent_settings)
        top.addWidget(btn_sent)

        btn_graph_defaults = QPushButton("📊  그래프 세부 설정")
        btn_graph_defaults.setFixedHeight(36)
        btn_graph_defaults.setStyleSheet(primary_btn_qss)
        btn_graph_defaults.clicked.connect(self._on_graph_default_settings)
        top.addWidget(btn_graph_defaults)

        btn_group = QPushButton("🧩  그룹 설정")
        btn_group.setFixedHeight(36)
        btn_group.setStyleSheet(primary_btn_qss)
        btn_group.clicked.connect(self._on_group_settings)
        top.addWidget(btn_group)

        lbl_dec = QLabel("소수점")
        lbl_dec.setStyleSheet(f"{FF_KR};font-size:12px;color:{_SUB};background:transparent;")
        top.addWidget(lbl_dec)

        self.edit_dec = QLineEdit(str(SETTINGS.decimal))
        self.edit_dec.setFixedWidth(36)
        self.edit_dec.setFixedHeight(36)
        self.edit_dec.setAlignment(Qt.AlignCenter)
        self.edit_dec.setStyleSheet(dec_qss)
        self.edit_dec.textEdited.connect(self._on_decimal_changed)
        top.addWidget(self.edit_dec)

        root.addLayout(top)
        self.lbl_path = QLabel("파일을 선택하거나 허브에서 xlsx를 먼저 선택하세요.")
        self.lbl_path.setStyleSheet(f"{FF_EN};font-size:10px;color:{_PATH};")
        root.addWidget(self.lbl_path)

        # 메인 탭
        self.tabs = QTabWidget()
        ph = QWidget()
        pl = QVBoxLayout(ph)
        hint = QLabel("xlsx 파일을 열면 분류군별 탭이 표시됩니다.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"{FF_KR};font-size:13px;color:{_PATH};")
        pl.addWidget(hint)
        self.tabs.addTab(ph, "안내")
        root.addWidget(self.tabs, stretch=1)

        self.loading_widget = QWidget()
        lw = QVBoxLayout(self.loading_widget)
        self.lbl_loading = QLabel("⏳ 엑셀 파일을 분석 중입니다... 0%")
        self.lbl_loading.setAlignment(Qt.AlignCenter)
        self.lbl_loading.setStyleSheet(f"{FF_KR}; font-size: 15px; font-weight: bold; color: {_TXT};")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setFixedWidth(300)
        self.progress_bar.setStyleSheet(f"QProgressBar {{ border: none; background-color: {_BORDER}; border-radius: 3px; }} QProgressBar::chunk {{ background-color: {_ACCENT}; border-radius: 3px; }}")
        lw.addStretch()
        lw.addWidget(self.lbl_loading, 0, Qt.AlignCenter)
        lw.addSpacing(20)
        lw.addWidget(self.progress_bar, 0, Qt.AlignCenter)
        lw.addStretch()
        self.loading_widget.hide()
        root.addWidget(self.loading_widget, stretch=1)

        self.statusBar().setStyleSheet(f"{FF_EN};font-size:10px;color:{_SUB};")
        self.statusBar().showMessage("준비")

    def _on_decimal_changed(self, text):
        try:
            val = int(text)
        except ValueError:
            return
        if not (0 <= val <= 4):
            return
        if SETTINGS.decimal == val:
            return
        SETTINGS.decimal = val
        # 전체 UI 재빌드 없이 시그널만 emit → 탭 상태 유지
        self.sig_chart_settings.emit()
        self.sig_sent_settings.emit()

    def _on_sent_settings(self):
        from ui_shared import SentenceSettingsDialog
        dlg = SentenceSettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.sig_sent_settings.emit()

    def _available_group_items(self) -> list[dict]:
        parsed = getattr(self, "_last_parsed", {}) or {}
        keys = []
        seen = set()

        def _add(key):
            key = str(key or "").strip()
            if not key or key in seen:
                return
            if ("합계" in key) or ("종합" in key):
                return
            if key in {"sci", "kor", "remark", "family", "order", "_total", "_ra", "qi_tesb", "qi_aesb"}:
                return
            if not (key.startswith("현지_") or key.startswith("문헌_")):
                return
            seen.add(key)
            keys.append(key)

        for obj in parsed.values():
            meta = getattr(obj, "meta", None)
            if not meta:
                continue
            for rn in getattr(meta, "round_names", []) or []:
                _add(rn)
            for k in getattr(meta, "field_cols", {}) or {}:
                _add(k)

        items = []
        for key in keys:
            sec, sec_label, detail, label = _parse_round_key_label(key)
            items.append({"key": key, "section": sec, "section_label": sec_label, "detail": detail, "label": label})
        return items

    def get_active_groups(self, round_names) -> list[tuple[str, list[str]]]:
        ordered = list(dict.fromkeys(round_names or []))
        available = set(ordered)
        out = []
        used = set()
        for g in self._groups:
            survey = g.get("survey") or _infer_group_survey(g.get("rounds", []))
            valid = [rn for rn in g.get("rounds", []) if rn in available and (not survey or str(rn).startswith(f"{survey}_"))]
            if valid:
                out.append((g.get("name", ""), valid))
                used.update(valid)
        if out:
            for rn in ordered:
                s = str(rn or "")
                if rn in used or "합계" in s or "종합" in s:
                    continue
                _sec, _sec_label, detail, _label = _parse_round_key_label(s)
                out.append((detail, [rn]))
        return out

    def _on_group_settings(self):
        dlg = GroupSettingsDialog(self._groups, self._available_group_items(), self)
        if dlg.exec() == QDialog.Accepted:
            self._groups = dlg.groups()
            if hasattr(self, "_last_parsed") and hasattr(self, "_last_stats"):
                cur_idx = self.tabs.currentIndex()
                self._group_reapply_loading = True
                self._progress_val = 0.0
                self.tabs.hide()
                self.loading_widget.show()
                self.progress_bar.setStyleSheet(f"QProgressBar {{ border: none; background-color: {_BORDER}; border-radius: 3px; }} QProgressBar::chunk {{ background-color: {_ACCENT}; border-radius: 3px; }}")
                self.progress_bar.setValue(0)
                self.lbl_loading.setText("⏳ 그룹 설정 재적용 중... 0%")
                QApplication.processEvents()
                try:
                    self._show_results(self._last_parsed, self._last_stats, show_loading=True)
                    if 0 <= cur_idx < self.tabs.count():
                        self.tabs.setCurrentIndex(cur_idx)
                finally:
                    self._group_reapply_loading = False

    def _on_color_settings(self):
        from ui_shared import ChartColorDialog
        dlg = ChartColorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.sig_chart_settings.emit()

    def _program_defaults_payload(self) -> dict:
        """QSettings에 저장할 이 컴퓨터의 프로그램 기본값 묶음을 만든다."""
        return {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "settings": SETTINGS.to_dict(),
            "graph_defaults": dict(getattr(self, "_program_graph_defaults", {}) or {}),
        }

    def _load_program_defaults(self, reset_first=False) -> bool:
        """프로그램 기본값을 QSettings에서 읽어 SETTINGS와 그래프 기본값에 반영한다."""
        if reset_first:
            from config import AppSettings
            SETTINGS.from_dict(AppSettings().to_dict())

        raw = self._program_settings.value(self._PROGRAM_DEFAULTS_KEY, "", str) if hasattr(self, "_program_settings") else ""
        if not raw:
            self._program_graph_defaults = {}
            return False
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("invalid defaults payload")
            SETTINGS.from_dict(data.get("settings", {}))
            graph_defaults = data.get("graph_defaults", {})
            self._program_graph_defaults = graph_defaults if isinstance(graph_defaults, dict) else {}
            return True
        except Exception:
            self._program_graph_defaults = {}
            return False

    def _save_program_defaults_payload(self):
        """현재 문장/그래프 기본값을 QSettings에 저장한다."""
        payload = self._program_defaults_payload()
        self._program_settings.setValue(
            self._PROGRAM_DEFAULTS_KEY,
            json.dumps(payload, ensure_ascii=False),
        )
        self._program_settings.sync()
        return payload

    def _save_sentence_program_defaults(self):
        """문장 설정 다이얼로그에서 호출되는 문장 기본값 저장 진입점."""
        try:
            self._save_program_defaults_payload()
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"문장 기본값 저장 중 오류가 발생했습니다.\n{e}")
            return False
        self.statusBar().showMessage("문장 기본값을 저장했습니다.", 5000)
        return True

    def _graph_kind_for(self, group_title: str, canvas) -> tuple[str, str]:
        """그래프 제목과 설정 모드로 프로그램 기본값 저장 단위를 판별한다."""
        title = str(group_title or "").strip()
        mode = str(getattr(canvas, "_setting_mode", "") or "").strip()
        compact = title.replace(" ", "")
        if mode == "pie" and "생활형" in compact:
            return "pie_life", "생활형 파이"
        if mode == "pie":
            return "pie_order", "목별 구성 파이"
        if mode in ("bird_combo", "dominance") or "우점" in compact:
            return "bar_dominance", "우점도 그래프"
        if mode == "diversity" or "다양" in compact:
            return "bar_diversity", "다양도 그래프"
        if "생활형" in compact:
            return "plant_life", "식물 생활형 그래프"
        if "귀화" in compact:
            return "plant_naturalized", "귀화율 그래프"
        return f"graph_{mode or compact}", title or "그래프"

    def _graph_default_from_canvas(self, canvas) -> dict:
        """현재 캔버스에서 프로그램 기본값으로 저장 가능한 그래프 설정만 추린다."""
        cfg = {}
        for k, v in dict(getattr(canvas, "_cfg", {}) or {}).items():
            key_s = str(k).lower()
            # 범례/라벨 드래그 위치처럼 데이터나 작업별 위치성 값은 기본값에서 제외한다.
            if "anchor" in key_s:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                cfg[k] = v
            elif isinstance(v, (list, tuple)):
                cfg[k] = list(v)
        item = {"cfg": cfg}
        if hasattr(canvas, "_radius"):
            try:
                item["radius"] = float(getattr(canvas, "_radius"))
            except Exception:
                pass
        return item

    def _save_current_graph_default(self, canvas, group_title: str) -> bool:
        """Save one canvas' current graph settings into the program graph defaults."""
        if canvas is None or not hasattr(canvas, "_cfg"):
            return False
        kind, label = self._graph_kind_for(group_title, canvas)
        defaults = dict(getattr(self, "_program_graph_defaults", {}) or {})
        defaults[kind] = self._graph_default_from_canvas(canvas)
        self._program_graph_defaults = defaults
        try:
            self._save_program_defaults_payload()
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"그래프 기본값 저장 중 오류가 발생했습니다.\n{e}")
            return False
        self.statusBar().showMessage(f"{label} 기본값을 저장했습니다.", 5000)
        return True

    def _collect_graph_default_kinds(self) -> dict:
        """현재 생성된 그래프를 훑어 기본값 설정 창에 보여줄 그래프 종류를 수집한다."""
        out = {}
        for i in range(self.tabs.count()):
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for canvas in root.findChildren(QWidget):
                if not hasattr(canvas, "_cfg"):
                    continue
                grp = self._parent_group_for_table(canvas)
                if grp is None:
                    continue
                kind, label = self._graph_kind_for(grp.title(), canvas)
                if kind not in out:
                    out[kind] = {
                        "label": label,
                        "kind": kind,
                        "default": self._graph_default_from_canvas(canvas),
                        "source_canvas": canvas,
                    }
        for kind, saved in (getattr(self, "_program_graph_defaults", {}) or {}).items():
            if kind in out and isinstance(saved, dict):
                cleaned = dict(saved)
                cleaned.pop("frame_size", None)
                out[kind]["default"].update(cleaned)
        return out

    def _apply_graph_default_to_canvas(self, canvas, default: dict):
        """저장된 그래프 종류별 기본값을 캔버스 cfg/radius/frame에 주입한다."""
        if not isinstance(default, dict):
            return
        cfg = default.get("cfg", {})
        if isinstance(cfg, dict):
            canvas._cfg.update(cfg)
        if "radius" in default and hasattr(canvas, "_radius"):
            try:
                canvas._radius = float(default.get("radius"))
            except Exception:
                pass
        size = _auto_pie_frame_size(getattr(canvas, "_radius", SETTINGS.pie_radius), getattr(canvas, "_cfg", {})) if hasattr(canvas, "_radius") else None
        if isinstance(size, list) and len(size) == 2:
            try:
                w = max(1, int(size[0]))
                h = max(1, int(size[1]))
            except Exception:
                return
            canvas._cfg["initial_graph_width"] = w
            canvas._cfg["initial_graph_height"] = h
            frame = getattr(canvas, "_frame", None)
            if frame is not None:
                frame.setFixedSize(w, h)
                sld_w = getattr(frame, "_sld_w", None)
                sld_h = getattr(frame, "_sld_h", None)
                if sld_w is not None: sld_w.setValue(w)
                if sld_h is not None: sld_h.setValue(h)
                sc = getattr(canvas, "_scroll_area", None)
                if sc is not None:
                    QTimer.singleShot(0, lambda sc=sc: (
                        sc.horizontalScrollBar().setValue((sc.horizontalScrollBar().maximum() + sc.horizontalScrollBar().minimum()) // 2),
                        sc.verticalScrollBar().setValue((sc.verticalScrollBar().maximum() + sc.verticalScrollBar().minimum()) // 2),
                    ))
        self._sync_canvas_settings_panel(canvas)

    def _sync_canvas_settings_panel(self, canvas):
        cb = getattr(canvas, "_sync_settings_panel", None)
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def apply_graph_default_before_draw(self, canvas, kind: str):
        """각 탭에서 그래프를 처음 그리기 전에 호출하는 기본값 적용 훅."""
        default = (getattr(self, "_program_graph_defaults", {}) or {}).get(kind)
        if default:
            self._apply_graph_default_to_canvas(canvas, default)

    def _apply_program_graph_defaults(self):
        """이미 열린 화면의 그래프들에 프로그램 기본값을 다시 적용하고 redraw한다."""
        defaults = getattr(self, "_program_graph_defaults", {}) or {}
        if not defaults:
            return
        for i in range(self.tabs.count()):
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for canvas in root.findChildren(QWidget):
                if not hasattr(canvas, "_cfg"):
                    continue
                grp = self._parent_group_for_table(canvas)
                if grp is None:
                    continue
                kind, _ = self._graph_kind_for(grp.title(), canvas)
                if kind in defaults:
                    self._apply_graph_default_to_canvas(canvas, defaults.get(kind))
                    cb = getattr(canvas, "_refresh_cb", None)
                    if callable(cb):
                        cb()
                    elif hasattr(canvas, "draw"):
                        canvas.draw()

    def _apply_open_color_defaults(self):
        color_keys = ["color_mode", "bar_color", "line_color", "div_color_1", "div_color_2", "div_color_3"]
        for i in range(self.tabs.count()):
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for canvas in root.findChildren(QWidget):
                if not hasattr(canvas, "_cfg"):
                    continue
                for key in color_keys:
                    if hasattr(SETTINGS, key):
                        canvas._cfg[key] = getattr(SETTINGS, key)
                cb = getattr(canvas, "_refresh_cb", None)
                if callable(cb):
                    cb()
                elif hasattr(canvas, "draw"):
                    canvas.draw()

    def _on_graph_default_settings(self):
        """그래프 기본값 설정 다이얼로그를 열고 저장된 기본값을 즉시 반영한다."""
        kinds = self._collect_graph_default_kinds()
        if not kinds:
            QMessageBox.information(self, "그래프 기본값 설정", "현재 생성된 그래프가 없습니다.")
            return
        dlg = GraphDefaultSettingsDialog(kinds, self)
        if dlg.exec() == QDialog.Accepted:
            self._program_graph_defaults = dlg.defaults()
            try:
                self._save_program_defaults_payload()
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"그래프 기본값 저장 중 오류가 발생했습니다.\n{e}")
                return
            self._apply_open_color_defaults()
            self._apply_program_graph_defaults()
            self.statusBar().showMessage("그래프 기본값을 저장했습니다.", 5000)

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "종목록 xlsx 선택", self._cur_path or "",
            "Excel Files (*.xlsx *.xlsm)"
        )
        if path: self._load(path)

    def _settings_json_path(self) -> str:
        if not self._cur_path:
            return ""
        base = os.path.splitext(os.path.basename(self._cur_path))[0]
        return os.path.join(os.path.dirname(self._cur_path), f"{base}.taxa_settings.json")

    def _tab_root_widget(self, tab_widget):
        if isinstance(tab_widget, QScrollArea):
            return tab_widget.widget()
        return tab_widget

    def _first_table_in_group(self, grp: QGroupBox):
        tables = grp.findChildren(QTableWidget)
        return tables[0] if tables else None

    def _parent_group_for_table(self, tbl: QTableWidget):
        p = tbl.parent()
        while p is not None:
            if isinstance(p, QGroupBox):
                return p
            p = p.parent()
        return None

    def _table_index_in_group(self, grp: QGroupBox, tbl: QTableWidget) -> int:
        if grp is None:
            return 0
        tables = grp.findChildren(QTableWidget)
        for idx, cur in enumerate(tables):
            if cur is tbl:
                return idx
        return 0

    def _table_at_index_in_group(self, grp: QGroupBox, index: int):
        tables = grp.findChildren(QTableWidget)
        if not tables:
            return None
        if 0 <= index < len(tables):
            return tables[index]
        return tables[0]

    def _canvases_in_group(self, grp: QGroupBox):
        if grp is None:
            return []
        return [w for w in grp.findChildren(QWidget) if hasattr(w, "_cfg")]

    def _canvas_index_in_group(self, grp: QGroupBox, canvas) -> int:
        for idx, cur in enumerate(self._canvases_in_group(grp)):
            if cur is canvas:
                return idx
        return 0

    def _canvas_at_index_in_group(self, grp: QGroupBox, index: int):
        canvases = self._canvases_in_group(grp)
        if not canvases:
            return None
        if 0 <= index < len(canvases):
            return canvases[index]
        return canvases[0]

    def _group_title_index(self, root, grp: QGroupBox) -> int:
        if root is None or grp is None:
            return 0
        idx = 0
        for cur in root.findChildren(QGroupBox):
            if cur.title() != grp.title():
                continue
            if cur is grp:
                return idx
            idx += 1
        return 0

    def _collect_ratio_state(self) -> list:
        out = []
        seen = set()
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for tbl in root.findChildren(QTableWidget):
                grp = self._parent_group_for_table(tbl)
                if grp is None:
                    continue
                normalized = bool(getattr(grp, "is_normalized", False) or getattr(tbl, "_is_normalized", False))
                if not normalized:
                    continue
                pct_col = getattr(grp, "_pct_col", None)
                if pct_col is None:
                    pct_col = getattr(tbl, "_pct_col", None)
                pct_row = getattr(grp, "_pct_row", None)
                if pct_row is None:
                    pct_row = getattr(tbl, "_pct_row", None)
                if pct_col is None and pct_row is None:
                    continue
                cnt_col = getattr(grp, "_cnt_col", None)
                if cnt_col is None:
                    cnt_col = getattr(tbl, "_cnt_col", None)

                item = {
                    "tab": tab_name,
                    "group_title": grp.title(),
                    "group_index": self._group_title_index(root, grp),
                    "table_index": self._table_index_in_group(grp, tbl),
                }
                if pct_col is not None:
                    rows = []
                    n_data = max(tbl.rowCount() - 1, 0)
                    for r in range(n_data):
                        k0 = (tbl.item(r, 0).text().strip() if tbl.item(r, 0) else "")
                        k1 = (tbl.item(r, 1).text().strip() if tbl.item(r, 1) else "")
                        key = f"{k0}|{k1}"
                        pit = tbl.item(r, int(pct_col))
                        ptxt = (pit.text().strip() if pit else "0")
                        try:
                            pval = float(ptxt.replace("%", "").replace(",", ""))
                        except Exception:
                            pval = 0.0
                        rows.append({"index": r, "key": key, "pct": pval})
                    item.update({
                        "axis": "col",
                        "pct_col": int(pct_col),
                        "cnt_col": None if cnt_col is None else int(cnt_col),
                        "rows": rows,
                    })
                else:
                    cnt_row = getattr(grp, "_cnt_row", None)
                    if cnt_row is None:
                        cnt_row = getattr(tbl, "_cnt_row", None)
                    start_col = int(getattr(tbl, "_pct_start_col", 1))
                    end_col_offset = int(getattr(tbl, "_pct_end_col_offset", 1))
                    n_data = max(tbl.columnCount() - start_col - end_col_offset, 0)
                    cols = []
                    for c in range(n_data):
                        col = start_col + c
                        hit = tbl.horizontalHeaderItem(col)
                        key = (hit.text().strip() if hit else str(col))
                        pit = tbl.item(int(pct_row), col)
                        ptxt = (pit.text().strip() if pit else "0")
                        try:
                            pval = float(ptxt.replace("%", "").replace(",", ""))
                        except Exception:
                            pval = 0.0
                        cols.append({"index": col, "key": key, "pct": pval})
                    item.update({
                        "axis": "row",
                        "pct_row": int(pct_row),
                        "cnt_row": None if cnt_row is None else int(cnt_row),
                        "start_col": start_col,
                        "end_col_offset": end_col_offset,
                        "cols": cols,
                    })
                sig = (
                    item.get("tab"), item.get("group_title"), item.get("group_index"),
                    item.get("table_index"), item.get("axis"), item.get("pct_col"), item.get("pct_row"),
                )
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(item)
        return out

    def _collect_graph_state(self) -> list:
        out = []
        seen = set()
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for canvas in root.findChildren(QWidget):
                if not hasattr(canvas, "_cfg"):
                    continue
                grp = self._parent_group_for_table(canvas)
                if grp is None:
                    continue
                cfg = {}
                for k, v in dict(getattr(canvas, "_cfg", {}) or {}).items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        cfg[k] = v
                    elif isinstance(v, (list, tuple)):
                        cfg[k] = list(v)
                item = {
                    "tab": tab_name,
                    "group_title": grp.title(),
                    "group_index": self._group_title_index(root, grp),
                    "canvas_index": self._canvas_index_in_group(grp, canvas),
                    "setting_mode": getattr(canvas, "_setting_mode", ""),
                    "cfg": cfg,
                }
                if hasattr(canvas, "_radius"):
                    try:
                        item["radius"] = float(getattr(canvas, "_radius"))
                    except Exception:
                        pass
                frame = getattr(canvas, "_frame", None)
                if frame is not None:
                    item["frame_size"] = [int(frame.width()), int(frame.height())]
                positions = getattr(canvas, "_positions", None)
                if isinstance(positions, dict):
                    item["positions"] = {
                        str(k): [float(v[0]), float(v[1])]
                        for k, v in positions.items()
                        if isinstance(v, (list, tuple)) and len(v) == 2
                    }
                sig = (item["tab"], item["group_title"], item["group_index"], item["canvas_index"])
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(item)
        return out

    def _collect_sentence_snapshots(self) -> list:
        snaps = []
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            root = self._tab_root_widget(self.tabs.widget(i))
            if root is None:
                continue
            for grp in root.findChildren(QGroupBox):
                if "문장" not in grp.title():
                    continue
                edits = grp.findChildren(QPlainTextEdit)
                for ei, ed in enumerate(edits):
                    txt = (ed.toPlainText() or "").strip()
                    if not txt:
                        continue
                    snaps.append({
                        "tab": tab_name,
                        "group_title": grp.title(),
                        "index": ei,
                        "text": txt,
                    })
        return snaps

    def _save_project_settings(self, notify=True):
        path = self._settings_json_path()
        if not path:
            if notify:
                QMessageBox.warning(self, "저장 실패", "먼저 엑셀 파일을 열어주세요.")
            return False

        payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "excel_file": os.path.basename(self._cur_path),
            "settings": SETTINGS.to_dict(),
            "groups": self._groups,
            "graph_settings": self._collect_graph_state(),
            "ratio_corrections": self._collect_ratio_state(),
            "sentence_snapshots": self._collect_sentence_snapshots(),
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            if notify:
                QMessageBox.critical(self, "저장 실패", f"설정 저장 중 오류가 발생했습니다.\n{e}")
            return False

        if notify:
            self.statusBar().showMessage(f"설정 저장 완료: {path}", 5000)
        return True

    def _load_project_settings(self, notify=True):
        path = self._settings_json_path()
        if not path:
            if notify:
                QMessageBox.warning(self, "불러오기 실패", "먼저 엑셀 파일을 열어주세요.")
            return False
        if not os.path.exists(path):
            if notify:
                QMessageBox.information(self, "불러오기", "저장된 설정 파일이 없습니다.")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            if notify:
                QMessageBox.critical(self, "불러오기 실패", f"설정 파일을 읽을 수 없습니다.\n{e}")
            return False

        try:
            SETTINGS.from_dict(data.get("settings", {}))
            self.edit_dec.setText(str(getattr(SETTINGS, "decimal", 1)))
            groups = data.get("groups", [])
            self._groups = groups if isinstance(groups, list) else []
            graph_state = data.get("graph_settings", [])
            self._pending_graph_state = graph_state if isinstance(graph_state, list) else []
            ratio_state = data.get("ratio_corrections", [])
            self._pending_ratio_state = ratio_state if isinstance(ratio_state, list) else []
            snaps = data.get("sentence_snapshots", [])
            self._loaded_sentence_snapshots = snaps if isinstance(snaps, list) else []
        except Exception as e:
            if notify:
                QMessageBox.critical(self, "불러오기 실패", f"설정 적용 중 오류가 발생했습니다.\n{e}")
            return False

        if notify:
            self.statusBar().showMessage(f"설정 불러오기 완료: {path}", 5000)
        return True

    def _apply_pending_graph_state(self):
        if not self._pending_graph_state:
            return

        def _apply_to_canvas(canvas, item):
            cfg = item.get("cfg", {})
            if isinstance(cfg, dict):
                canvas._cfg.update(cfg)
            if "radius" in item and hasattr(canvas, "_radius"):
                canvas._radius = float(item.get("radius"))
            positions = item.get("positions")
            if isinstance(positions, dict) and hasattr(canvas, "_positions"):
                canvas._positions = {
                    str(k): (float(v[0]), float(v[1]))
                    for k, v in positions.items()
                    if isinstance(v, (list, tuple)) and len(v) == 2
                }
            frame = getattr(canvas, "_frame", None)
            size = item.get("frame_size")
            if frame is not None and isinstance(size, list) and len(size) == 2:
                frame.setFixedSize(max(1, int(size[0])), max(1, int(size[1])))
            self._sync_canvas_settings_panel(canvas)
            cb = getattr(canvas, "_refresh_cb", None)
            if callable(cb):
                cb()
            elif hasattr(canvas, "draw"):
                canvas.draw()

        applied = 0
        for item in list(self._pending_graph_state):
            tab_name = item.get("tab", "")
            grp_title = item.get("group_title", "")
            has_group_index = "group_index" in item
            group_index = int(item.get("group_index", 0) or 0)
            canvas_index = int(item.get("canvas_index", 0) or 0)

            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) != tab_name:
                    continue
                root = self._tab_root_widget(self.tabs.widget(i))
                if root is None:
                    break
                title_seen = 0
                for grp in root.findChildren(QGroupBox):
                    if grp.title() != grp_title:
                        continue
                    if has_group_index and title_seen != group_index:
                        title_seen += 1
                        continue
                    title_seen += 1
                    canvas = self._canvas_at_index_in_group(grp, canvas_index)
                    if canvas is None:
                        continue
                    try:
                        _apply_to_canvas(canvas, item)
                        applied += 1
                    except Exception:
                        pass
                    if has_group_index:
                        break
                break
        self._pending_graph_state = []
        if applied:
            self.statusBar().showMessage(f"그래프 설정 {applied}개 복원", 4000)

    def _apply_pending_ratio_state(self):
        if not self._pending_ratio_state:
            return

        def _fmt_pct_text_like_cell(v, sample_text):
            if "%" in str(sample_text):
                return f"{float(v):.{SETTINGS.decimal}f}%"
            return f"{float(v):.{SETTINGS.decimal}f}"

        applied = 0
        for item in list(self._pending_ratio_state):
            tab_name = item.get("tab", "")
            grp_title = item.get("group_title", "")
            has_group_index = "group_index" in item
            group_index = int(item.get("group_index", 0) or 0)
            axis = item.get("axis", "col")
            table_index = int(item.get("table_index", 0) or 0)
            saved_rows = item.get("rows") if isinstance(item.get("rows"), list) else []
            saved_cols = item.get("cols") if isinstance(item.get("cols"), list) else []

            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) != tab_name:
                    continue
                root = self._tab_root_widget(self.tabs.widget(i))
                if root is None:
                    break
                title_seen = 0
                for grp in root.findChildren(QGroupBox):
                    if grp.title() != grp_title:
                        continue
                    if has_group_index and title_seen != group_index:
                        title_seen += 1
                        continue
                    title_seen += 1
                    tbl = self._table_at_index_in_group(grp, table_index)
                    if tbl is None:
                        continue
                    try:
                        if axis == "row":
                            pct_row = int(item.get("pct_row"))
                            cnt_row_raw = item.get("cnt_row")
                            cnt_row = None if cnt_row_raw is None else int(cnt_row_raw)
                            start_col = int(item.get("start_col", 1) or 1)
                            end_col_offset = int(item.get("end_col_offset", 1) or 1)
                            if saved_cols:
                                sample = tbl.item(pct_row, start_col).text() if tbl.columnCount() > start_col and tbl.item(pct_row, start_col) else ""
                                col_map = {str(c.get("key", "")): float(c.get("pct", 0.0)) for c in saved_cols}
                                idx_map = {int(c.get("index", -1)): float(c.get("pct", 0.0)) for c in saved_cols}
                                n_data = max(tbl.columnCount() - start_col - end_col_offset, 0)
                                for cc in range(n_data):
                                    col = start_col + cc
                                    hit = tbl.horizontalHeaderItem(col)
                                    key = (hit.text().strip() if hit else str(col))
                                    if key in col_map:
                                        pval = col_map[key]
                                    elif col in idx_map:
                                        pval = idx_map[col]
                                    else:
                                        continue
                                    cell = tbl.item(pct_row, col)
                                    if cell is None:
                                        cell = QTableWidgetItem("")
                                        tbl.setItem(pct_row, col, cell)
                                    cell.setText(_fmt_pct_text_like_cell(pval, sample))
                                total_col = start_col + n_data
                                if tbl.columnCount() > total_col:
                                    total_v = round(sum(float(c.get("pct", 0.0)) for c in saved_cols), SETTINGS.decimal)
                                    total_cell = tbl.item(pct_row, total_col)
                                    if total_cell is None:
                                        total_cell = QTableWidgetItem("")
                                        tbl.setItem(pct_row, total_col, total_cell)
                                    total_cell.setText(_fmt_pct_text_like_cell(total_v, sample))
                            else:
                                normalize_tbl_pct_row(tbl, pct_row, cnt_row=cnt_row, start_col=start_col, end_col_offset=end_col_offset)
                            tbl._pct_row = pct_row
                            tbl._cnt_row = cnt_row
                            tbl._pct_start_col = start_col
                            tbl._pct_end_col_offset = end_col_offset
                        else:
                            pct_col = int(item.get("pct_col"))
                            cnt_col_raw = item.get("cnt_col")
                            cnt_col = None if cnt_col_raw is None else int(cnt_col_raw)
                            if saved_rows:
                                sample = tbl.item(0, pct_col).text() if tbl.rowCount() > 0 and tbl.item(0, pct_col) else ""
                                row_map = {str(r.get("key", "")): float(r.get("pct", 0.0)) for r in saved_rows}
                                idx_map = {int(r.get("index", -1)): float(r.get("pct", 0.0)) for r in saved_rows}
                                n_data = max(tbl.rowCount() - 1, 0)
                                for rr in range(n_data):
                                    k0 = (tbl.item(rr, 0).text().strip() if tbl.item(rr, 0) else "")
                                    k1 = (tbl.item(rr, 1).text().strip() if tbl.item(rr, 1) else "")
                                    key = f"{k0}|{k1}"
                                    if key in row_map:
                                        pval = row_map[key]
                                    elif rr in idx_map:
                                        pval = idx_map[rr]
                                    else:
                                        continue
                                    cell = tbl.item(rr, pct_col)
                                    if cell is None:
                                        cell = QTableWidgetItem("")
                                        tbl.setItem(rr, pct_col, cell)
                                    cell.setText(_fmt_pct_text_like_cell(pval, sample))

                                if tbl.rowCount() > 0:
                                    total_v = round(sum(float(r.get("pct", 0.0)) for r in saved_rows), SETTINGS.decimal)
                                    tr = tbl.rowCount() - 1
                                    total_cell = tbl.item(tr, pct_col)
                                    if total_cell is None:
                                        total_cell = QTableWidgetItem("")
                                        tbl.setItem(tr, pct_col, total_cell)
                                    total_cell.setText(_fmt_pct_text_like_cell(total_v, sample))
                            else:
                                normalize_tbl_pct_col(tbl, pct_col, cnt_col=cnt_col)
                            grp._pct_col = pct_col
                            grp._cnt_col = cnt_col
                            tbl._pct_col = pct_col
                            tbl._cnt_col = cnt_col
                        grp.is_normalized = True
                        tbl._is_normalized = True
                        on_norm = getattr(grp, "on_normalize", None)
                        if callable(on_norm):
                            on_norm()
                        on_norm = getattr(tbl, "on_normalize", None)
                        if callable(on_norm):
                            on_norm()
                        applied += 1
                    except Exception:
                        pass
                    if has_group_index:
                        break
                break
        self._pending_ratio_state = []
        if applied:
            self.statusBar().showMessage(f"비율 보정 상태 {applied}개 복원", 4000)

    def _on_save_project_settings(self):
        self._save_project_settings(notify=True)

    def _on_load_project_settings(self):
        loaded = self._load_project_settings(notify=True)
        if not loaded:
            return
        if hasattr(self, "_last_parsed") and hasattr(self, "_last_stats"):
            cur_idx = self.tabs.currentIndex()
            self._show_results(self._last_parsed, self._last_stats, show_loading=False)
            if 0 <= cur_idx < self.tabs.count():
                self.tabs.setCurrentIndex(cur_idx)
        # sig_chart_settings는 emit하지 않는다.
        # _show_results가 이미 로드된 SETTINGS로 모든 탭을 새로 생성하며,
        # emit하면 land_tab._refresh() / aqua_tab._refresh_charts()가 테이블을
        # 재생성·재계산해 _apply_pending_ratio_state가 복원한 비율 보정을 덮어쓴다.
        self.sig_sent_settings.emit()

    def _load(self, path: str):
        self._cur_path = path
        self._load_program_defaults(reset_first=True)
        self._groups = []
        self._pending_graph_state = []
        self._pending_ratio_state = []
        self._loaded_sentence_snapshots = []
        if hasattr(self, "edit_dec"):
            self.edit_dec.setText(str(getattr(SETTINGS, "decimal", 1)))
        self.lbl_path.setText(path)
        self.statusBar().showMessage("⏳ 분석 중…")
        self.btn_open.setEnabled(False)

        self.tabs.hide()
        self.loading_widget.show()

        self.progress_bar.setStyleSheet(f"QProgressBar {{ border: none; background-color: {_BORDER}; border-radius: 3px; }} QProgressBar::chunk {{ background-color: {_ACCENT}; border-radius: 3px; }}")
        self.progress_bar.setValue(0)
        self._progress_val = 0.0
        self.lbl_loading.setText("⏳ 엑셀 파일을 분석 중입니다... 0%")
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(50)

        self._worker = LoadWorker(path)
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _update_progress(self):
        if self._progress_val < 50:
            self._progress_val += (50 - self._progress_val) * 0.05
            val = int(self._progress_val)
            self.progress_bar.setValue(val)
            self.lbl_loading.setText(f"⏳ 엑셀 파일을 분석 중입니다... {val}%")

    def _on_loaded(self, parsed, stats):
        self._last_parsed = parsed
        self._last_stats = stats
        self._load_project_settings(notify=False)
        if hasattr(self, "_progress_timer"):
            self._progress_timer.stop()

        self._progress_val = 50.0
        self.progress_bar.setValue(50)
        self.lbl_loading.setText("⏳ 화면(UI) 생성 중... 50%")
        QApplication.processEvents()

        # 상태를 갱신한 직후 화면 렌더링 작업을 시작합니다.
        QTimer.singleShot(20, lambda: self._show_results(parsed, stats))

    def step_sub_progress(self, msg: str, ratio: float):
        if not hasattr(self, "_current_tab_weight"): return
        add_val = self._current_tab_weight * ratio
        self._current_tab_consumed += add_val
        self._progress_val += add_val
        if getattr(self, "_silent_loading", False): return
        val = int(min(99, self._progress_val))
        self.progress_bar.setValue(val)
        self.lbl_loading.setText(f"⏳ {msg}... {val}%")
        QApplication.processEvents()

    def _show_results(self, parsed, stats, show_loading=True):
        self.btn_open.setEnabled(True)
        cur_idx = self.tabs.currentIndex()
        while self.tabs.count(): self.tabs.removeTab(0)

        # ── 탭 순서 고정 ──────────────────────────────────────────────────────
        TAB_ORDER = [
            # 육상동물
            "포유류", "조류", "양서류·파충류", "양서파충류", "곤충류",
            # 육수
            "어류상", "저서상",
            # 식물
            "식물상", "귀화식물", "교란생물",
            "구계학적 특정식물", "멸종위기종", "습생식물", "희귀·특산식물",
            # 법정보호종 (공통 — 항상 맨 뒤)
            "법정보호종", "법정보호종목록",
        ]
        def _sort_key(item):
            n = item[0]
            try:    return TAB_ORDER.index(n)
            except: return len(TAB_ORDER)   # 목록에 없으면 맨 뒤

        ordered = sorted(stats.items(), key=_sort_key)
        total_tabs = max(len(ordered), 1)
        _ctx = {"plant_aux": {}}   # 클로저 간 공유 상태

        overview_w = _build_land_overview_tab(parsed, parent_window=self)
        if overview_w is not None:
            sc_over = QScrollArea(); sc_over.setWidgetResizable(True)
            sc_over.setFrameShape(QFrame.NoFrame); sc_over.setWidget(overview_w)
            self.tabs.addTab(sc_over, "전분류군 현황")

        aqua_overview_w = _build_aqua_overview_tab(parsed, parent_window=self)
        if aqua_overview_w is not None:
            sc_aqua_over = QScrollArea(); sc_aqua_over.setWidgetResizable(True)
            sc_aqua_over.setFrameShape(QFrame.NoFrame); sc_aqua_over.setWidget(aqua_overview_w)
            self.tabs.addTab(sc_aqua_over, "육수 전분류군 현황")

        def _finish_all():
            # ── 수환경평가 탭 (저서상 데이터가 있을 때만, 법정보호종 앞에 삽입) ──
            from parser import ParsedAquatic as _PA2
            aqua_parsed = {n: o for n, o in parsed.items() if isinstance(o, _PA2)}
            benthos_parsed = {
                n: o for n, o in aqua_parsed.items()
                if o and getattr(o, "taxon", None) == "benthos" and o.species
            }
            if benthos_parsed:
                water_w = build_water_eval_tab(benthos_parsed)
                insert_idx = self.tabs.count()
                for i in range(self.tabs.count()):
                    if "법정보호종" in self.tabs.tabText(i):
                        insert_idx = i; break
                self.tabs.insertTab(insert_idx, water_w, "💧  수환경평가")

            self._last_applied_graph = list(self._pending_graph_state)
            self._apply_pending_graph_state()
            self._last_applied_ratio = list(self._pending_ratio_state)
            self._apply_pending_ratio_state()

            if show_loading:
                self.progress_bar.setValue(100)
                done_msg = "✔ 그룹 설정 재적용 완료! 100%" if getattr(self, "_group_reapply_loading", False) else "✔ 분석 및 화면 생성 완료! 100%"
                self.lbl_loading.setText(done_msg)
                self.progress_bar.setStyleSheet(f"QProgressBar {{ border: none; background-color: {_BORDER}; border-radius: 3px; }} QProgressBar::chunk {{ background-color: {_SUCCESS}; border-radius: 3px; }}")
                QApplication.processEvents()
                total_sp = sum(s.total_species for s in stats.values() if hasattr(s, "total_species"))
                self.statusBar().showMessage(f"✔ 완료 — {len(stats)}개 시트 / 합계 {total_sp}종")
                self._finish_loading()
            else:
                if cur_idx >= 0 and cur_idx < self.tabs.count():
                    self.tabs.setCurrentIndex(cur_idx)

        def _build_tab_at(idx):
            if idx >= len(ordered):
                _finish_all()
                return

            name, stat = ordered[idx]
            self._current_tab_weight = 49.0 / total_tabs
            self._current_tab_consumed = 0.0

            if show_loading:
                val = int(self._progress_val)
                self.progress_bar.setValue(val)
                self.lbl_loading.setText(f"⏳ 화면(UI) 생성 중 ({name})... {val}%")

            sc = QScrollArea(); sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.NoFrame)

            if isinstance(stat, TaxaStats):
                taxon = stat.taxon
                icon = TAB_ICON.get(taxon, "🔬")
                p_sheet = parsed.get(name)
                prot_sh = None
                for pobj in parsed.values():
                    from parser import ParsedProtected
                    if isinstance(pobj, ParsedProtected):
                        prot_sh = pobj; break
                from parser import ParsedSheet as _PS
                land_w = build_land_tab(stat, p_sheet, prot_sh, parent_window=self) if isinstance(p_sheet, _PS) else _animal_tab(stat, p_sheet)
                sc.setWidget(land_w)
                self.tabs.addTab(sc, f"{icon}  {name}")
            elif isinstance(stat, AquaticStats):
                icon = TAB_ICON.get(stat.taxon, "🔬")
                a_sheet = parsed.get(name)
                from parser import ParsedAquatic as _PA, ParsedProtected as _PPr
                prot_sh_aq = next((o for o in parsed.values() if isinstance(o, _PPr)), None)
                aqua_w = build_aqua_tab(stat, a_sheet, prot_sheet=prot_sh_aq, parent_window=self) \
                         if isinstance(a_sheet, _PA) else _aquatic_tab(stat, a_sheet)
                sc.setWidget(aqua_w)
                self.tabs.addTab(sc, f"{icon}  {name}")
            elif isinstance(stat, PlantStats):
                p_sheet = parsed.get(name)
                if getattr(p_sheet, "taxon", None) != "plant":
                    QTimer.singleShot(0, lambda i=idx: _build_tab_at(i + 1))
                    return
                from parser import ParsedPlant as _PP
                aux_sheets = {}
                for k, v in parsed.items():
                    if "귀화" in k: aux_sheets["귀화식물"] = v
                    elif "교란" in k: aux_sheets["교란생물"] = v
                    elif "구계학" in k or "특정" in k: aux_sheets["구계학적 특정식물"] = v
                    elif "멸종" in k: aux_sheets["멸종위기종"] = v
                    elif "습생" in k: aux_sheets["습생식물"] = v
                    elif "희귀" in k and "특산" in k: aux_sheets["희귀·특산식물"] = v
                    elif "희귀" in k: aux_sheets["희귀식물"] = v
                    elif "특산" in k: aux_sheets["특산식물"] = v
                _ctx["plant_aux"] = aux_sheets
                from parser import ParsedProtected as _PPr_plant
                prot_sh_plant = next((v for v in parsed.values() if isinstance(v, _PPr_plant)), None)
                plant_w = build_plant_tab(stat, p_sheet, prot_sheet=prot_sh_plant, parent_window=self, aux_sheets=aux_sheets) \
                          if isinstance(p_sheet, _PP) else _plant_tab(stat)
                sc.setWidget(plant_w)
                self.tabs.addTab(sc, f"🌿  {name}")
                # 식생 탭은 별도 singleShot으로 분리 → 이벤트 루프 양보 후 빌드
                def _add_veg_then_next(i=idx):
                    if show_loading:
                        self.lbl_loading.setText(f"⏳ 화면(UI) 생성 중 (식생)... {int(self._progress_val)}%")
                        self.step_sub_progress("화면(UI) 생성 중 (식생)", 0.04)
                    self.tabs.addTab(make_vegetation_tab(self), "🌿  식생")
                    rem = self._current_tab_weight - self._current_tab_consumed
                    if rem > 0:
                        self._progress_val += rem
                    QTimer.singleShot(0, lambda: _build_tab_at(i + 1))
                QTimer.singleShot(0, _add_veg_then_next)
                return
            elif isinstance(stat, PlantSpecialStats):
                rem = self._current_tab_weight - self._current_tab_consumed
                if rem > 0: self._progress_val += rem
                QTimer.singleShot(0, lambda i=idx: _build_tab_at(i + 1))
                return
            elif isinstance(stat, ProtectedStats):
                prot_raw = parsed.get(name)
                aux = _ctx["plant_aux"]
                if not aux:
                    for k, v in parsed.items():
                        if "희귀" in k and "특산" in k: aux["희귀·특산식물"] = v
                        elif "희귀" in k: aux["희귀식물"] = v
                        elif "특산" in k: aux["특산식물"] = v
                sc.setWidget(_protected_tab(stat, prot_raw, parent_window=self, aux_sheets=aux))
                self.tabs.addTab(sc, f"🛡  {name}")

            rem = self._current_tab_weight - self._current_tab_consumed
            if rem > 0:
                self._progress_val += rem
            QTimer.singleShot(0, lambda i=idx: _build_tab_at(i + 1))

        QTimer.singleShot(0, lambda: _build_tab_at(0))

    def _finish_loading(self):
        self.loading_widget.hide()
        self.tabs.show()
        self.tabs.setGraphicsEffect(None)

        def _emit_and_restore():
            self.sig_chart_settings.emit()
            # sig_chart_settings가 land/aqua 탭의 refresh를 동기 호출해 테이블을
            # 재생성·재계산하므로, emit 직후 비율 보정을 다시 덮어 적용한다.
            # (_replace_tbl이 setParent(None)으로 old 위젯을 즉시 트리에서 제거하므로
            #  findChildren이 new 테이블만 반환하는 것이 보장된다)
            if getattr(self, "_last_applied_graph", None):
                self._pending_graph_state = list(self._last_applied_graph)
                self._apply_pending_graph_state()
            if getattr(self, "_last_applied_ratio", None):
                self._pending_ratio_state = list(self._last_applied_ratio)
                self._apply_pending_ratio_state()
            # 저장된 그래프 기본값을 모든 캔버스에 적용
            # (aqua/plant은 before_draw에서 이미 적용됐지만, land 탭 등은 누락되므로 여기서 일괄 보정)
            self._apply_program_graph_defaults()

        QTimer.singleShot(0, _emit_and_restore)

    def _on_error(self, msg):
        if hasattr(self, "_progress_timer"):
            self._progress_timer.stop()
        self.loading_widget.hide()
        self.tabs.show()
        self.btn_open.setEnabled(True)
        self.statusBar().showMessage("오류 발생")
        QMessageBox.critical(self, "분석 오류", msg[:800])

    def closeEvent(self, ev: QCloseEvent):
        if self.parent() is not None:
            ev.ignore(); self.hide()
        else:
            super().closeEvent(ev)


# ── 단독 실행 ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    install_global_no_focus_rect_style(app)
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    w = TaxaWindow(excel_path=path)
    w.show()
    sys.exit(app.exec())
