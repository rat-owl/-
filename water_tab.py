# water_tab.py — 수환경평가 탭 (저서상 Qi(AESB) / Qi(TESB) 기반)
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from collections import OrderedDict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QPushButton, QFrame, QApplication, QPlainTextEdit, QGroupBox,
    QStyledItemDelegate,
)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QColor, QPen

from config import (
    _BG, _CARD, _BORDER, _TXT, _SUB,
    _ACCENT, _ACCENT_L,
    _FONT_KR, FF_KR, FF_EN, BD, BD1,
)
from ui_shared import CopyableTableWidget, make_copy_button

_QSS = f"""
QWidget   {{ background:{_BG}; {FF_KR}; font-size:13px; color:{_TXT}; }}
QTableWidget {{
    {BD}; border-radius:8px; background:{_CARD};
    gridline-color:{_BORDER}; {FF_KR}; font-size:12px;
}}
QTableWidget::item          {{ padding:4px 10px; }}
QTableWidget::item:selected {{
    background: {_ACCENT_L};
    color: {_ACCENT};
}}
QHeaderView::section {{
    background:{_BG}; {BD1};
    padding:5px 8px; {FF_KR}; font-size:11px; font-weight:700; color:{_SUB};
}}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical         {{ background:{_BG}; width:6px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#B0B8C8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""


# ── 표 31: TESB/AESB 구간별 물환경 평가 기준 ──────────────────────────────────
_CLASS_INFO = [
    # (등급, TESB_최소, AESB_최소, 생물다양성, 환경상태, 관리수역, 배경색)
    ("A", 120, 3.5, "매우높음", "매우좋음", "우선보전수역", "#EAFDF3"),
    ("B",  70, 3.0, "높음",    "좋음",    "보전수역",    "#F5FFE7"),
    ("C",  30, 2.5, "보통",    "보통",    "예찰",        "#FBF9CA"),
    ("D",  15, 2.0, "낮음",    "나쁨",    "개선수역",    "#FFE5C9"),
    ("E",   0, 0.0, "매우낮음","매우나쁨","우선개선수역", "#FFBBBB"),
]

def _classify(score: float, criteria: str):
    """score 와 criteria('TESB' or 'AESB')로 등급 정보 반환."""
    idx = 1 if criteria == "TESB" else 2
    for row in _CLASS_INFO:
        if score >= row[idx]:
            return row
    return _CLASS_INFO[-1]


_GRADE_ORDER = {r[0]: i for i, r in enumerate(_CLASS_INFO)}  # A=0, E=4


def _adopted_cls(tesb: float, aesb: float):
    """TESB·AESB 등급을 비교해 더 낮은(나쁜) 등급 정보를 반환."""
    cls_t = _classify(tesb, "TESB")
    cls_a = _classify(aesb, "AESB")
    return cls_t if _GRADE_ORDER[cls_t[0]] >= _GRADE_ORDER[cls_a[0]] else cls_a


def _item(txt, align=Qt.AlignCenter):
    it = QTableWidgetItem(str(txt))
    it.setTextAlignment(align)
    return it


_SKIP_STATIONS = {"합계", "종합", ""}

def _extract_rounds_stations(round_names: list) -> OrderedDict:
    """
    round_names 에서 {차시명: [지점명, ...]} OrderedDict 추출.
    키 형식: "현지_1차_Wa.1" (3단계) 또는 "현지_Wa.1" (2단계 폴백)
    '합계'·'종합' 지점은 aqua_tab._detail_rns와 동일하게 제외.
    """
    result = OrderedDict()
    for rname in round_names:
        parts = rname.split("_", 2)
        if not parts or parts[0] != "현지":
            continue
        if len(parts) == 3:
            _, round_name, station = parts
        elif len(parts) == 2:
            # 2단계 키: "현지_Wa.1" → round_name="1차", station="Wa.1"
            round_name, station = "1차", parts[1]
        else:
            continue
        last = station if station else round_name
        if last in _SKIP_STATIONS:
            continue
        result.setdefault(round_name, [])
        if station not in result[round_name]:
            result[round_name].append(station)
    return result


def _is_present(val) -> bool:
    """개체수 숫자든 기호(+, ○ 등)든 비어있지 않으면 출현 처리."""
    s = str(val).strip() if val is not None else ""
    return s not in ("", "None", "-", "x", "X")


def _compute_station(species_list, round_name: str, station: str):
    """
    지점별 TESB / AESB / 출현종수 계산.
      출현 판단 : 빈값·"-"·"x" 이외 모든 값 (숫자·기호 포함)
      TESB      = Σ Qi(TESB)  (출현 종 전체)
      AESB      = Σ Qi(AESB)  / (Qi(AESB) 점수가 있는 종수)
    """
    key = f"현지_{round_name}_{station}"
    n_total = 0      # 출현 종수 (기호 포함)
    sum_tesb = 0.0
    sum_aesb = 0.0
    n_aesb = 0       # Qi(AESB) 점수가 있는 종수

    for sp in species_list:
        if not _is_present(sp.rounds.get(key)):
            continue
        n_total += 1
        sum_tesb += getattr(sp, "score_tesb", 0.0) or 0.0
        aesb_score = getattr(sp, "score_aesb", 0.0) or 0.0
        if aesb_score:
            sum_aesb += aesb_score
            n_aesb += 1

    aesb = sum_aesb / n_aesb if n_aesb > 0 else 0.0
    return sum_tesb, aesb, n_total


# ── 테이블 스타일 상수 ────────────────────────────────────────────
_HDR_BG     = "#D0D7E3"   # 헤더 셀 배경
_HDR_TXT    = _TXT
_LABEL_BG   = "#EEF1F6"   # 행 라벨 열 배경
_WHITE_BG   = "#FFFFFF"   # 일반 평가 텍스트 셀 배경

# 열 순서 상수
_ROW_LABELS = ["출현종수", "T E S B", "A E S B",
               "물환경 평가 등급", "생물 다양성", "환경 상태", "관리수역 구분"]
_RI_N    = 0
_RI_CLS  = 3
_RI_BIO  = 4
_RI_ENV  = 5
_RI_MGT  = 6


def _hdr_item(txt: str, bold: bool = True) -> QTableWidgetItem:
    """헤더 스타일 셀."""
    it = QTableWidgetItem(str(txt))
    it.setTextAlignment(Qt.AlignCenter)
    it.setBackground(QColor(_HDR_BG))
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    return it


def _lbl_item(txt: str) -> QTableWidgetItem:
    """행 라벨 열 스타일 셀."""
    it = QTableWidgetItem(str(txt))
    it.setTextAlignment(Qt.AlignCenter)
    it.setBackground(QColor(_LABEL_BG))
    f = it.font(); f.setBold(True); it.setFont(f)
    return it


def _boost_saturation(hex_color: str, sat_mul: float = 1.3, val_mul: float = 1.0) -> str:
    """기본 등급색 대비 채도를 높여 채택 점수를 더 눈에 띄게 만든다."""
    c = QColor(hex_color)
    h, s, v, a = c.getHsv()
    # 무채색/예외값 방지: hsv 변환이 불안정하면 원색 유지
    if h < 0:
        return hex_color
    s2 = max(0, min(255, int(s * sat_mul)))
    v2 = max(0, min(255, int(v * val_mul)))
    return QColor.fromHsv(h, s2, v2, a).name()


_ADOPTED_ROLE = Qt.UserRole + 1


def _grade_color(grade: str) -> str:
    """등급별 단색 배경 색상. _CLASS_INFO의 색상을 사용."""
    for g, _, _, _, _, _, bg in _CLASS_INFO:
        if g == grade:
            return bg
    return "#FFFFFF"


class _AdoptedItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.data(_ADOPTED_ROLE):
            painter.save()
            pen = QPen(QColor("#565656"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()


def _make_eval_table(all_species, rounds_stations: OrderedDict,
                     has_score: bool) -> QTableWidget:
    """
    조사차수를 왼쪽 열(지점수 만큼 병합), 지점을 그 옆 열, 지표를 나머지 열로 하는 평가표.
    등급은 지점별 TESB·AESB 중 낮은 쪽을 채택.
    구조:
      헤더 : [조사차수] [조사지점] [출현종수] [TESB] [AESB] [산정등급] [생물다양성] [환경상태] [관리수역]
    """
    rounds_order = list(rounds_stations.keys())

    # 행 목록: (차시, 지점)
    row_list = [(rnd, st)
                for rnd in rounds_order
                for st in rounds_stations[rnd]]

    n_metric_cols = len(_ROW_LABELS)
    n_cols = 2 + n_metric_cols   # 차수 열 + 지점 열 + 지표 열들
    n_rows = len(row_list)

    tbl = CopyableTableWidget(n_rows, n_cols)
    tbl.setItemDelegate(_AdoptedItemDelegate(tbl))
    tbl.verticalHeader().setVisible(False)
    tbl.setEditTriggers(QTableWidget.NoEditTriggers)
    tbl.setSelectionMode(QTableWidget.ExtendedSelection)
    tbl.setSelectionBehavior(QTableWidget.SelectItems)
    tbl.setShowGrid(True)

    # 열 헤더
    tbl.setHorizontalHeaderLabels(["조사차수", "조사지점"] + _ROW_LABELS)
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    for c in range(2, n_cols):
        tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
    tbl.verticalHeader().setDefaultSectionSize(30)

    # ── 차수 열: 차시별 지점 수 만큼 행 병합 ──────────────────
    start_ri = 0
    for rnd in rounds_order:
        stations = rounds_stations[rnd]
        span = len(stations)
        tbl.setItem(start_ri, 0, _hdr_item(rnd))
        if span > 1:
            tbl.setSpan(start_ri, 0, span, 1)
        start_ri += span

    # ── 지점 열 + 지표 데이터 ────────────────────────────────
    for ri, (rnd, st) in enumerate(row_list):
        tbl.setItem(ri, 1, _lbl_item(st))

        tesb, aesb, n = _compute_station(all_species, rnd, st)

        if has_score:
            cls_t = _classify(tesb, "TESB")   # (등급, …, bg)
            cls_a = _classify(aesb, "AESB")
            rank_t = _GRADE_ORDER[cls_t[0]]
            rank_a = _GRADE_ORDER[cls_a[0]]
            tesb_adopted = rank_t >= rank_a    # 낮은(나쁜) 등급 = 더 높은 rank
            aesb_adopted = rank_a >= rank_t
            adopted       = cls_t if tesb_adopted else cls_a
            cls_label, _, _, biodiv, env_state, mgmt, bg = adopted

            tesb_txt = f"{tesb:.0f} ({cls_t[0]})"
            aesb_txt = f"{aesb:.2f} ({cls_a[0]})"
            tesb_cell_bg = _grade_color(cls_t[0])
            aesb_cell_bg = _grade_color(cls_a[0])
        else:
            cls_label = biodiv = env_state = mgmt = bg = None
            tesb_txt = aesb_txt = "—"
            tesb_cell_bg = aesb_cell_bg = None

        vals = [
            str(n),
            tesb_txt,
            aesb_txt,
            cls_label   if has_score else "—",
            biodiv      if has_score else "—",
            env_state   if has_score else "—",
            mgmt        if has_score else "—",
        ]

        for ci_off, val in enumerate(vals):
            col = 2 + ci_off
            it = _item(val)
            if has_score:
                if ci_off == 1 and tesb_cell_bg:
                    it.setBackground(QColor(tesb_cell_bg))
                    if tesb_adopted:
                        boosted_bg = _boost_saturation(tesb_cell_bg)
                        it.setBackground(QColor(boosted_bg))
                        f = it.font(); f.setBold(True); it.setFont(f)
                        it.setForeground(QColor("#000000"))
                        it.setData(_ADOPTED_ROLE, True)
                elif ci_off == 2 and aesb_cell_bg:
                    it.setBackground(QColor(aesb_cell_bg))
                    if aesb_adopted:
                        boosted_bg = _boost_saturation(aesb_cell_bg)
                        it.setBackground(QColor(boosted_bg))
                        f = it.font(); f.setBold(True); it.setFont(f)
                        it.setForeground(QColor("#000000"))
                        it.setData(_ADOPTED_ROLE, True)
                elif ci_off >= _RI_CLS:
                    it.setBackground(QColor(_WHITE_BG))
            tbl.setItem(ri, col, it)

    return tbl


def _copy_full_table(tbl: CopyableTableWidget):
    """선택 영역이 있으면 그것만, 없으면 표 전체를 클립보드에 복사."""
    if tbl.selectedRanges():
        tbl.copy_selection()
        return
    rows = tbl.rowCount()
    cols = tbl.columnCount()
    lines, html_rows = [], ["<table border='1' cellspacing='0' cellpadding='4'>"]
    for r in range(rows):
        cells, hcells = [], ["<tr>"]
        for c in range(cols):
            it  = tbl.item(r, c)
            txt = it.text() if it else ""
            rs  = tbl.rowSpan(r, c)
            cs  = tbl.columnSpan(r, c)
            cells.append(txt)
            span = ""
            if rs > 1: span += f" rowspan='{rs}'"
            if cs > 1: span += f" colspan='{cs}'"
            hcells.append(f"<td{span}>{txt}</td>")
        hcells.append("</tr>")
        lines.append("\t".join(cells))
        html_rows.append("".join(hcells))
    html_rows.append("</table>")
    mime = QMimeData()
    mime.setText("\n".join(lines))
    mime.setHtml("".join(html_rows))
    QApplication.clipboard().setMimeData(mime)


def _score_range_text(scores, criteria: str) -> str:
    if not scores:
        return "-"
    lo = min(scores)
    hi = max(scores)
    if criteria == "TESB":
        return f"{lo:.0f}~{hi:.0f}"
    return f"{lo:.2f}~{hi:.2f}"


def _range_or_single(values) -> str:
    if not values:
        return "-"
    if values[0] == values[-1]:
        return values[0]
    return f"{values[0]}~{values[-1]}"


def _build_eval_sentence(all_species, rounds_stations: OrderedDict, has_score: bool) -> str:
    if not has_score:
        return "수환경 평가 결과, Qi 점수 컬럼이 없어 문장을 생성할 수 없습니다."

    tesb_scores, aesb_scores, adopted_rows = [], [], []
    for rnd, stations in rounds_stations.items():
        for st in stations:
            tesb, aesb, _ = _compute_station(all_species, rnd, st)
            tesb_scores.append(tesb)
            aesb_scores.append(aesb)
            cls_label, _, _, biodiv, env_state, mgmt, _ = _adopted_cls(tesb, aesb)
            adopted_rows.append((cls_label, biodiv, env_state, mgmt))

    if not adopted_rows:
        return "수환경 평가 결과, 평가 가능한 지점 데이터가 없습니다."

    # 채택 등급 기준으로 정렬 (A→E 순)
    adopted_rows.sort(key=lambda x: _GRADE_ORDER.get(x[0], 99))

    tesb_txt  = _score_range_text(tesb_scores, "TESB")
    aesb_txt  = _score_range_text(aesb_scores, "AESB")
    grade_txt = _range_or_single([adopted_rows[0][0], adopted_rows[-1][0]])
    biodiv_txt = _range_or_single([adopted_rows[0][1], adopted_rows[-1][1]])
    env_txt   = _range_or_single([adopted_rows[0][2], adopted_rows[-1][2]])
    zone_txt  = _range_or_single([adopted_rows[0][3], adopted_rows[-1][3]])

    return (
        f"수환경 평가 결과, TESB 생태점수는 \"{tesb_txt}\", "
        f"AESB 생태점수는 \"{aesb_txt}\", "
        f"산정 등급은 \"{grade_txt}\", 생물다양성은 \"{biodiv_txt}\", "
        f"환경상태는 \"{env_txt}\", 지역구분으로는 \"{zone_txt}\"으로 분석됨"
    )




def build_water_eval_tab(parsed_aquatic: dict) -> QWidget:
    """
    수환경평가 탭 위젯 반환.
    parsed_aquatic : {sheet_name: ParsedAquatic}  — 저서상(benthos) 시트만 전달할 것
    """
    w = QWidget()
    w.setStyleSheet(_QSS)
    outer = QVBoxLayout(w)
    outer.setContentsMargins(10, 10, 10, 10)
    outer.setSpacing(10)

    # 저서상(benthos) 시트만 선택
    benthos = {
        name: pa for name, pa in parsed_aquatic.items()
        if pa and pa.taxon == "benthos" and pa.species
    }
    if not benthos:
        lbl = QLabel("저서상(benthos) 데이터가 없습니다.\n수환경평가는 저서상 데이터만 사용합니다.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"{FF_KR}; font-size:13px; color:{_SUB};")
        outer.addWidget(lbl)
        return w
    target = benthos

    all_round_names = []
    for pa in target.values():
        if pa and pa.meta:
            for rn in pa.meta.round_names:
                if rn not in all_round_names:
                    all_round_names.append(rn)

    rounds_stations = _extract_rounds_stations(all_round_names)
    all_species = [sp for pa in target.values() for sp in pa.species]

    # 실제 관측 기록이 있는 (차시, 지점) 조합만 유지
    # — 헤더에 열이 있어도 데이터가 없는 차수는 제외
    def _has_data(rnd: str, st: str) -> bool:
        key = f"현지_{rnd}_{st}"
        return any(_is_present(sp.rounds.get(key)) for sp in all_species)

    rounds_stations = OrderedDict(
        (rnd, [st for st in stations if _has_data(rnd, st)])
        for rnd, stations in rounds_stations.items()
    )
    rounds_stations = OrderedDict(
        (rnd, stations)
        for rnd, stations in rounds_stations.items()
        if stations
    )

    if not rounds_stations:
        lbl = QLabel("현지조사 데이터(차시/지점)가 없습니다.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"{FF_KR}; font-size:13px; color:{_SUB};")
        outer.addWidget(lbl)
        return w

    has_score = any(
        getattr(sp, "score_aesb", 0.0) or getattr(sp, "score_tesb", 0.0)
        for sp in all_species
    )

    # ── 정보 바 (등급 범례 + 복사 버튼) ─────────────────────────
    bar = QFrame()
    bar.setStyleSheet(f"QFrame {{ background:{_CARD}; {BD}; border-radius:10px; }}")
    bar_lay = QHBoxLayout(bar)
    bar_lay.setContentsMargins(14, 8, 14, 8)
    bar_lay.setSpacing(10)

    info_lbl = QLabel("산정 등급: TESB·AESB 중 낮은 등급 채택")
    info_lbl.setStyleSheet(f"{FF_KR}; font-size:12px; color:{_SUB};")
    bar_lay.addWidget(info_lbl)
    bar_lay.addStretch()

    leg_lbl = QLabel("등급:")
    leg_lbl.setStyleSheet(f"{FF_KR}; font-size:11px; color:{_SUB};")
    bar_lay.addWidget(leg_lbl)
    for cls_label, tesb_min, aesb_min, biodiv, env_state, mgmt, bg in _CLASS_INFO:
        chip = QLabel(f"  {cls_label}  ")
        chip.setStyleSheet(
            f"background:{bg}; border-radius:4px; padding:2px 4px;"
            f" {FF_KR}; font-size:12px; font-weight:700; color:{_TXT};"
        )
        chip.setToolTip(
            f"등급 {cls_label}  |  {mgmt}\n"
            f"TESB≥{tesb_min}  /  AESB≥{aesb_min}\n"
            f"생물다양성: {biodiv}  /  환경상태: {env_state}"
        )
        bar_lay.addWidget(chip)

    if not has_score:
        warn = QLabel("  ※ Qi 컬럼 없음 — 등급 계산 불가")
        warn.setStyleSheet(f"{FF_KR}; font-size:11px; color:#D97706;")
        bar_lay.addWidget(warn)

    tbl_holder: list[CopyableTableWidget] = [None]
    btn_copy = make_copy_button(lambda: tbl_holder[0], height=28)
    bar_lay.addWidget(btn_copy)

    outer.addWidget(bar)

    # ── 문장 그룹 ────────────────────────────────────────────
    sent_txt = QPlainTextEdit()
    sent_txt.setReadOnly(True)
    sent_txt.setFixedHeight(90)
    sent_txt.setStyleSheet(
        f"QPlainTextEdit{{background:{_BG};border:1.5px solid {_BORDER};"
        f"border-radius:8px;{FF_KR};font-size:12px;padding:6px;color:{_TXT};}}"
    )

    grp_sent = QGroupBox("문장")
    grp_sent.setStyleSheet("QGroupBox{background:#FFFFFF;}")
    sent_lay = QVBoxLayout(grp_sent)
    sent_lay.setContentsMargins(8, 8, 8, 8)
    sent_lay.setSpacing(6)

    from ui_shared import _COPY_BTN_QSS
    btn_sent_copy = QPushButton("📋  복사")
    btn_sent_copy.setFixedHeight(30)
    btn_sent_copy.setStyleSheet(_COPY_BTN_QSS)
    sent_btn_row = QHBoxLayout()
    sent_btn_row.addWidget(btn_sent_copy)
    sent_btn_row.addStretch()
    sent_lay.addLayout(sent_btn_row)
    sent_lay.addWidget(sent_txt)

    def _copy_sentence():
        QApplication.clipboard().setText(sent_txt.toPlainText())
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_sent_copy)

    btn_sent_copy.clicked.connect(_copy_sentence)

    # ── 테이블 빌드 (단일 렌더링) ────────────────────────────
    tbl = _make_eval_table(all_species, rounds_stations, has_score)
    tbl_holder[0] = tbl
    outer.addWidget(tbl, stretch=1)
    outer.addWidget(grp_sent)
    sent_txt.setPlainText(_build_eval_sentence(all_species, rounds_stations, has_score))

    return w
