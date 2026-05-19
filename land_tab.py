from __future__ import annotations
# land_tab.py — 육상동물 분석 탭 v6

import math, sys, os, colorsys, re

from aqua_tab import _set_total_pct_cell
sys.path.insert(0, os.path.dirname(__file__))

from collections import OrderedDict, defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QLabel, QPlainTextEdit, QPushButton,
    QTabWidget, QScrollArea, QFrame, QSizePolicy,
    QApplication, QDoubleSpinBox, QFormLayout,
    QDialog, QDialogButtonBox, QRadioButton, QButtonGroup,
    QSpinBox, QLineEdit, QToolButton, QCheckBox, QColorDialog,
    QSlider, QComboBox, QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    _MPL = True
except ImportError:
    _MPL = False

from analyzer import TaxaStats
from parser   import ParsedSheet, ParsedProtected

# ── config / ui_shared 에서 공통 요소 import ──────────────────────
from config import (
    _BG, _CARD, _BORDER, _TXT, _SUB, _PATH,
    _ACCENT, _ACCENT_D, _ACCENT_L, _SUCCESS, _WARN, _ERR,
    _FONT_EN, _FONT_KR, FF_KR,
    ACCENT, WARN,
    PIE_COLORS, GRAPH_H,
    LIFE_DISPLAY, TRACE_MAP, SITE_TAXONS, TAXON_LABEL,
    SETTINGS, CHK_INDICATOR_QSS,
)
from ui_shared import (
    DragPctSlider, GraphValueSlider, _normalized_percentages, _apply_ratio_correction, make_tab_qss, make_scroll_widget, make_copy_button,
    bold_row, set_total_pct_cell, apply_light_chart_axes,
    CopyableTableWidget,
    _item, _int, _fmt, _pct, _make_tbl, _auto_fit_table, _tbl_auto_height,
    _Canvas, PieCanvas, CanvasGroupBox, ResizableCanvasFrame, CanvasSizeSlider,
    _apply_mpl, _get_nice_bounds, _apply_axes_common, _apply_bar_margins, _apply_graph_scale,
    _series_palette, _gray_palette, make_color_settings_btn, make_copy_graph_btn,
    normalize_tbl_pct_col,
    lit_result_prefix, lit_shi_prefix,
    make_outline_btn_qss, _COPY_BTN_QSS, _OUTLINE_BTN_GREEN, _OUTLINE_BTN_ORANGE,
)
from graph_widgets import (
    apply_graph_default,
    wrap_canvas as _common_wrap_canvas,
    make_settings_below_graph as _common_make_settings_below_graph,
    make_triplet as _common_make_triplet,
    make_pie_settings_panel as _common_make_pie_settings_panel,
    make_bar_settings_panel as _common_make_bar_settings_panel,
    auto_pie_side as _common_pie_side,
    attach_title_controls_to_canvas_group as _attach_title_to_cv,
)
from shared import _has_present, _prot_list_graded, _ecosystem_disturber_list, _apply_title, _resolve_iga, _josa


_DIALOG_QSS = f"""
    QDialog {{ background: {_BG}; {FF_KR}; }}
    QLabel, QCheckBox {{ {FF_KR}; font-size: 13px; color: {_TXT}; }}
    QTabWidget::pane {{ border: 1.5px solid {_BORDER}; border-radius: 0 8px 8px 8px; background: {_CARD}; }}
    QTabBar::tab {{
        {FF_KR}; font-size: 13px; font-weight: 600; padding: 6px 16px;
        background: #E9ECEF; border: 1.5px solid {_BORDER};
        border-bottom: none; border-radius: 6px 6px 0 0;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{ background: {_CARD}; color: {_ACCENT}; font-weight: 700; border-bottom: none; }}
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QListWidget {{
        border: 1.5px solid {_BORDER}; border-radius: 6px;
        padding: 4px 8px; background: white; {FF_KR}; font-size: 13px; color: {_TXT};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:hover, QLineEdit:focus, QListWidget:focus {{ border-color: {_ACCENT}; }}
    QPushButton {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {_ACCENT}, stop:1 {_ACCENT_D});
        color: white; border: none; border-radius: 7px;
        {FF_KR}; font-size: 13px; font-weight: 700; padding: 8px 18px;
    }}
    QPushButton:hover {{ background: #3B82F6; }}
""" + CHK_INDICATOR_QSS


def _tab_qss(big=True):
    py = "7px" if big else "5px"
    px = "18px" if big else "14px"
    fs = "12px" if big else "11px"
    mh = "18px" if big else "16px"
    radius = "10px" if big else "9px"
    pane_radius = "12px" if big else "10px"
    return f"""
        QTabBar {{ qproperty-drawBase: 0; }}
        QTabBar::tab {{
            {FF_KR}; font-size:{fs}; font-weight:600;
            min-height:{mh}; padding:{py} {px};
            background:#EEF2F7; color:{_SUB};
            border:1px solid transparent;
            border-radius:{radius};
            margin-right:6px;
        }}
        QTabBar::tab:selected {{
            background:#FFFFFF; color:{_ACCENT}; font-weight:700;
            border-color:#DCE5F0;
        }}
        QTabBar::tab:hover {{ background:#F8FBFF; color:{_ACCENT}; }}
        QTabWidget::pane {{
            border:none; background:transparent;
        }}
    """



# _fmt / _pct / _int / _item / _make_tbl / _auto_fit_table / CopyableTableWidget
# → ui_shared 에서 import (상단 참조)


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _rn(name: str) -> str:
    return name.replace("문헌_","").replace("현지_","")

def _round_survey_label(label: str) -> str:
    label = str(label or "").strip()
    if not label:
        return "조사"
    if "".join(label.split()).endswith("조사"):
        return label
    return f"{label} 조사"

def _survey_prefix(survey: str, rns) -> str:
    survey_name = "현지조사" if survey == "field" else "문헌조사"
    if getattr(SETTINGS, "field_intro_mode", "auto") == "fixed":
        return survey_name
    labels = []
    for r in rns or []:
        if "합계" in r or "종합" in r:
            continue
        lbl = _rn(r)
        if lbl and lbl not in labels:
            labels.append(lbl)
    if len(labels) > 1:
        return f"총 {len(labels)}회의 {survey_name}"
    if len(labels) == 1:
        return _round_survey_label(labels[0])
    return survey_name


# ── 종 집합 분리 ──────────────────────────────────────────────────────────────
def _species_by_round(sheet: ParsedSheet) -> dict:
    fld_rounds = [r for r in sheet.meta.round_names
                  if "현지" in r and r != "현지_합계"]
    lit_rounds  = [r for r in sheet.meta.round_names if "문헌" in r]
    fld_all = [sp for sp in sheet.species
               if any(_has_present(sp.rounds.get(r)) for r in fld_rounds)]
    lit_all = [sp for sp in sheet.species
               if any(_has_present(sp.rounds.get(r)) for r in lit_rounds)]
    field = {}
    if fld_all:
        field["전체"] = fld_all
        for r in fld_rounds:
            sub = [sp for sp in sheet.species if _has_present(sp.rounds.get(r))]
            if sub: field[r] = sub
    lit = {}
    if lit_all:
        lit["전체"] = lit_all
        for r in lit_rounds:
            sub = [sp for sp in sheet.species if _has_present(sp.rounds.get(r))]
            if sub: lit[r] = sub
    return {"field": field, "lit": lit}

def _family_count(species_list) -> int:
    return len(set(sp.family for sp in species_list if sp.family))

def _genus_count(species_list) -> int:
    return len(set(sp.sci_name.split()[0] for sp in species_list
                   if sp.sci_name and sp.sci_name.split()))

def _order_count(species_list) -> int:
    return len(set(sp.order for sp in species_list if sp.order))

def _taxa_counts_str(species_list) -> str:
    """SETTINGS 레벨 설정에 따라 '목 과 속 종' 카운트 문자열 생성."""
    S = SETTINGS
    parts = []
    if S.sent_show_order:  parts.append(f"{_order_count(species_list)}목")
    if S.sent_show_family: parts.append(f"{_family_count(species_list)}과")
    if S.sent_show_genus:  parts.append(f"{_genus_count(species_list)}속")
    if S.sent_show_species:parts.append(f"{len(species_list)}종")
    return " ".join(parts) if parts else f"{len(species_list)}종"



def _order_counts(species_list) -> dict:
    d = {}
    for sp in species_list:
        if sp.order not in d:
            d[sp.order] = 0
        d[sp.order] += 1
    return d

def _calc_div_indiv(species_list, rns) -> dict:
    if not species_list: return {"H":0.0, "E":0.0, "RI":0.0}
    indiv_list = []
    for sp in species_list:
        cnt = sum(_int(sp.rounds.get(r, 0)) for r in rns if "합계" not in r and "종합" not in r)
        if cnt > 0:
            indiv_list.append(cnt)
    total = sum(indiv_list)
    S = len(indiv_list)
    if total == 0 or S == 0:
        return {"H":0.0, "E":0.0, "RI":0.0}
    H = sum(-(c/total)*math.log(c/total) for c in indiv_list)
    E = H / math.log(S) if S > 1 else 0.0
    RI = (S - 1) / math.log(total) if total > 1 else 0.0
    return {"H":H, "E":E, "RI":RI}

def _dom_rows(species, rns, limit=7, min_pct=None, force_norm=False):
    rns_clean = [r for r in rns if "합계" not in r and "종합" not in r]
    rows = []
    for sp in species:
        indiv = sum(_int(sp.rounds.get(r, 0)) for r in rns_clean)
        if indiv > 0:
            rows.append([sp, indiv])
    rows.sort(key=lambda x: (-x[1], x[0].kor_name or getattr(x[0], 'sci_name', '')))

    counts = [x[1] for x in rows]
    if force_norm:
        pcts, _ = _apply_ratio_correction(_normalized_percentages(counts))
    else:
        total_ind = sum(counts)
        pcts = [c / total_ind * 100 if total_ind else 0 for c in counts]
    
    final_rows = []
    for (sp, indiv), pct in zip(rows, pcts):
        if min_pct is not None and pct < min_pct: continue
        final_rows.append((sp, indiv, pct))
    return final_rows[:limit]

def _format_dom(dom_rows):
    if not dom_rows: return "", "", ""
    dom = dom_rows[0]
    dom_str = f"{(dom[0].kor_name or getattr(dom[0], 'sci_name', ''))} {dom[1]:,}개체({_pct(dom[2])})"
    sub_str = ""
    rest_str = ""
    if len(dom_rows) > 1:
        sub = dom_rows[1]
        sub_str = f"{(sub[0].kor_name or getattr(sub[0], 'sci_name', ''))} {sub[1]:,}개체({_pct(sub[2])})"
    if len(dom_rows) > 2:
        grouped = defaultdict(list)
        for r in dom_rows[2:]:
            name = r[0].kor_name or getattr(r[0], 'sci_name', '')
            grouped[(r[1], r[2])].append(name)
        rest_parts = []
        for (cnt, pct), names in sorted(grouped.items(), key=lambda x: -x[0][0]):
            name_str = ", ".join(names)
            if len(names) > 1:
                rest_parts.append(_resolve_iga(f"{name_str}이(가) 각각 {cnt:,}개체({_pct(pct)})", name_str))
            else:
                rest_parts.append(f"{name_str} {cnt:,}개체({_pct(pct)})")
        rest_str = ", ".join(rest_parts)
    return dom_str, sub_str, rest_str

def _dominance_sentence(label, dom_rows, end_text, threshold_pct=None):
    dom_str, sub_str, rest_str = _format_dom(dom_rows)
    if not dom_str:
        if threshold_pct is None:
            return f"조사지역 내 출현 {label}의 우점종은 확인되지 않음"
        return f"조사지역 내 출현 {label}의 우점도 {threshold_pct:.1f}% 이상 종은 확인되지 않음"

    s = f"조사지역 내 출현 {label}의 우점종은 {dom_str}"
    if sub_str:
        s += f", 아우점종은 {sub_str}"
    if rest_str:
        s += f", 그 외 {rest_str} 등의 순"
    return f"{s}{_josa(s, '으로로')} {end_text}"

def _dominance_sentence_from_table_rows(label, dom_rows, end_text, threshold_pct=None):
    if not dom_rows:
        if threshold_pct is None:
            return f"조사지역 내 출현 {label}의 우점종은 확인되지 않음"
        return f"조사지역 내 출현 {label}의 우점도 {threshold_pct:.1f}% 이상 종은 확인되지 않음"

    def _name(row): return row[0]
    def _cnt(row): return int(row[1])
    def _pct_val(row): return float(row[2])
    def _part(row): return f"{_name(row)} {_cnt(row):,}개체({_pct(_pct_val(row))})"

    s = f"조사지역 내 출현 {label}의 우점종은 {_part(dom_rows[0])}"
    if len(dom_rows) > 1:
        s += f", 아우점종은 {_part(dom_rows[1])}"
    if len(dom_rows) > 2:
        grouped = defaultdict(list)
        for row in dom_rows[2:]:
            grouped[(_cnt(row), _pct_val(row))].append(_name(row))
        rest_parts = []
        for (cnt, pct), names in sorted(grouped.items(), key=lambda x: -x[0][0]):
            name_str = ", ".join(names)
            if len(names) > 1:
                rest_parts.append(_resolve_iga(f"{name_str}이(가) 각각 {cnt:,}개체({_pct(pct)})", name_str))
            else:
                rest_parts.append(f"{name_str} {cnt:,}개체({_pct(pct)})")
        s += f", 그 외 {', '.join(rest_parts)} 등의 순"
    return f"{s}{_josa(s, '으로로')} {end_text}"

def _life_str(species_list, force_norm=False):
    life_cnt = {}
    for sp in species_list:
        lv = sp.rounds.get("life")
        if not lv or str(lv).strip() in ("","None"): continue
        for code in str(lv).strip().upper().split("+"):
            code = code.strip()
            if code: life_cnt[code] = life_cnt.get(code, 0) + 1
    total = len(species_list)
    disp = dict(LIFE_DISPLAY)
    counts = [cnt for code, cnt in sorted(life_cnt.items(), key=lambda x: -x[1])]
    if force_norm:
        pcts, _ = _apply_ratio_correction(_normalized_percentages(counts))
    else:
        pcts = [c / total * 100 if total else 0 for c in counts]
    parts = []
    dec = SETTINGS.decimal
    for (code, cnt), pct in zip(sorted(life_cnt.items(), key=lambda x: -x[1]), pcts):
        name = disp.get(code, code).split("(")[0]
        parts.append(f"{name} {cnt}종({pct:.{dec}f}%)")
    return ", ".join(parts)

def _order_str(species_list, survey="field", force_norm=False):
    S = SETTINGS
    verb = S.order_verb_f if survey == "field" else S.order_verb_l
    oc = _order_counts(species_list)
    ok_map = _get_ok_map(species_list)
    sorted_oc = list(oc.items())
    counts_arr = [cnt for eng, cnt in sorted_oc]
    if force_norm:
        pcts, _ = _apply_ratio_correction(_normalized_percentages(counts_arr))
    else:
        total = len(species_list)
        pcts = [cnt / total * 100 if total else 0 for cnt in counts_arr]

    grouped = defaultdict(list)
    for (eng, cnt), pct in zip(sorted_oc, pcts):
        kor = ok_map.get(eng, eng)
        grouped[cnt].append((kor, pct))
    grouped_sorted = sorted(grouped.items(), key=lambda x: -x[0])
    formatted_parts = []
    dec = SETTINGS.decimal
    for i, (cnt, items) in enumerate(grouped_sorted):
        names = [x[0] for x in items]
        pct = items[0][1]
        name_str = "과 ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + "과 " + names[-1]
        if i == 0:
            formatted_parts.append(_resolve_iga(f"{name_str}이(가) {cnt}종({_pct(pct)})로 가장 많이 {verb}", name_str))
        else:
            suffix = "각각 " if len(names) > 1 else ""
            formatted_parts.append(_resolve_iga(f"{name_str}이(가) {suffix}{cnt}종({_pct(pct)})", name_str))
    if len(formatted_parts) > 1:
        return formatted_parts[0] + f", {S.order_next} " + ", ".join(formatted_parts[1:])
    else:
        return formatted_parts[0] if formatted_parts else ""

AMPHIBIA_ORDERS = {"도롱뇽목", "CAUDATA", "개구리목", "ANURA", "무미목", "유미목"}
REPTILIA_ORDERS = {"거북목", "TESTUDINES", "뱀목", "SQUAMATA", "유린목"}
def _get_herp_group(sp):
    o = (sp.order or "").strip().upper()
    k = getattr(sp, "order_kor", "").strip()
    if o in AMPHIBIA_ORDERS or k in AMPHIBIA_ORDERS: return "양서류"
    if o in REPTILIA_ORDERS or k in REPTILIA_ORDERS: return "파충류"
    return "양서파충류"

def _calc_div(species_list) -> dict:
    oc = defaultdict(int)
    for sp in species_list: oc[sp.order] += 1
    total = len(species_list)
    if not total: return {"H":0.0,"E":0.0,"RI":0.0}
    H  = sum(-(c/total)*math.log(c/total) for c in oc.values() if c > 0)
    S  = len(oc)
    E  = H/math.log(S) if S > 1 else 0.0
    RI = (S-1)/math.log(total) if total > 1 else 0.0
    return {"H":H,"E":E,"RI":RI}


def _prot_none_contrast(text: str) -> str:
    s = str(text or "").strip().rstrip(",")
    rules = [
        ("되지 않았음", "되지 않았으나"), ("되지 않았다", "되지 않았으나"), ("되지 않음", "되지 않았으나"),
        ("하지 않았음", "하지 않았으나"), ("하지 않았다", "하지 않았으나"), ("하지 않음", "하지 않았으나"),
        ("나지 않았음", "나지 않았으나"), ("나지 않았다", "나지 않았으나"), ("나지 않음", "나지 않았으나"),
        ("없었음", "없었으나"), ("없었다", "없었으나"), ("없음", "없으나"),
        ("않았음", "않았으나"), ("않았다", "않았으나"), ("않음", "않으나"),
    ]
    for old, new in rules:
        if s.endswith(old):
            return s[: -len(old)] + new
    if s.endswith("음"):
        return s[:-1] + "으나"
    if s.endswith("다"):
        return s[:-1] + "나"
    return s + "이나"


def _prot_list(taxon, prot_sheet, species_list):
    if not prot_sheet: return 0, ""
    tmap = {"mammal":"포유류","bird":"조류",
            "herp":"양서류·파충류","insect":"곤충류"}
    my    = tmap.get(taxon,"")
    names = {sp.kor_name for sp in species_list}
    prot  = [sp.kor_name for sp in prot_sheet.species
             if (not my or sp.group == my) and sp.kor_name in names]
    if not prot: return 0, ""
    return len(prot), ", ".join(prot) + f" 등 총 {len(prot)}종"




def _get_tbl(obj):
    if isinstance(obj, QTableWidget): return obj
    if hasattr(obj, "findChild"):
        return obj.findChild(QTableWidget)
    return None

def _extract_pie_data(tbl_obj, lcol, vcol, skip_last=True):
    tbl = _get_tbl(tbl_obj)
    d = OrderedDict()
    if not tbl: return d
    for r in range(tbl.rowCount() - (1 if skip_last else 0)):
        it_l = tbl.item(r, lcol)
        it_v = tbl.item(r, vcol)
        l = it_l.text() if it_l else ""
        txt = it_v.text().replace(',', '').replace('%', '').strip() if it_v else "0"
        try:
            v = float(txt)
        except ValueError:
            v = 0.0
        d[l] = d.get(l, 0.0) + v
    return d

# ══════════════════════════════════════════════════════════════════════════════
# 차트 함수 — 캔버스를 인자로 받아 내부에서 다시 그림 (설정 실시간 반영용)
# ══════════════════════════════════════════════════════════════════════════════

def _draw_bird_combo(canvas: _Canvas, tbl_obj):
    """조류 개체수+우점도 차트 그리기 (canvas 재사용)"""
    tbl = _get_tbl(tbl_obj)
    if not _MPL or not tbl: return
    
    rows = []
    for r in range(tbl.rowCount() - 1):
        lbl = tbl.item(r, 1).text()
        cnt = _int(tbl.item(r, 2).text().replace(',', ''))
        dom = float(tbl.item(r, 3).text().replace('%', ''))
        rows.append((lbl, cnt, dom))
    if not rows: return

    dom_pct = canvas._cfg.get("dom_pct", SETTINGS.dom_pct)
    decimal = canvas._cfg.get("decimal", SETTINGS.decimal)
    bar_horiz = canvas._cfg.get("bar_horiz", SETTINGS.bar_horiz)
    fs = canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize)
    line_color = canvas._cfg.get("line_color", SETTINGS.line_color)
    grid_on = canvas._cfg.get("grid_on", SETTINGS.grid_on)
    grid_color = canvas._cfg.get("grid_color", SETTINGS.grid_color)
    x_label_rot = canvas._cfg.get("x_label_rot", SETTINGS.x_label_rot)
    marker_size = canvas._cfg.get("marker_size", SETTINGS.marker_size)
    line_width = canvas._cfg.get("line_width", SETTINGS.line_width)
    bar_h_height = canvas._cfg.get("bar_h_height", SETTINGS.bar_h_height)
    bar_v_width = canvas._cfg.get("bar_v_width", SETTINGS.bar_v_width)
    show_count_label = canvas._cfg.get("bar_count_label_inside", getattr(SETTINGS, "bar_count_label_inside", False))
    show_legend = canvas._cfg.get("show_legend", getattr(SETTINGS, "show_legend", True))
    bar_sort = canvas._cfg.get("bar_sort", getattr(SETTINGS, "bar_sort", "desc"))

    if bar_sort == "desc":
        rows.sort(key=lambda r: r[1], reverse=True)
    elif bar_sort == "asc":
        rows.sort(key=lambda r: r[1])

    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    doms   = [r[2] for r in rows]
    colors = _series_palette(len(labels), canvas)
    label_mode = getattr(SETTINGS, "label_mode", "none")
    
    axis_min = canvas._cfg.get("axis_min", SETTINGS.axis_min)
    axis_max = canvas._cfg.get("axis_max", SETTINGS.axis_max)
    axis_step = canvas._cfg.get("axis_step", SETTINGS.axis_step)

    def _apply_axis(ax_tgt, is_x, data_max):
        c_min, c_max, c_step = axis_min, axis_max, axis_step
        effective_max = c_max if c_max > 0 else (data_max if data_max > 0 else 1.0)
        auto_max, auto_step = _get_nice_bounds(effective_max)
        
        if c_max <= 0: c_max = auto_max
        if c_step <= 0: c_step = auto_step
        if c_min < c_max:
            if is_x: ax_tgt.set_xlim(c_min, c_max)
            else: ax_tgt.set_ylim(c_min, c_max)
        if c_step > 0:
            import matplotlib.ticker as ticker
            if is_x: ax_tgt.xaxis.set_major_locator(ticker.MultipleLocator(c_step))
            else: ax_tgt.yaxis.set_major_locator(ticker.MultipleLocator(c_step))

    _apply_mpl()
    fig = canvas.figure; fig.clf()

    def _add_draggable_legend(ax, handles, labels, *, default_anchor, default_loc, ncol):
        if not handles:
            return
        anchor_key = "combo_legend_anchor_h" if bar_horiz else "combo_legend_anchor_v"
        saved_anchor = getattr(SETTINGS, anchor_key, None)
        if saved_anchor:
            anchor = (
                max(-1.0, min(2.0, float(saved_anchor[0]))),
                max(-1.0, min(2.0, float(saved_anchor[1]))),
            )
        else:
            anchor = default_anchor
        loc = "center" if saved_anchor else default_loc
        leg = ax.legend(handles, labels, loc=loc, bbox_to_anchor=anchor,
                        ncol=ncol, frameon=False, fontsize=max(7, fs - 1))
        leg.set_zorder(1000)
        canvas._active_combo_legend = leg
        canvas._active_combo_legend_info = (leg, ax, anchor_key)

        old_cid = getattr(canvas, "_combo_legend_release_cid", None)
        if old_cid is not None:
            try:
                canvas.mpl_disconnect(old_cid)
            except Exception:
                pass

        def _store_legend_anchor(event, legend=leg, legend_ax=ax):
            try:
                renderer = canvas.figure.canvas.get_renderer()
                bbox = legend.get_window_extent(renderer=renderer)
                cx = (bbox.x0 + bbox.x1) / 2
                cy = (bbox.y0 + bbox.y1) / 2
                anchor_xy = legend_ax.transAxes.inverted().transform((cx, cy))
                anchor = (
                    max(-1.0, min(2.0, float(anchor_xy[0]))),
                    max(-1.0, min(2.0, float(anchor_xy[1]))),
                )
                setattr(SETTINGS, anchor_key, anchor)
                canvas._cfg[anchor_key] = anchor
            except Exception:
                pass

        canvas._combo_legend_release_cid = canvas.mpl_connect("button_release_event", _store_legend_anchor)

    if bar_horiz:
        ax  = fig.add_subplot(111); y = range(len(labels))
        bars = ax.barh(list(y), doms, color=colors, height=bar_h_height, zorder=3, label="우점도(%)")
        ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=fs)
        ax.invert_yaxis()
        _apply_axes_common(ax, ylabel="", xlabel=getattr(SETTINGS, "y_axis_title", "우점도(%)"), fs=fs)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.spines["left"].set_zorder(5)  # 축선이 막대 위로 오게 하여 겹침(가려짐) 방지
        ax.set_axisbelow(True)
        if grid_on: ax.xaxis.grid(True, color=grid_color, linewidth=0.7)
        else: ax.xaxis.grid(False)
        ax.tick_params(axis="x", labelsize=fs)
        _apply_axis(ax, is_x=True, data_max=max(doms) if doms else 1.0)
        xmax = ax.get_xlim()[1]
        for i, (bar, c, d) in enumerate(zip(bars, counts, doms)):
            if show_count_label:
                ax.text(xmax * 0.012, i,
                        f"{c:,}", ha="left", va="center",
                        fontsize=max(6, fs - 1), fontweight="bold", color="black", zorder=6)
            ax.text(bar.get_width() + xmax * 0.01, i,
                    f"{d:.{decimal}f}%", ha="left", va="center",
                    fontsize=max(6, fs - 1), fontweight="bold", color="black", zorder=6, clip_on=False)
        if show_legend:
            handles, legend_labels = ax.get_legend_handles_labels()
            _add_draggable_legend(ax, handles, legend_labels,
                                  default_anchor=(0.98, 0.98),
                                  default_loc="upper right", ncol=1)
    else:
        ax1  = fig.add_subplot(111); x = range(len(labels))
        bars = ax1.bar(list(x), counts, color=colors, width=bar_v_width, zorder=3, label="개체수")
        
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(labels, rotation=0, ha="center", rotation_mode="anchor", fontsize=fs)
        _apply_axes_common(ax1, ylabel="개체수", fs=fs)
        ax1.spines["top"].set_visible(False); ax1.set_axisbelow(True)
        if grid_on: ax1.yaxis.grid(True, color=grid_color, linewidth=0.7)
        else: ax1.yaxis.grid(False)
        ax1.tick_params(axis="y", labelsize=fs)
        ax1.margins(x=0.05)
        _apply_axis(ax1, is_x=False, data_max=max(counts) if counts else 1.0)
        _ymax = ax1.get_ylim()[1]
        if show_count_label:
            for bar, c in zip(bars, counts):
                ax1.text(bar.get_x() + bar.get_width() / 2, _ymax * 0.015,
                         f"{c:,}", ha="center", va="bottom", fontsize=max(6, fs-1), fontweight="bold", color="black")
        ax2 = ax1.twinx()
        ax2.plot(list(x), doms, color=line_color, linewidth=line_width, marker="D", markersize=marker_size, zorder=4, label="우점도(%)")
        ax2.set_ylabel(getattr(SETTINGS, "y_axis_title", "우점도(%)"), fontsize=fs, color="black")
        ax2.tick_params(axis="y", colors="black", labelsize=fs); ax2.spines["top"].set_visible(False)
        
        # 우점도 우측 y축 눈금 및 최대치도 예쁘게 자동 정렬
        ax2_max, ax2_step = _get_nice_bounds(max(doms) if doms else 1.0)
        ax2.set_ylim(0, ax2_max)
        import matplotlib.ticker as ticker
        ax2.yaxis.set_major_locator(ticker.MultipleLocator(ax2_step))

        for xi, d in zip(x, doms):
            ax2.text(xi, d + ax2_max * 0.03, f"{d:.{decimal}f}%",
                     ha="center", va="bottom", fontsize=max(6, fs-1),
                     fontweight="bold", color="black", zorder=6)

        if show_legend:
            handles1, legend_labels1 = ax1.get_legend_handles_labels()
            handles2, legend_labels2 = ax2.get_legend_handles_labels()
            _add_draggable_legend(ax1, handles1 + handles2, legend_labels1 + legend_labels2,
                                  default_anchor=(0.5, -0.12),
                                  default_loc="upper center", ncol=2)

    _apply_bar_margins(fig, canvas)
    _apply_graph_scale(fig, canvas)
    canvas.draw()


def _draw_diversity_bar(canvas: _Canvas, tbl_obj):
    """곤충 다양도 세로 막대"""
    tbl = _get_tbl(tbl_obj)
    if not _MPL or not tbl: return
    
    decimal = 2
    fs = canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize)
    grid_on = canvas._cfg.get("grid_on", SETTINGS.grid_on)
    grid_color = canvas._cfg.get("grid_color", SETTINGS.grid_color)
    div_bar_width = canvas._cfg.get("div_bar_width", SETTINGS.div_bar_width)
    div_bar_gap = canvas._cfg.get("div_bar_gap", SETTINGS.div_bar_gap)
    
    axis_min = canvas._cfg.get("axis_min", SETTINGS.axis_min)
    axis_max = canvas._cfg.get("axis_max", SETTINGS.axis_max)
    axis_step = canvas._cfg.get("axis_step", SETTINGS.axis_step)

    labels = ["종다양도지수\n(H')", "종풍부도지수\n(RI)", "균등도지수\n(EI)"]
    values = []
    for r in range(3):
        try: values.append(float(tbl.item(r, 1).text().replace(',', '')))
        except: values.append(0.0)
        
    _cm = getattr(SETTINGS, "color_mode", "auto")
    if _cm == "gray":
        colors = _gray_palette(3)
    elif _cm == "solid":
        colors = [getattr(SETTINGS, "bar_color", "#4472C4")] * 3
    else:
        colors = [
            canvas._cfg.get("div_color_1", SETTINGS.div_color_1),
            canvas._cfg.get("div_color_2", SETTINGS.div_color_2),
            canvas._cfg.get("div_color_3", SETTINGS.div_color_3),
        ]

    _apply_mpl()
    fig = canvas.figure; fig.clf(); ax = fig.add_subplot(111)
    _n = 3
    _span = (_n - 1) * div_bar_gap
    _offset = -_span / 2
    x = [i * div_bar_gap + _offset for i in range(_n)]
    bars = ax.bar(x, values, color=colors, width=div_bar_width, zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=fs)
    _fixed_half = (_n - 1) * 0.5 + 0.5
    _axis_half = max(_fixed_half, _span / 2 + div_bar_width / 2 + 0.1)
    ax.set_xlim(-_axis_half, _axis_half)
    _apply_axes_common(ax, ylabel=getattr(SETTINGS, "y_axis_title", "지수 값"), fs=fs)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_bounds(-_axis_half, _axis_half)
    ax.spines["bottom"].set_zorder(4)
    ax.spines["left"].set_zorder(4)
    ax.set_axisbelow(True)
    if grid_on: ax.yaxis.grid(True, color=grid_color, linewidth=0.7)
    else: ax.yaxis.grid(False)
    ax.tick_params(axis="y", labelsize=fs)
    
    c_min, c_max, c_step = axis_min, axis_max, axis_step
    effective_max = c_max if c_max > 0 else (max(values) if values and max(values) > 0 else 1.0)
    auto_max, auto_step = _get_nice_bounds(effective_max)
    if c_max <= 0: c_max = auto_max
    if c_step <= 0: c_step = auto_step
    if c_min < c_max:
        ax.set_ylim(c_min, c_max)
    if c_step > 0:
        import matplotlib.ticker as ticker
        ax.yaxis.set_major_locator(ticker.MultipleLocator(c_step))
        
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f"{val:.{decimal}f}", ha="center", va="bottom", fontsize=max(6, fs-1), fontweight="bold")
    _apply_bar_margins(fig, canvas)
    _apply_graph_scale(fig, canvas)
    canvas.draw()


# ══════════════════════════════════════════════════════════════════════════════
# 표 위젯
# ══════════════════════════════════════════════════════════════════════════════

def _get_ok_map(species_list):
    m = {}
    for sp in species_list:
        if sp.order:
            kor = getattr(sp, "order_kor", "")
            m[sp.order] = kor if kor else sp.order
    return m

def _order_table(species_list, sort_mode="taxa") -> QTableWidget:
    oc    = _order_counts(species_list)
    ok_map = _get_ok_map(species_list)
    total = len(species_list)
    tbl   = _make_tbl(["목 (영문)", "목 (한글)", "종수", "비율"])
    tbl.setRowCount(len(oc) + 1)
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

    sorted_oc = list(oc.items())
    if sort_mode == "desc":
        sorted_oc.sort(key=lambda x: (-x[1], x[0]))

    pct_sum = 0.0
    for ri, (eng, cnt) in enumerate(sorted_oc):
        pct = cnt / total * 100 if total else 0
        tbl.setItem(ri, 0, _item(eng, Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(ok_map.get(eng, eng), Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(cnt))
        tbl.setItem(ri, 3, _item(_fmt(pct)))
        pct_sum += round(pct, SETTINGS.decimal)
    last = len(oc)
    tbl.setItem(last, 0, _item("합계")); tbl.setItem(last, 1, _item(""))
    tbl.setItem(last, 2, _item(total))
    set_total_pct_cell(tbl, last, 3, pct_sum,
                       item_factory=_item, pct_formatter=_fmt, err_color=_ERR,
                       decimals=SETTINGS.decimal)
    for c in range(4):
        it = tbl.item(last, c)
        if it: it.setBackground(QColor(_BG))
    _auto_fit_table(tbl)
    return tbl


def _div_table(species_list, rns) -> QTableWidget:
    div = _calc_div_indiv(species_list, rns)
    tbl = _make_tbl(["지수", "값"])
    tbl.setRowCount(3)
    for ri, (lbl, key) in enumerate([("종다양도지수(H')","H"),("종풍부도지수(RI)","RI"),("균등도지수(EI)","E")]):
        tbl.setItem(ri, 0, _item(lbl, Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(f"{div[key]:.2f}"))
        tbl.setRowHeight(ri, 24)
    tbl.verticalHeader().setDefaultSectionSize(24)
    tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # setFixedHeight 미설정 → 그룹박스 전체를 채워 빈 영역 클릭 시 선택 해제됨
    _auto_fit_table(tbl)
    return tbl


def _filtered_species_table(sheet: ParsedSheet, species_list, rname: str, threshold_pct: float, rns=None) -> QTableWidget:
    """개체수 우점도 기준 필터링 표: 설정% 이상의 종만 표시"""
    def _count_for(sp):
        if rname == "전체":
            detail_rns = [r for r in (rns or []) if "합계" not in str(r) and "종합" not in str(r)]
            cnt = sum(_int(sp.rounds.get(r)) for r in detail_rns)
            return cnt if cnt > 0 else _int(sp.rounds.get("현지_합계"))
        return _int(sp.rounds.get(rname))

    rows = [(sp, _count_for(sp)) for sp in species_list if _count_for(sp) > 0]

    counts = [c for _, c in rows]
    total_ind = sum(counts)
    
    filtered = []
    for sp, cnt in rows:
        pct = (cnt / total_ind * 100) if total_ind else 0
        if pct >= threshold_pct:
            filtered.append((sp, cnt, pct))
    filtered.sort(key=lambda x: -x[1])  # 개체수 내림차순

    tbl = _make_tbl(["학명", "국명", "개체수", "우점도"])
    tbl.setRowCount(len(filtered) + 1)
    _auto_fit_table(tbl)

    for ri, (sp, cnt, pct) in enumerate(filtered):
        tbl.setItem(ri, 0, _item(sp.sci_name or "", Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(sp.kor_name or "", Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(cnt))
        tbl.setItem(ri, 3, _item(_fmt(pct)))

    last = len(filtered)
    tbl.setItem(last, 0, _item("합계"))
    tbl.setItem(last, 1, _item(""))
    tbl.setItem(last, 2, _item(sum(c for _, c in rows)))
    tbl.setItem(last, 3, _item(_fmt(100.0 if rows else 0)))
    for c in range(4):
        it = tbl.item(last, c)
        if it:
            it.setBackground(QColor(_BG))
    return tbl


def _life_table(species_list) -> QTableWidget:
    life_cnt = {}
    for sp in species_list:
        lv = sp.rounds.get("life")
        if not lv or str(lv).strip() in ("","None"): continue
        for code in str(lv).strip().upper().split("+"):
            code = code.strip()
            if code: life_cnt[code] = life_cnt.get(code, 0) + 1
    disp  = dict(LIFE_DISPLAY)
    total = len(species_list)
    tbl   = _make_tbl(["생활형", "종수", "비율"])
    tbl.setRowCount(len(life_cnt) + 1)
    
    sorted_life = sorted(life_cnt.items(), key=lambda x: (-x[1], x[0]))
    counts = [cnt for code, cnt in sorted_life]
    
    pct_sum = 0.0
    for ri, (code, cnt) in enumerate(sorted_life):
        pct = cnt / total * 100 if total else 0
        tbl.setItem(ri, 0, _item(disp.get(code, code), Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(cnt))
        tbl.setItem(ri, 2, _item(_fmt(pct)))
        pct_sum += round(pct, SETTINGS.decimal)
    last = len(life_cnt)
    tbl.setItem(last, 0, _item("합계"))
    tbl.setItem(last, 1, _item(sum(life_cnt.values())))
    _set_total_pct_cell(tbl, last, 2, pct_sum if total else 0, pct_formatter=_fmt)
    for c in range(3):
        it = tbl.item(last, c)
        if it and c != 2:
            it.setBackground(QColor(_BG))
    _auto_fit_table(tbl)
    return tbl


# ══════════════════════════════════════════════════════════════════════════════
# 문장 생성
# ══════════════════════════════════════════════════════════════════════════════

def _cleanup_sentence_text(text: str) -> str:
    lines = []
    for line in str(text or "").split("\n"):
        s = re.sub(r"\s+,", ",", line)
        s = re.sub(r",\s*,+", ",", s)
        s = re.sub(r",\s+(이|가|은|는|의|으로|로)(?=$)", r"\1", s)
        s = re.sub(r",\s+(확인됨|확인되었음|나타남|전언됨|청취됨|서식)", r" \1", s)
        s = re.sub(r"개체이(?=\s|$)", "개체가", s)
        s = re.sub(r"\s{2,}", " ", s)
        s = re.sub(r"\s+([.)])", r"\1", s)
        lines.append(s.strip())
    return "\n".join(lines)

def _finish_sentence(text: str, title: str) -> str:
    return _apply_title(_cleanup_sentence_text(text), title)

def _resolve_leading_iga(text: str, subject: str) -> str:
    """문장 설정의 '이/가 ...' 형태를 앞 단어 받침에 맞춘다."""
    s = str(text or "")
    if s.startswith("이(가)"):
        return _resolve_iga(s, subject)
    if s.startswith("이 "):
        return _josa(subject, "이가") + s[1:]
    if s.startswith("가 "):
        return _josa(subject, "이가") + s[1:]
    return s

def _build_sentence(taxon, species_list, rns, prot_sheet, survey, split_herp=False, force_norm=False, tbl_ref=None) -> str:
    S     = SETTINGS
    label = TAXON_LABEL.get(taxon, taxon)
    total = len(species_list)
    prot_n, prot_str = _prot_list_graded(taxon, prot_sheet, species_list)
    disturb_n, disturb_clause = _ecosystem_disturber_list(prot_sheet, species_list)
    tbl_ref = tbl_ref or {}

    def _resolve_ref(name):
        ref = tbl_ref.get(name)
        if callable(ref):
            try:
                return ref()
            except Exception:
                return None
        return ref
    
    is_field = (survey == "field")
    s1_mid = S.field_s1_mid if is_field else S.lit_s1_mid
    s1_end = S.field_s1_end if is_field else S.lit_s1_end
    counts = _taxa_counts_str(species_list)
    
    s1_mid_josa = _resolve_leading_iga(s1_mid, counts)
        
    s1_end_base = S.end_field if is_field else S.end_lit

    prot_none = S.prot_none_field if is_field else S.prot_none_lit
    prot_part = f"{prot_str} {prot_n}종{s1_end}" if prot_n else f"{prot_none}"
    if disturb_n:
        if prot_n:
            prot_part = f"{prot_str} {prot_n}종, 생태계교란 생물은 {disturb_clause} {disturb_n}종{s1_end}"
        else:
            prot_part = f"{_prot_none_contrast(prot_none)}, 생태계교란 생물은 {disturb_clause} {disturb_n}종{s1_end}"

    survey_prefix = _survey_prefix(survey, rns)
    order_rows_tbl = _resolve_ref("order") or []
    dom_rows_tbl = _resolve_ref("dominance") or []
    life_rows_tbl = _resolve_ref("life") or []
    div_vals_tbl = _resolve_ref("diversity") or {}
    
    if is_field:
        if taxon in ("mammal", "herp"):
            if taxon == "herp" and split_herp:
                amp = [sp for sp in species_list if _get_herp_group(sp) == "양서류"]
                rep = [sp for sp in species_list if _get_herp_group(sp) == "파충류"]
                parts = []
                if amp: parts.append(f"양서류는 {_taxa_counts_str(amp)}")
                if rep: parts.append(f"파충류는 {_taxa_counts_str(rep)}")
                desc = ", ".join(parts)
                s1 = f"{survey_prefix} 결과 {desc} 등 총 {counts}{s1_mid} 법정보호종은 {prot_part}"
            else:
                s1 = f"{survey_prefix} 결과 {label}는 총 {counts}{s1_mid} 법정보호종은 {prot_part}"

            # s2: 목별 구성 문장
            grouped = defaultdict(list)
            if order_rows_tbl:
                for row in order_rows_tbl:
                    grouped[row["count"]].append((row["label"], row["pct"]))
            else:
                oc = _order_counts(species_list)
                ok_map = _get_ok_map(species_list)
                sorted_oc = sorted(oc.items(), key=lambda x: -x[1])
                total_sp = len(species_list)
                if force_norm:
                    pcts = _normalized_percentages([c for _, c in sorted_oc])
                else:
                    pcts = [c / total_sp * 100 if total_sp else 0 for _, c in sorted_oc]
                for (eng, cnt), pct in zip(sorted_oc, pcts):
                    grouped[cnt].append((ok_map.get(eng, eng), pct))
            grouped_sorted = sorted(grouped.items(), key=lambda x: -x[0])

            ord_first = getattr(S, "mammal_order_first", "로 가장 다양하게 나타났으며")
            ord_end   = getattr(S, "mammal_order_end",   "의 순으로 나타남")

            ord_parts = []
            for i, (cnt, items) in enumerate(grouped_sorted):
                names   = [x[0] for x in items]
                pct_val = items[0][1]
                name_str = "과 ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + "과 " + names[-1]
                if i == 0:
                    ord_parts.append(_resolve_iga(
                        f"{name_str}이(가) {cnt}종({_pct(pct_val)}){ord_first}", name_str))
                else:
                    suffix = "각각 " if len(names) > 1 else ""
                    ord_parts.append(_resolve_iga(
                        f"{name_str}이(가) {suffix}{cnt}종({_pct(pct_val)})", name_str))

            if len(ord_parts) > 1:
                s2 = f"분류군별 출현현황을 살펴보면 {ord_parts[0]}, 그 외 {', '.join(ord_parts[1:])}{ord_end}"
            elif ord_parts:
                name_str0 = grouped_sorted[0][1][0][0]
                cnt0 = grouped_sorted[0][0]
                pct0 = grouped_sorted[0][1][0][1]
                s2 = _resolve_iga(
                    f"분류군별 출현현황을 살펴보면 {name_str0}이(가) {cnt0}종({_pct(pct0)}){ord_end}", name_str0)
            else:
                s2 = ""

            return _finish_sentence("\n".join(filter(None, [s1, s2])), S.sentence_title)
            
        elif taxon == "bird":
            total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in species_list for r in rns if "합계" not in r and "종합" not in r)
            s1_mid_josa_indiv = _resolve_leading_iga(s1_mid, f"{total_ind:,}개체")
            s1 = f"{survey_prefix} 결과 {label}는 총 {counts} {total_ind:,}개체{s1_mid_josa_indiv} 법정보호종은 {prot_part}"
            
            if dom_rows_tbl:
                dom_rows = [(row["label"], row["count"], row["pct"]) for row in dom_rows_tbl]
                s2 = _dominance_sentence_from_table_rows(label, dom_rows, s1_end_base, SETTINGS.dom_pct)
            else:
                dom_rows = _dom_rows(species_list, rns, max(1, len(species_list)), min_pct=SETTINGS.dom_pct, force_norm=force_norm)
                s2 = _dominance_sentence(label, dom_rows, s1_end_base, SETTINGS.dom_pct)

            if life_rows_tbl:
                life_str = ", ".join(f"{row['label']} {_pct(row['pct'])}" for row in life_rows_tbl)
            else:
                life_str = _life_str(species_list, force_norm=force_norm)
            s3 = f"출현 {label}의 도래유형은 {life_str}{_josa(life_str, '으로로')} {s1_end_base}"
            
            div = _calc_div_indiv(species_list, rns)
            h_val = div_vals_tbl.get("H", div['H'])
            ri_val = div_vals_tbl.get("RI", div['RI'])
            e_val = div_vals_tbl.get("E", div['E'])
            s4 = f"출현 {label}의 군집지수 분석 결과, 종다양도지수는 {h_val:.2f}, 종풍부도지수는 {ri_val:.2f}, 균등도지수는 {e_val:.2f}{S.div_end}"
            
            return _finish_sentence("\n".join([s1, s2, s3, s4]), S.sentence_title)
            
        elif taxon == "insect":
            s1 = f"{survey_prefix} 결과 총 {counts}{s1_mid_josa} 이 중 법정보호종은 {prot_part}"
            
            grouped = defaultdict(list)
            if order_rows_tbl:
                for row in order_rows_tbl:
                    grouped[row["count"]].append((row["label"], row["pct"]))
            else:
                oc = _order_counts(species_list)
                ok_map = _get_ok_map(species_list)
                sorted_oc = list(oc.items())
                counts_arr = [cnt for eng, cnt in sorted_oc]
                total_sp = len(species_list)
                if force_norm:
                    pcts = _normalized_percentages(counts_arr)
                else:
                    pcts = [cnt / total_sp * 100 if total_sp else 0 for cnt in counts_arr]
                for (eng, cnt), pct in zip(sorted_oc, pcts):
                    grouped[cnt].append((ok_map.get(eng, eng), pct))
            grouped_sorted = sorted(grouped.items(), key=lambda x: -x[0])
            
            parts = []
            for i, (cnt, items) in enumerate(grouped_sorted):
                names = [x[0] for x in items]
                pct = items[0][1]
                name_str = "과 ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + "과 " + names[-1]
                if i == 0:
                    parts.append(_resolve_iga(f"{name_str}이(가) {cnt}종({_pct(pct)})로 가장 다양한 분포현황을 나타냈으며", name_str))
                else:
                    suffix = "각각 " if len(names) > 1 else ""
                    parts.append(_resolve_iga(f"{name_str}이(가) {suffix}{cnt}종({_pct(pct)})", name_str))
            
            if len(parts) > 1:
                _rest = ', '.join(parts[1:])
                s2 = f"조사된 {label}의 분류군별 출현현황을 살펴보면 {parts[0]}, 그 외 {_rest}{_josa(_rest, '으로로')} {s1_end_base}"
            elif parts:
                s2 = f"조사된 {label}의 분류군별 출현현황을 살펴보면 {parts[0].replace('나타냈으며', '나타내는 것으로 ' + s1_end_base)}"
            else:
                s2 = ""
            
            dom_rows = _dom_rows(species_list, rns, max(1, len(species_list)), min_pct=SETTINGS.dom_pct, force_norm=force_norm)
            s3 = _dominance_sentence(label, dom_rows, s1_end_base, SETTINGS.dom_pct)
                
            div = _calc_div_indiv(species_list, rns)
            h_val = div_vals_tbl.get("H", div['H'])
            ri_val = div_vals_tbl.get("RI", div['RI'])
            e_val = div_vals_tbl.get("E", div['E'])
            s4 = f"출현 {label}의 군집지수 분석 결과, 종다양도지수는 {h_val:.2f}, 종풍부도지수는 {ri_val:.2f}, 균등도지수는 {e_val:.2f}{S.div_end}"
            
            return _finish_sentence("\n".join(filter(None, [s1, s2, s3, s4])), S.sentence_title)

    else:
        result_prefix = lit_result_prefix(rns, survey_prefix, comma=True)
        if taxon == "herp" and split_herp:
            amp = [sp for sp in species_list if _get_herp_group(sp) == "양서류"]
            rep = [sp for sp in species_list if _get_herp_group(sp) == "파충류"]
            parts = []
            if amp: parts.append(f"양서류는 {_taxa_counts_str(amp)}")
            if rep: parts.append(f"파충류는 {_taxa_counts_str(rep)}")
            desc = ", ".join(parts) or f"{label}는 총 {counts}"
            s1 = f"{survey_prefix} 결과, {desc}{s1_mid_josa} 법정보호종은 {prot_part}"
        else:
            s1 = f"{survey_prefix} 결과, {label}는 총 {counts}{s1_mid_josa} 법정보호종은 {prot_part}"
        if result_prefix != f"{survey_prefix} 寃곌낵,":
            s1 = s1.replace(f"{survey_prefix} 寃곌낵,", result_prefix, 1)
        return _finish_sentence(s1, S.sentence_title)


# ══════════════════════════════════════════════════════════════════════════════
# 단일 패널 빌더
# ══════════════════════════════════════════════════════════════════════════════

def _replace_tbl(grp: QGroupBox, new_tbl: QTableWidget):
    """GroupBox 안의 첫 번째 테이블 위젯을 새 것으로 교체"""
    lay = grp.layout()
    if lay is None: return
    for i in range(lay.count()):
        item = lay.itemAt(i)
        if item and isinstance(item.widget(), QTableWidget):
            old = item.widget()
            lay.replaceWidget(old, new_tbl)
            old.setParent(None)  # 위젯 트리에서 즉시 제거 (findChildren 오탐 방지)
            old.deleteLater()
            return
    lay.addWidget(new_tbl)


def wrap_canvas(title, canvas, default_size=None):
    """캔버스를 CanvasGroupBox + ResizableCanvasFrame 으로 감싸는 공통 헬퍼."""
    # 그래프 프레임/스크롤/크기 조절 UI는 graph_widgets에서 일괄 관리한다.
    return _common_wrap_canvas(title, canvas, alignment=Qt.AlignCenter, default_size=default_size)


def _pie_side(radius, cfg):
    return _common_pie_side(radius, cfg)


def _pie_radius(side, cfg):
    offset = float((cfg or {}).get("pie_label_offset", getattr(SETTINGS, "pie_label_offset", 0.15)))
    r = (side - 360 - offset * 70) / 170
    return max(0.35, min(1.5, r))


def _bind_auto_max(grp, sld_w, sld_h):
    def _on_res(w, h):
        mw = max(300, w)
        mh = max(200, h)
        if mw > sld_w._sld.maximum():
            sld_w.setMaximum(mw)
        if mh > sld_h._sld.maximum():
            sld_h.setMaximum(mh)
        if not getattr(grp, "_init_done", False) and w > 150 and h > 150:
            grp._init_done = True
            sld_w.setValue(mw)
            sld_h.setValue(mh)
    grp.resized_sig.connect(_on_res)


def _bind_auto_max_pie(grp, sld_size):
    def _on_res(w, h):
        m = max(300, min(w, h))
        if m > sld_size._sld.maximum():
            sld_size.setMaximum(m)
        if not getattr(grp, "_init_done", False) and w > 150 and h > 150:
            grp._init_done = True
            sld_size.setValue(m)
    grp.resized_sig.connect(_on_res)


def _make_settings_graph(panel_w, cv_grp):
    """설정 패널 + 그래프를 좌우 QSplitter 로 구성."""
    return _common_make_settings_below_graph(panel_w, cv_grp)


def _field_panel(taxon, sheet, species_list, prot_sheet, rname,
                 chart_sig: list, sent_sig: list = None, rns_override=None,
                 total_rns=None, total_species=None, parent_window=None) -> QWidget:
    """현지조사 패널: 상단 요약 + 그래프 하위탭 + 문장"""
    w   = QWidget(); lay = QVBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)
    
    rns = list(rns_override) if rns_override is not None else (
        [rname] if rname != "전체" else [r for r in sheet.meta.round_names if "현지" in r and "합계" not in r and "종합" not in r]
    )

    def _make_triplet(tbl_grp, panel_w, cv_grp):
        cv_grp.setMinimumWidth(360)
        return _common_make_triplet(
            tbl_grp,
            panel_w,
            cv_grp,
            panel_min=220,
            panel_max=260,
            sizes=(1, 240, 860),
            table_content_width=True,
            settings_position="bottom",
        )

    def _make_tbl_grp(title, tbl, pct_col=None, cnt_col=None, on_normalize=None):
        g = QGroupBox(title)
        g._pct_col = pct_col
        g._cnt_col = cnt_col
        if pct_col is not None:
            tbl._pct_col = pct_col
            tbl._cnt_col = cnt_col
            if not hasattr(tbl, "_is_normalized"):
                tbl._is_normalized = False
        g.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l = QVBoxLayout(g)
        l.setContentsMargins(6, 12, 6, 6)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        hint_lbl = None
        if pct_col is not None:
            btn_norm = QPushButton("∑ 비율 보정")
            btn_norm.setFixedHeight(24)
            btn_norm.setStyleSheet(_OUTLINE_BTN_GREEN)
            btn_norm.setToolTip("비율 합계를 100.00으로 자동 보정하고 변경 내역을 표시합니다.")

            hint_lbl = QLabel("")
            hint_lbl.setStyleSheet(
                f"font-size: 11px; color: #B45309; {FF_KR}; "
                "background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 4px; "
                "padding: 3px 8px;"
            )
            hint_lbl.setWordWrap(True)
            hint_lbl.hide()

            def _do_norm():
                t = _get_tbl(g)
                if t:
                    hint = normalize_tbl_pct_col(t, pct_col, cnt_col=cnt_col, pct_formatter=_fmt)
                    g.is_normalized = True
                    t._is_normalized = True
                    t._pct_col = pct_col
                    t._cnt_col = cnt_col
                    if hint:
                        hint_lbl.setText(hint)
                        hint_lbl.show()
                    else:
                        hint_lbl.hide()
                    if hasattr(g, 'on_normalize') and g.on_normalize:
                        g.on_normalize()
                    elif on_normalize:
                        on_normalize()
            btn_norm.clicked.connect(_do_norm)
            btn_row.addWidget(btn_norm)

        btn_copy = QPushButton("📋 표 복사")
        btn_copy.setFixedHeight(24)
        btn_copy.setStyleSheet(_COPY_BTN_QSS)
        def _copy_current():
            t = _get_tbl(g)
            if t and hasattr(t, "copy_selection"):
                t.copy_selection()
                from ui_shared import apply_button_feedback
                apply_button_feedback(btn_copy)
        btn_copy.clicked.connect(_copy_current)
        btn_row.addWidget(btn_copy)

        l.addLayout(btn_row)
        if hint_lbl is not None:
            l.addWidget(hint_lbl)
        l.addWidget(tbl)
        return g

    grp_ord = _make_tbl_grp("목별 종수", _order_table(species_list), pct_col=3, cnt_col=2)

    # ── 정렬 버튼 (내림차순 / 분류군순) ──────────────────────────────
    _ord_sort_mode = ["taxa"]  # 클로저용 가변 컨테이너

    def _rebuild_ord_tbl():
        _replace_tbl(grp_ord, _order_table(species_list, _ord_sort_mode[0]))
        if getattr(grp_ord, "is_normalized", False):
            normalize_tbl_pct_col(_get_tbl(grp_ord), grp_ord._pct_col, cnt_col=grp_ord._cnt_col, pct_formatter=_fmt)
        pie.draw_pie(_extract_pie_data(grp_ord, 1, 3))

    btn_sort_desc = QPushButton("↓ 내림차순"); btn_sort_desc.setFixedHeight(24)
    btn_sort_desc.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa = QPushButton("☰ 분류군순"); btn_sort_taxa.setFixedHeight(24)
    btn_sort_taxa.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row = QHBoxLayout(); _sort_row.setContentsMargins(0, 0, 0, 2); _sort_row.setSpacing(4)
    _sort_row.addWidget(btn_sort_desc); _sort_row.addWidget(btn_sort_taxa); _sort_row.addStretch()
    grp_ord.layout().insertLayout(0, _sort_row)

    def _on_sort_desc():
        _ord_sort_mode[0] = "desc"; _rebuild_ord_tbl()
    def _on_sort_taxa():
        _ord_sort_mode[0] = "taxa"; _rebuild_ord_tbl()
    btn_sort_desc.clicked.connect(_on_sort_desc)
    btn_sort_taxa.clicked.connect(_on_sort_taxa)

    # Tab1: 목별 구성
    pie = PieCanvas()
    pie._setting_mode = "pie"
    apply_graph_default(parent_window, pie, "pie_order")
    pie.draw_pie(_extract_pie_data(grp_ord, 1, 3))
    pie._refresh_cb = lambda: pie.draw_pie(_extract_pie_data(grp_ord, 1, 3))
    grp_ord.on_normalize = pie._refresh_cb
    cv_grp_pie = wrap_canvas("목별 구성 비율", pie)
    
    panel_pie = _common_make_pie_settings_panel(pie, radius_label="그래프 크기")
    
    tab1_w  = QWidget(); t1l = QVBoxLayout(tab1_w); t1l.setContentsMargins(0,0,0,0)
    t1l.addWidget(_make_triplet(grp_ord, panel_pie, cv_grp_pie), stretch=1)
    
    # Tab2: 다양도지수
    grp_div = _make_tbl_grp("다양도지수", _div_table(species_list, rns))
    div_cv  = _Canvas(4, 4)
    div_cv._setting_mode = "diversity"
    apply_graph_default(parent_window, div_cv, "bar_diversity")
    _draw_diversity_bar(div_cv, grp_div)
    div_cv._refresh_cb = lambda: _draw_diversity_bar(div_cv, grp_div)
    cv_grp_div = wrap_canvas("다양도 지수", div_cv, default_size=(820, 480))
    
    panel_div = _common_make_bar_settings_panel(
        div_cv,
        mode="diversity",
        include_title=True,
        include_y_title=True,
    )
    _attach_title_to_cv(cv_grp_div, panel_div._title_controls)

    tab2_w  = QWidget(); t2l = QVBoxLayout(tab2_w); t2l.setContentsMargins(0,0,0,0)
    t2l.addWidget(_make_triplet(grp_div, panel_div, cv_grp_div), stretch=1)

    combo_cv = life_pie = grp_filtered = grp_life = None
    tab3_w = tab4_w = None
    if taxon == "bird":
        grp_filtered = _make_tbl_grp(
            f"우점도 ≥{SETTINGS.dom_pct}% 개체",
            _filtered_species_table(sheet, species_list, rname, SETTINGS.dom_pct, rns),
        )
        
        combo_cv = _Canvas(6, 5)
        combo_cv._setting_mode = "bird_combo"
        apply_graph_default(parent_window, combo_cv, "bar_dominance")
        _draw_bird_combo(combo_cv, grp_filtered)
        combo_cv._refresh_cb = lambda: _draw_bird_combo(combo_cv, grp_filtered)
        cv_grp_combo = wrap_canvas("개체수·우점도", combo_cv, default_size=(960, 520))

        grp_life = _make_tbl_grp("생활형", _life_table(species_list), pct_col=2, cnt_col=1)
        life_pie = PieCanvas()
        life_pie._setting_mode = "pie"
        apply_graph_default(parent_window, life_pie, "pie_life")
        life_pie.draw_pie(_extract_pie_data(grp_life, 0, 2))
        life_pie._refresh_cb = lambda: life_pie.draw_pie(_extract_pie_data(grp_life, 0, 2))
        def _on_life_norm():
            if life_pie._refresh_cb:
                life_pie._refresh_cb()
            _refresh_sent()
        grp_life.on_normalize = _on_life_norm
        cv_grp_life = wrap_canvas("생활형 비율", life_pie)
        
        
        def _on_panel_change():
            pct = float(combo_cv._cfg.get("dom_pct", SETTINGS.dom_pct))
            _replace_tbl(grp_filtered, _filtered_species_table(sheet, species_list, rname, pct, rns))
            grp_filtered.setTitle(f"우점도 ≥{pct:.1f}% 개체")
            combo_cv._refresh_cb()
            _refresh_sent()

        def _on_dom_norm():
            if combo_cv._refresh_cb: combo_cv._refresh_cb()
            _refresh_sent()

        panel_settings = _common_make_bar_settings_panel(
            combo_cv,
            mode="dominance",
            include_title=True,
            include_y_title=True,
            show_direction=True,
            show_legend=True,
            show_sort=True,
            show_dom_pct=True,
            on_change=_on_panel_change,
        )
        _attach_title_to_cv(cv_grp_combo, panel_settings._title_controls)
        grp_filtered.on_normalize = _on_dom_norm

        # tab3: 표 | 설정 | 그래프
        tab3_w = QWidget(); t3l = QVBoxLayout(tab3_w); t3l.setContentsMargins(0,0,0,0)
        t3l.addWidget(_make_triplet(grp_filtered, panel_settings, cv_grp_combo), stretch=1)

        panel_life = _common_make_pie_settings_panel(life_pie, radius_label="그래프 크기")
        
        def _on_life_norm():
            if life_pie._refresh_cb: life_pie._refresh_cb()
            _refresh_sent()
        grp_life.on_normalize = _on_life_norm

        tab4_w = QWidget(); t4l = QVBoxLayout(tab4_w); t4l.setContentsMargins(0,0,0,0)
        t4l.addWidget(_make_triplet(grp_life, panel_life, cv_grp_life), stretch=1)

    elif taxon == "insect":
        # ── 곤충: 개체수·우점도 탭 (조류와 동일 형식) ──────────────────
        grp_filtered = _make_tbl_grp(
            f"우점도 ≥{SETTINGS.dom_pct}% 개체",
            _filtered_species_table(sheet, species_list, rname, SETTINGS.dom_pct, rns),
        )

        combo_cv = _Canvas(6, 5)
        combo_cv._setting_mode = "bird_combo"
        apply_graph_default(parent_window, combo_cv, "bar_dominance")
        _draw_bird_combo(combo_cv, grp_filtered)
        combo_cv._refresh_cb = lambda: _draw_bird_combo(combo_cv, grp_filtered)
        cv_grp_combo = wrap_canvas("개체수·우점도", combo_cv, default_size=(960, 520))

        def _on_ins_change():
            pct = float(combo_cv._cfg.get("dom_pct", SETTINGS.dom_pct))
            _replace_tbl(grp_filtered, _filtered_species_table(sheet, species_list, rname, pct, rns))
            grp_filtered.setTitle(f"우점도 ≥{pct:.1f}% 개체")
            combo_cv._refresh_cb()
            _refresh_sent()

        panel_insect = _common_make_bar_settings_panel(
            combo_cv,
            mode="dominance",
            include_title=True,
            include_y_title=True,
            show_direction=True,
            show_legend=True,
            show_sort=True,
            show_dom_pct=True,
            on_change=_on_ins_change,
        )
        _attach_title_to_cv(cv_grp_combo, panel_insect._title_controls)
        def _on_ins_dom_norm():
            if combo_cv._refresh_cb: combo_cv._refresh_cb()
            _refresh_sent()
        grp_filtered.on_normalize = _on_ins_dom_norm

        tab3_w = QWidget(); t3l = QVBoxLayout(tab3_w); t3l.setContentsMargins(0,0,0,0)
        t3l.addWidget(_make_triplet(grp_filtered, panel_insect, cv_grp_combo), stretch=1)

    gtabs = QTabWidget(); gtabs.setDocumentMode(True)
    gtabs.setStyleSheet(_tab_qss(True))
    gtabs.addTab(tab1_w, "📊 목별 구성")
    gtabs.addTab(tab2_w, "📈 다양도지수")
    if tab3_w: gtabs.addTab(tab3_w, "🦗 개체수·우점도" if taxon == "insect" else "🦅 개체수·우점도")
    if tab4_w: gtabs.addTab(tab4_w, "🥧 생활형 비율")
    gtabs.setMinimumHeight(300)
    lay.addWidget(gtabs, stretch=1)

    _is_qual_only = sum(
        _int(sp.rounds.get(r, 0))
        for sp in species_list
        for r in rns
        if "합계" not in r and "종합" not in r
    ) == 0
    if _is_qual_only:
        qual_lbl = QLabel("※ 정성조사만 진행되었음")
        qual_lbl.setStyleSheet(f"{FF_KR}; font-size:12px; color:#D97706; padding:8px;")
        qual_lbl.setAlignment(Qt.AlignLeft)
        lay.addWidget(qual_lbl)

    grp_s = QGroupBox("문장")
    grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}")
    sv    = QVBoxLayout(grp_s); sv.setContentsMargins(8, 8, 8, 8); sv.setSpacing(6)
    
    chk_split_herp = None
    if taxon == "herp":
        chk_split_herp = QCheckBox("양서류, 파충류 분리 표기")
        chk_split_herp.setChecked(True)
        chk_split_herp.setStyleSheet(
            f"QCheckBox {{ color: {_ACCENT}; font-weight: bold; }}"
            + CHK_INDICATOR_QSS
        )
        
    txt   = QPlainTextEdit(); txt.setReadOnly(True); txt.setFixedHeight(110)
    txt.setStyleSheet(f"QPlainTextEdit{{background:{_BG};border:1.5px solid {_BORDER};border-radius:8px;{FF_KR};font-size:12px;}}")

    def _refresh():
        _replace_tbl(grp_ord, _order_table(species_list))
        if getattr(grp_ord, 'is_normalized', False):
            normalize_tbl_pct_col(_get_tbl(grp_ord), grp_ord._pct_col, cnt_col=grp_ord._cnt_col, pct_formatter=_fmt)
            
        _replace_tbl(grp_div, _div_table(species_list, rns))
        
        if grp_filtered:
            _replace_tbl(grp_filtered, _filtered_species_table(sheet, species_list, rname, SETTINGS.dom_pct, rns))
            if getattr(grp_filtered, 'is_normalized', False):
                normalize_tbl_pct_col(_get_tbl(grp_filtered), grp_filtered._pct_col, cnt_col=grp_filtered._cnt_col, pct_formatter=_fmt)
                
        if grp_life:
            _replace_tbl(grp_life, _life_table(species_list))
            if getattr(grp_life, 'is_normalized', False):
                normalize_tbl_pct_col(_get_tbl(grp_life), grp_life._pct_col, cnt_col=grp_life._cnt_col, pct_formatter=_fmt)
            
        pie.draw_pie(_extract_pie_data(grp_ord, 1, 3))
        if life_pie: life_pie.draw_pie(_extract_pie_data(grp_life, 0, 2))
        if combo_cv: _draw_bird_combo(combo_cv, grp_filtered)
        _draw_diversity_bar(div_cv, grp_div)
        
        _refresh_sent()
        
    def _refresh_sent():
        split = chk_split_herp.isChecked() if chk_split_herp else False
        # 표의 현재 보정 상태를 직접 읽어 문장에 반영
        force_norm = (
            getattr(grp_ord,  'is_normalized', False) or
            getattr(grp_filtered, 'is_normalized', False) or
            getattr(grp_life, 'is_normalized', False)
        )

        def _order_rows_from_tbl():
            tbl = _get_tbl(grp_ord)
            out = []
            if not tbl:
                return out
            for r in range(max(tbl.rowCount() - 1, 0)):
                label_it = tbl.item(r, 1)
                cnt_it = tbl.item(r, 2)
                pct_it = tbl.item(r, 3)
                if not label_it or not cnt_it or not pct_it:
                    continue
                try:
                    out.append({
                        "label": label_it.text().strip(),
                        "count": int(float(cnt_it.text().replace(",", "").strip() or 0)),
                        "pct": float(pct_it.text().replace("%", "").replace(",", "").strip() or 0),
                    })
                except ValueError:
                    continue
            return out

        def _dom_rows_from_tbl():
            tbl = _get_tbl(grp_filtered) if grp_filtered else None
            out = []
            if not tbl:
                return out
            for r in range(max(tbl.rowCount() - 1, 0)):
                label_it = tbl.item(r, 1)
                cnt_it = tbl.item(r, 2)
                pct_it = tbl.item(r, 3)
                if not label_it or not cnt_it or not pct_it:
                    continue
                try:
                    out.append({
                        "label": label_it.text().strip(),
                        "count": int(float(cnt_it.text().replace(",", "").strip() or 0)),
                        "pct": float(pct_it.text().replace("%", "").replace(",", "").strip() or 0),
                    })
                except ValueError:
                    continue
            return out

        def _life_rows_from_tbl():
            tbl = _get_tbl(grp_life) if grp_life else None
            out = []
            if not tbl:
                return out
            for r in range(max(tbl.rowCount() - 1, 0)):
                label_it = tbl.item(r, 0)
                pct_it = tbl.item(r, 2)
                if not label_it or not pct_it:
                    continue
                try:
                    out.append({
                        "label": label_it.text().strip(),
                        "pct": float(pct_it.text().replace("%", "").replace(",", "").strip() or 0),
                    })
                except ValueError:
                    continue
            return out

        def _div_vals_from_tbl():
            tbl = _get_tbl(grp_div)
            out = {}
            if not tbl:
                return out
            key_map = {"종다양도지수(H')": "H", "종풍부도지수(RI)": "RI", "균등도지수(EI)": "E"}
            for r in range(tbl.rowCount()):
                label_it = tbl.item(r, 0)
                val_it = tbl.item(r, 1)
                if not label_it or not val_it:
                    continue
                key = key_map.get(label_it.text().strip())
                if not key:
                    continue
                try:
                    out[key] = float(val_it.text().replace(",", "").strip() or 0)
                except ValueError:
                    continue
            return out

        group_sent = _build_sentence(
            taxon,
            species_list,
            rns,
            prot_sheet,
            "field",
            split,
            force_norm=force_norm,
            tbl_ref={
                "order": _order_rows_from_tbl,
                "dominance": _dom_rows_from_tbl,
                "life": _life_rows_from_tbl,
                "diversity": _div_vals_from_tbl,
            },
        )
        if total_rns and total_species:
            total_sent = _build_sentence(taxon, total_species, total_rns, prot_sheet, "field", split, force_norm=False)
            txt.setPlainText("\n".join(filter(None, [total_sent, group_sent])))
        else:
            txt.setPlainText(group_sent)
    txt_sent = _refresh_sent

    _refresh()

    def _on_ord_norm():
        if pie._refresh_cb: pie._refresh_cb()
        _refresh_sent()
    grp_ord.on_normalize = _on_ord_norm

    btn_copy = QPushButton("📋  복사"); btn_copy.setFixedHeight(30)
    btn_copy.setStyleSheet(_COPY_BTN_QSS)
    def _copy_sents():
        QApplication.clipboard().setText(txt.toPlainText())
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_copy)
    btn_copy.clicked.connect(_copy_sents)

    if chart_sig:
        chart_sig[0].connect(_refresh)
    if sent_sig:
        sent_sig[0].connect(_refresh_sent)

    br = QHBoxLayout()
    br.addWidget(btn_copy)
    if chk_split_herp:
        br.addSpacing(8)
        br.addWidget(chk_split_herp)
        chk_split_herp.stateChanged.connect(_refresh)
    br.addStretch()
    sv.addLayout(br); sv.addWidget(txt)
    lay.addWidget(grp_s)

    return w


def _lit_panel_all(taxon, lit_dict: dict, prot_sheet,
                   chart_sig: list, sent_sig: list, group_entries=None) -> QWidget:
    """문헌조사 통합 패널: 문헌별 요약표 + 기재 문장."""
    w = QWidget(); lay = QVBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

    ind_rounds = [r for r in lit_dict if r != "전체"]
    sp_all     = lit_dict.get("전체") or []
    group_entries = group_entries or []

    # 행 데이터: (레이블, species_list, is_total)
    def _row_data():
        rows = []
        if group_entries:
            for group_name, sp_group in group_entries:
                rows.append((group_name, sp_group, True))
            return rows
        if ind_rounds:
            for rk in ind_rounds:
                rows.append((_rn(rk), lit_dict[rk], False))
            if sp_all:
                rows.append(("전체", sp_all, True))
        elif sp_all:
            rows.append(("문헌조사", sp_all, False))
        return rows

    # ── 1) 문헌별 요약표 ──────────────────────────────────────────────
    grp_sum = QGroupBox("문헌별 요약")
    st = QVBoxLayout(grp_sum); st.setContentsMargins(6, 12, 6, 6); st.setSpacing(4)

    # 헤더: 구분 | 분류군 현황 | 법정보호종
    tbl_sum = _make_tbl(["구분", "분류군 현황", "법정보호종"])
    tbl_sum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _fill_sum_tbl():
        rows = _row_data()
        tbl_sum.setRowCount(max(len(rows), 1))
        for ri, (lbl, sp_list, is_total) in enumerate(rows):
            prot_n, prot_clause = _prot_list_graded(taxon, prot_sheet, sp_list)
            tbl_sum.setItem(ri, 0, _item(lbl,                         Qt.AlignLeft | Qt.AlignVCenter))
            tbl_sum.setItem(ri, 1, _item(_taxa_counts_str(sp_list)))
            tbl_sum.setItem(ri, 2, _item(prot_clause if prot_n else "-", Qt.AlignLeft | Qt.AlignVCenter))
            if is_total:
                bold_row(tbl_sum, ri, _BG)
        _tbl_auto_height(tbl_sum)

    _fill_sum_tbl()
    _auto_fit_table(tbl_sum)
    st.addWidget(make_copy_button(tbl_sum))
    st.addWidget(tbl_sum)
    lay.addWidget(grp_sum, 0)

    # ── 2) 문헌조사 기재 문장 ────────────────────────────────────────
    _TXT_QSS = (
        f"QPlainTextEdit{{background:{_BG};border:1.5px solid {_BORDER};"
        f"border-radius:8px;{FF_KR};font-size:12px;padding:6px;}}"
    )
    chk_split_herp = None
    if taxon == "herp":
        chk_split_herp = QCheckBox("양서류, 파충류 분리 표기")
        chk_split_herp.setChecked(True)
        chk_split_herp.setStyleSheet(
            f"QCheckBox {{ color: {_ACCENT}; font-weight: bold; }}"
            + CHK_INDICATOR_QSS
        )

    def _lit_count_subject(sp_list):
        label = TAXON_LABEL.get(taxon, taxon)
        if taxon == "herp" and chk_split_herp and chk_split_herp.isChecked():
            amp = [sp for sp in sp_list if _get_herp_group(sp) == "양서류"]
            rep = [sp for sp in sp_list if _get_herp_group(sp) == "파충류"]
            parts = []
            if amp: parts.append(f"양서류는 {_taxa_counts_str(amp)}")
            if rep: parts.append(f"파충류는 {_taxa_counts_str(rep)}")
            return ", ".join(parts) or f"{label}는 {_taxa_counts_str(sp_list)}"
        return f"{label}는 {_taxa_counts_str(sp_list)}"

    def _build_lit_lines():
        S = SETTINGS
        lines = []
        split = chk_split_herp.isChecked() if chk_split_herp else False
        if sp_all and ind_rounds:
            lines.append(_build_sentence(taxon, sp_all, ind_rounds, prot_sheet, "lit", split_herp=split))
            
        for lbl, sp_list, _ in _row_data():
            if lbl == "전체":
                continue
            counts   = _taxa_counts_str(sp_list)
            prot_n, prot_clause = _prot_list_graded(taxon, prot_sheet, sp_list)
            disturb_n, disturb_clause = _ecosystem_disturber_list(prot_sheet, sp_list)
            prot_part = (f"{prot_clause} {prot_n}종{S.lit_s1_end}"
                         if prot_n else f"{S.prot_none_lit}")
            if disturb_n:
                if prot_n:
                    prot_part = f"{prot_clause} {prot_n}종, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
                else:
                    prot_part = f"{_prot_none_contrast(S.prot_none_lit)}, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
            if getattr(S, "field_intro_mode", "auto") == "fixed":
                prefix = "문헌조사 결과,"
            else:
                prefix = lit_result_prefix([lbl], _round_survey_label(lbl), comma=True)
            subject = _lit_count_subject(sp_list)
            mid = _resolve_leading_iga(S.lit_s1_mid, counts)
            lines.append(f"{prefix} {subject}{mid} 법정보호종은 {prot_part}")
        return _finish_sentence("\n".join(lines), S.sentence_title)

    grp_s = QGroupBox("문헌조사 기재 문장")
    grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}")
    sv    = QVBoxLayout(grp_s); sv.setContentsMargins(8, 8, 8, 8); sv.setSpacing(6)
    n_lit = max(len(group_entries) + len(ind_rounds) + (1 if sp_all and ind_rounds else 0), 1)
    txt   = QPlainTextEdit(); txt.setReadOnly(True)
    txt.setMinimumHeight(60); txt.setFixedHeight(min(n_lit * 42 + 20, 320))
    txt.setStyleSheet(_TXT_QSS)
    txt.setPlainText(_build_lit_lines())
    txt._sent_refresh_fn = lambda: txt.setPlainText(_build_lit_lines())
    if chk_split_herp:
        chk_split_herp.stateChanged.connect(txt._sent_refresh_fn)

    btn_copy = QPushButton("📋  복사"); btn_copy.setFixedHeight(30)
    btn_copy.setStyleSheet(_COPY_BTN_QSS)
    def _copy_lit_sents():
        QApplication.clipboard().setText(txt.toPlainText())
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_copy)
    btn_copy.clicked.connect(_copy_lit_sents)

    def _refresh_all():
        _fill_sum_tbl()
        txt.setPlainText(_build_lit_lines())

    if sent_sig:
        sent_sig[0].connect(_refresh_all)
    if chart_sig:
        chart_sig[0].connect(_refresh_all)

    br = QHBoxLayout(); br.addWidget(btn_copy)
    if chk_split_herp:
        br.addSpacing(8)
        br.addWidget(chk_split_herp)
    br.addStretch()
    sv.addLayout(br); sv.addWidget(txt)
    lay.addWidget(grp_s, 0)

    lay.addStretch()
    return w


def _field_panel_section(taxon, sheet, species_list, prot_sheet, rname,
                         chart_sig: list, sent_sig: list, keep_text: str, rns_override=None, parent_window=None) -> QWidget:
    panel = _field_panel(taxon, sheet, species_list, prot_sheet,
                         rname, chart_sig, sent_sig, rns_override=rns_override, parent_window=parent_window)
    tabs = panel.findChildren(QTabWidget)
    target = next(
        (t for t in tabs if any(keep_text in t.tabText(i) for i in range(t.count()))),
        None
    )
    if target:
        for i in range(target.count() - 1, -1, -1):
            if keep_text not in target.tabText(i):
                target.removeTab(i)
    return panel


def _field_section_round_tabs(taxon, sheet, fld_dict: dict, prot_sheet, keep_text: str,
                              chart_sig: list, sent_sig: list, parent_window=None) -> QTabWidget:
    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    tabs.setStyleSheet(_tab_qss(False))
    for rname, sp_list in fld_dict.items():
        if not sp_list:
            continue
        panel = _field_panel_section(taxon, sheet, sp_list, prot_sheet,
                                     rname, chart_sig, sent_sig, keep_text, parent_window=parent_window)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(panel)
        tabs.addTab(sc, _rn(rname))
    return tabs


def _field_round_full_panel(taxon, sheet, display_name, sp_list, rns, rname, site_panel,
                            prot_sheet, chart_sig: list, sent_sig: list, parent_window=None) -> QTabWidget:
    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    tabs.setStyleSheet(_tab_qss(False))

    sc_site = QScrollArea()
    sc_site.setWidgetResizable(True)
    sc_site.setFrameShape(QFrame.NoFrame)
    sc_site.setWidget(site_panel)
    tabs.addTab(sc_site, "입지현황")

    for title, keep_text in (("목별구성", "목별 구성"), ("다양도지수", "다양도지수")):
        panel = _field_panel_section(taxon, sheet, sp_list, prot_sheet,
                                     rname, chart_sig, sent_sig, keep_text, rns_override=rns, parent_window=parent_window)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(panel)
        tabs.addTab(sc, title)
    return tabs


class _RoundSiteCoordinator:
    def __init__(self, parent_window=None):
        self._parent_window = parent_window
        self._loc_items = list(_DEFAULT_LOCS)
        self._trace_map = dict(TRACE_MAP)
        self._syncing = False
        self._all_panel = None
        self._all_rows = {}
        self._sub_panels = []
        self._sub_rows = defaultdict(list)

    def _rebuild_all(self, sp: str, trace: str):
        if self._syncing or self._all_panel is None:
            return
        key = (sp, trace)
        all_row = self._all_rows.get(key)
        if all_row is None:
            return
        merged = {}
        for panel, r in self._sub_rows.get(key, []):
            for loc in [x.strip() for x in panel.get_loc_text(r).split(",") if x.strip()]:
                merged.setdefault(loc, True)
        self._all_panel.set_loc(all_row, list(merged.keys()))
        self._all_panel._make_sentence()

    def _edit_locs(self):
        dlg = LocEditorDialog(self._loc_items, self._all_panel)
        if dlg.exec() == QDialog.Accepted:
            self._loc_items = dlg.get()
            self._rebuild_panels()

    def _edit_traces(self):
        dlg = TraceEditorDialog(self._trace_map, self._all_panel)
        if dlg.exec() == QDialog.Accepted:
            self._trace_map = dlg.get()
            for p in self._sub_panels + ([self._all_panel] if self._all_panel else []):
                p._make_sentence()

    def _rebuild_panels(self):
        states = {}
        for panel in self._sub_panels:
            for r in range(panel.tbl.rowCount()):
                sp = (panel.tbl.item(r, 0) or QTableWidgetItem()).text()
                tr = (panel.tbl.item(r, 1) or QTableWidgetItem()).text()
                states[(sp, tr, id(panel), r)] = panel.get_loc_text(r)
        for panel in self._sub_panels:
            panel._loc_items = self._loc_items
            for r in range(panel.tbl.rowCount()):
                sp = (panel.tbl.item(r, 0) or QTableWidgetItem()).text()
                tr = (panel.tbl.item(r, 1) or QTableWidgetItem()).text()
                if tr in ("H", "C"):
                    label_text = "탐문조사 (별도 처리)" if tr == "H" else "무인센서카메라 (별도 처리)"
                    lbl = QLabel(label_text)
                    lbl.setAlignment(Qt.AlignCenter)
                    lbl.setStyleSheet(f"color:{_SUB};font-size:11px;{FF_KR};font-style:italic;")
                    panel.tbl.setCellWidget(r, 2, lbl)
                else:
                    prev = set(x.strip() for x in
                               states.get((sp, tr, id(panel), r), "").split(",") if x.strip())
                    panel.tbl.setCellWidget(r, 2, panel._build_loc_widget(r, tr, prev))
        for key in self._all_rows:
            self._rebuild_all(key[0], key[1])


def _site_rows_for_rns(sheet, rns):
    rows = []
    for sp in sheet.species:
        for rname in rns:
            val = sp.rounds.get(rname)
            if not val or str(val).strip() in ("", "None", "-", "◎"):
                continue
            for code in _split_trace(str(val).strip()):
                rows.append((sp.kor_name, code))
    return rows


def _build_round_site_panels(sheet, display_name, taxon, fld_dict, all_rns, prot_sheet, parent_window, rns_by_label=None):
    coord = _RoundSiteCoordinator(parent_window)
    panel_by_rname = {}
    rns_by_label = rns_by_label or {}

    keys_order = []
    seen = set()
    sub_specs = []
    for rname, sp_list in fld_dict.items():
        if rname == "전체" or not sp_list:
            continue
        rns = rns_by_label.get(rname, [rname])
        rows = _site_rows_for_rns(sheet, rns)
        sub_specs.append((rname, rows, sp_list))
        for key in rows:
            if key not in seen:
                seen.add(key)
                keys_order.append(key)

    all_sp = fld_dict.get("전체") or [
        sp for sp in sheet.species
        if any(_has_present(sp.rounds.get(r)) for r in all_rns)
    ]
    all_panel = _SitePanel(keys_order, coord._loc_items, display_name,
                           taxon, all_sp, all_rns, prot_sheet,
                           parent_page=coord, is_all=True)
    coord._all_panel = all_panel
    panel_by_rname["전체"] = all_panel
    for r, key in enumerate(keys_order):
        coord._all_rows[key] = r

    for rname, rows, sp_list in sub_specs:
        panel = _SitePanel(rows, coord._loc_items, display_name,
                           taxon, sp_list, [rname], prot_sheet,
                           parent_page=coord, is_all=False)
        coord._sub_panels.append(panel)
        panel_by_rname[rname] = panel
        for r, key in enumerate(rows):
            coord._sub_rows[key].append((panel, r))

    if parent_window and hasattr(parent_window, "sig_sent_settings"):
        def _refresh_site_sentences():
            for p in coord._sub_panels + ([coord._all_panel] if coord._all_panel else []):
                p._make_sentence()
        parent_window.sig_sent_settings.connect(_refresh_site_sentences)

    return panel_by_rname


# ══════════════════════════════════════════════════════════════════════════════
# 입지별 출현현황 (포유류 / 양서파충류)
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_LOCS = ["산림","농경지","초지","수변","하천","주거지","공원","도로변"]

_SITE_SENT_DEFAULTS = {
    "s1_prefix": "조사된 {분류군}의 입지별 출현현황을 정리하면, 조사지역의 ",
    "s2_prefix": "지역주민의 탐문조사에서는 ",
    "s2_core_A": "현지조사시 확인된 {현지확인}의 서식이 ",
    "s2_core_B": "{탐문}의 서식이 ",
    "s2_core_C": "현지조사시 확인된 {현지확인} 이외에 {탐문}의 서식이 ",
}

class SiteSentSettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        flags = self.windowFlags()
        flags = (flags | Qt.WindowMinMaxButtonsHint) & ~Qt.MSWindowsFixedSizeDialogHint
        self.setWindowFlags(flags)
        self.setWindowTitle("입지별 출현현황 템플릿 설정")
        self.setStyleSheet(_DIALOG_QSS)
        self.resize(840, 700)
        self.setMinimumSize(760, 620)
        self.setSizeGripEnabled(True)
        lay  = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)

        def _fit_edit_width(edit: QLineEdit):
            text = edit.text() or " "
            width = edit.fontMetrics().horizontalAdvance(text) + 48
            edit.setFixedWidth(max(48, min(1100, width)))

        def _make_edit(text: str) -> QLineEdit:
            e = QLineEdit(text)
            _fit_edit_width(e)
            e.setCursorPosition(0)
            e.textChanged.connect(lambda _t, _e=e: _fit_edit_width(_e))
            return e
        
        def _row(label_text, key, has_var=None):
            val = cfg.get(key, _SITE_SENT_DEFAULTS[key])
            if has_var:
                parts = val.split(has_var)
                le = _make_edit(parts[0])
                lbl = QLabel(has_var)
                lbl.setStyleSheet(f"color:{_ACCENT}; font-weight:bold;")
                le2 = _make_edit(parts[1] if len(parts) > 1 else "")
                row_w = QWidget()
                h = QHBoxLayout(row_w)
                h.setContentsMargins(0,0,0,0)
                h.setSpacing(4)
                h.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if key in ["s2_core_A", "s2_core_B", "s2_core_C"]:
                    import re
                    pattern = r'(\{.*?\})'
                    split_parts = re.split(pattern, val)
                    edit_widgets = []
                    for p in split_parts:
                        if p.startswith('{') and p.endswith('}'):
                            l = QLabel(p)
                            l.setStyleSheet(f"color:{_ACCENT}; font-weight:bold;")
                            h.addWidget(l)
                        else:
                            e = _make_edit(p)
                            edit_widgets.append(e)
                            h.addWidget(e)
                    h.addStretch(1)
                    form.addRow(label_text, row_w)
                    return edit_widgets
                else:
                    h.addWidget(le); h.addWidget(lbl); h.addWidget(le2)
                    h.addStretch(1)
                    form.addRow(label_text, row_w)
                    return [le, le2]
            else:
                le = _make_edit(val)
                form.addRow(label_text, le)
                return [le]

        self.w_s1p = _row("출현현황 앞부분:", "s1_prefix", "{분류군}")
        self.w_s2p = _row("탐문조사 앞부분:", "s2_prefix")
        self.w_cA  = _row("현지확인 있을 때:", "s2_core_A", "{현지확인}")
        self.w_cB  = _row("탐문만 있을 때:", "s2_core_B", "{탐문}")
        self.w_cC  = _row("둘 다 있을 때:", "s2_core_C", "{현지확인}") 

        hint = QLabel("파란색 변수는 고정값입니다.\n※ 문장 종결 어미는 [기본 문장 어미 설정]의 값을 따릅니다.")
        hint.setStyleSheet(f"{FF_KR};color:{_SUB};font-weight:700;font-size:12px;")
        lay.addLayout(form); lay.addWidget(hint)
        btns    = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_def = QPushButton("기본값"); btns.addButton(btn_def, QDialogButtonBox.ResetRole)
        btn_def.clicked.connect(self._reset)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._fit_dialog_size()

    def _fit_dialog_size(self):
        hint = self.sizeHint()
        screen = QApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            max_w = max(500, int(ag.width() * 0.92))
            max_h = max(320, int(ag.height() * 0.88))
        else:
            max_w, max_h = 800, 900

        target_w = min(max_w, max(760, hint.width() + 40))
        target_h = min(max_h, max(620, hint.height() + 30))
        self.resize(target_w, target_h)

    def _reset(self):
        def _set_row(w_list, key):
            val = _SITE_SENT_DEFAULTS[key]
            import re
            parts = [p for p in re.split(r'(\{.*?\})', val) if not (p.startswith('{') and p.endswith('}'))]
            for i, w in enumerate(w_list):
                if i < len(parts):
                    w.setText(parts[i])
                    w.setCursorPosition(0)
                    
        _set_row(self.w_s1p, "s1_prefix")
        _set_row(self.w_s2p, "s2_prefix")
        _set_row(self.w_cA, "s2_core_A")
        _set_row(self.w_cB, "s2_core_B")
        _set_row(self.w_cC, "s2_core_C")

    def get(self) -> dict:
        return {
            "s1_prefix": self.w_s1p[0].text() + "{분류군}" + (self.w_s1p[1].text() if len(self.w_s1p)>1 else ""),
            "s2_prefix": self.w_s2p[0].text(),
            "s2_core_A": self.w_cA[0].text() + "{현지확인}" + (self.w_cA[1].text() if len(self.w_cA)>1 else ""),
            "s2_core_B": self.w_cB[0].text() + "{탐문}" + (self.w_cB[1].text() if len(self.w_cB)>1 else ""),
            "s2_core_C": self.w_cC[0].text() + "{현지확인}" + (self.w_cC[1].text() if len(self.w_cC)>1 else "") + "{탐문}" + (self.w_cC[2].text() if len(self.w_cC)>2 else ""),
        }
def _split_trace(s: str) -> list[str]:
    """대소문자를 구분하여 코드를 분리합니다 (예: H=탐문, h=털)."""
    if not s: return []
    return [t.strip() for t in s.replace("/",",").split(",") if t.strip()]

def _fmt_trace(codes: set, trace_map: dict | None = None) -> str:
    tm = trace_map if trace_map is not None else TRACE_MAP
    out = [tm[c] for c in tm if c in codes]
    return ", ".join(out)


class LocEditorDialog(QDialog):
    def __init__(self, locs: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("입지 목록 편집")
        self.resize(400, 420)
        self.setStyleSheet(_DIALOG_QSS)
        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QInputDialog
        lay = QVBoxLayout(self)
        self.lw = QListWidget()
        for x in locs: QListWidgetItem(x, self.lw)
        lay.addWidget(self.lw)
        br = QHBoxLayout()
        for txt, fn in [("추가",self._add),("수정",self._edit),("삭제",self._del)]:
            b = QPushButton(txt); b.clicked.connect(fn); br.addWidget(b)
        br.addStretch(); lay.addLayout(br)
        btns    = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_def = QPushButton("기본값"); btns.addButton(btn_def, QDialogButtonBox.ResetRole)
        btn_def.clicked.connect(lambda: (self.lw.clear(),
                                         [QListWidgetItem(x, self.lw) for x in _DEFAULT_LOCS]))
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._QInputDialog = QInputDialog
        self._QListWidgetItem = QListWidgetItem

    def _add(self):
        t, ok = self._QInputDialog.getText(self, "추가", "입지명")
        if ok and t.strip(): self._QListWidgetItem(t.strip(), self.lw)
    def _edit(self):
        item = self.lw.currentItem()
        if not item: return
        t, ok = self._QInputDialog.getText(self, "수정", "입지명", text=item.text())
        if ok and t.strip(): item.setText(t.strip())
    def _del(self):
        r = self.lw.currentRow()
        if r >= 0: self.lw.takeItem(r)
    def get(self) -> list:
        return [self.lw.item(i).text().strip() for i in range(self.lw.count())
                if self.lw.item(i).text().strip()]


class TraceEditorDialog(QDialog):
    """흔적 코드 ↔ 이름 매핑 편집 다이얼로그."""
    def __init__(self, trace_map: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("흔적 목록 편집")
        self.resize(420, 400)
        self.setStyleSheet(_DIALOG_QSS)
        from PySide6.QtWidgets import QListWidgetItem, QInputDialog
        self._QInputDialog = QInputDialog
        self._QListWidgetItem = QListWidgetItem

        lay = QVBoxLayout(self)
        hint = QLabel("코드와 표시 이름을 편집합니다 (대소문자 구분: H=탐문, h=털 등).")
        hint.setStyleSheet(f"{FF_KR};font-size:12px;color:{_SUB};")
        lay.addWidget(hint)

        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["코드", "이름"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(40)
        self.tbl.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        for code, name in trace_map.items():
            self._append_row(code, name)
        lay.addWidget(self.tbl)

        br = QHBoxLayout()
        for txt, fn in [("추가", self._add), ("삭제", self._del)]:
            b = QPushButton(txt); b.clicked.connect(fn); br.addWidget(b)
        btn_reset = QPushButton("기본값"); btn_reset.clicked.connect(self._reset)
        br.addStretch(); br.addWidget(btn_reset)
        lay.addLayout(br)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _append_row(self, code="", name=""):
        r = self.tbl.rowCount(); self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(code))
        self.tbl.setItem(r, 1, QTableWidgetItem(name))

    def _add(self):
        d1 = self._QInputDialog(self)
        d1.setWindowTitle("추가")
        d1.setLabelText("코드 (단일 영문자)")
        d1.resize(300, 150)
        d1.setStyleSheet(_DIALOG_QSS)
        if d1.exec() != QDialog.Accepted or not d1.textValue().strip(): return
        code = d1.textValue()
        
        d2 = self._QInputDialog(self)
        d2.setWindowTitle("추가")
        d2.setLabelText("표시 이름")
        d2.resize(300, 150)
        d2.setStyleSheet(_DIALOG_QSS)
        if d2.exec() == QDialog.Accepted and d2.textValue().strip():
            self._append_row(code.strip(), d2.textValue().strip())

    def _del(self):
        rows = sorted({idx.row() for idx in self.tbl.selectedIndexes()}, reverse=True)
        for r in rows: self.tbl.removeRow(r)

    def _reset(self):
        self.tbl.setRowCount(0)
        for code, name in TRACE_MAP.items():
            self._append_row(code, name)

    def get(self) -> dict:
        result = {}
        for r in range(self.tbl.rowCount()):
            code = (self.tbl.item(r, 0) or QTableWidgetItem()).text().strip()  # 대소문자 유지
            name = (self.tbl.item(r, 1) or QTableWidgetItem()).text().strip()
            if code and name:
                result[code] = name
        return result


class _SitePanel(QWidget):
    def __init__(self, rows, loc_items, display_name, taxon, species_list, rns, prot_sheet,
                 parent_page=None, is_all=False):
        super().__init__()
        self.display_name = display_name
        self._loc_items   = loc_items
        self._is_all      = is_all
        self._parent_page = parent_page
        self._syncing     = False
        self.taxon        = taxon
        self.species_list = species_list
        self.rns          = rns
        self.prot_sheet   = prot_sheet

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4,4,4,4); layout.setSpacing(6)

        self.tbl = CopyableTableWidget(len(rows), 3)
        self.tbl.setHorizontalHeaderLabels(["국명","흔적","입지"])
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectItems)
        self.tbl.setSelectionMode(QTableWidget.ExtendedSelection)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self._row_keys = []

        for r, (sp, trace) in enumerate(rows):
            for ci, txt in enumerate([sp, trace, ""]):
                it = QTableWidgetItem(txt)
                it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.tbl.setItem(r, ci, it)
            if not is_all:
                if trace == "H":  # 탐문: 입지 선택 비활성화
                    from PySide6.QtWidgets import QLabel
                    from PySide6.QtCore import Qt as _Qt
                    lbl = QLabel("탐문조사 (별도 처리)")
                    lbl.setAlignment(_Qt.AlignCenter)
                    lbl.setStyleSheet(f"color:{_SUB};font-size:11px;{FF_KR};font-style:italic;")
                    self.tbl.setCellWidget(r, 2, lbl)
                elif trace == "C":  # 무인센서카메라: 입지 선택 비활성화
                    from PySide6.QtWidgets import QLabel
                    from PySide6.QtCore import Qt as _Qt
                    lbl = QLabel("무인센서카메라 (별도 처리)")
                    lbl.setAlignment(_Qt.AlignCenter)
                    lbl.setStyleSheet(f"color:{_SUB};font-size:11px;{FF_KR};font-style:italic;")
                    self.tbl.setCellWidget(r, 2, lbl)
                else:
                    w = self._build_loc_widget(r, trace, set())  # 기본: 체크 없음
                    self.tbl.setCellWidget(r, 2, w)
                self.tbl.setRowHeight(r, 36)
            self._row_keys.append((sp, trace))

        tbl_row = QHBoxLayout()

        btn_loc = QPushButton("⚙ 입지 편집"); btn_loc.setFixedHeight(24)
        btn_loc.setStyleSheet(_OUTLINE_BTN_GREEN)
        if self._parent_page:
            btn_loc.clicked.connect(self._parent_page._edit_locs)
        tbl_row.addWidget(btn_loc)

        btn_trace = QPushButton("✏ 흔적 편집"); btn_trace.setFixedHeight(24)
        btn_trace.setStyleSheet(_OUTLINE_BTN_ORANGE)
        if self._parent_page:
            btn_trace.clicked.connect(self._parent_page._edit_traces)
        tbl_row.addWidget(btn_trace)

        btn_sent_cfg = QPushButton("⚙ 문장 템플릿"); btn_sent_cfg.setFixedHeight(24)
        btn_sent_cfg.setStyleSheet(_OUTLINE_BTN_GREEN)
        def _open_sent_cfg():
            # global dictionary to local dictionary format
            cfg = {
                "s1_prefix": SETTINGS.site_s1_prefix,
                "s2_prefix": SETTINGS.site_s2_prefix,
                "s2_core_A": SETTINGS.site_s2_core_A,
                "s2_core_B": SETTINGS.site_s2_core_B,
                "s2_core_C": SETTINGS.site_s2_core_C,
            }
            dlg = SiteSentSettingsDialog(cfg, self)
            if dlg.exec() == QDialog.Accepted:
                new_cfg = dlg.get()
                SETTINGS.site_s1_prefix = new_cfg.get("s1_prefix", "")
                SETTINGS.site_s2_prefix = new_cfg.get("s2_prefix", "")
                SETTINGS.site_s2_core_A = new_cfg.get("s2_core_A", "")
                SETTINGS.site_s2_core_B = new_cfg.get("s2_core_B", "")
                SETTINGS.site_s2_core_C = new_cfg.get("s2_core_C", "")
                # refresh all site panels
                if self._parent_page and self._parent_page._parent_window:
                    if hasattr(self._parent_page._parent_window, "sig_sent_settings"):
                        self._parent_page._parent_window.sig_sent_settings.emit()
                else:
                    self._make_sentence()
        btn_sent_cfg.clicked.connect(_open_sent_cfg)
        tbl_row.addWidget(btn_sent_cfg)

        tbl_row.addStretch()

        btn_copy_tbl = QPushButton("📋 표 복사"); btn_copy_tbl.setFixedHeight(24)
        btn_copy_tbl.setStyleSheet(_COPY_BTN_QSS)
        def _do_copy_tbl():
            self.tbl.copy_selection()
            from ui_shared import apply_button_feedback
            apply_button_feedback(btn_copy_tbl)
        btn_copy_tbl.clicked.connect(_do_copy_tbl)
        tbl_row.addWidget(btn_copy_tbl)

        layout.addLayout(tbl_row)
        layout.addWidget(self.tbl, stretch=3)

        grp_s = QGroupBox("문장")
        sv    = QVBoxLayout(grp_s); sv.setContentsMargins(8,8,8,8); sv.setSpacing(4)
        self.txt = QPlainTextEdit(); self.txt.setReadOnly(True); self.txt.setFixedHeight(90)
        self.txt.setStyleSheet(
            f"QPlainTextEdit{{background:{_BG};border:1.5px solid {_BORDER};border-radius:8px;{FF_KR};font-size:12px;padding:6px;}}"
        )
        btn_row  = QHBoxLayout()
        btn_gen  = QPushButton("🖊  문장 생성"); btn_gen.setFixedHeight(28)
        btn_gen.setStyleSheet(_OUTLINE_BTN_GREEN)
        btn_copy = QPushButton("📋  복사");       btn_copy.setFixedHeight(28)
        btn_copy.setStyleSheet(_COPY_BTN_QSS)
        btn_gen.clicked.connect(self._make_sentence)
        def _do_copy_sents():
            QApplication.clipboard().setText(self.txt.toPlainText())
            from ui_shared import apply_button_feedback
            apply_button_feedback(btn_copy)
        btn_copy.clicked.connect(_do_copy_sents)
        btn_row.addWidget(btn_gen); btn_row.addWidget(btn_copy)
        
        if self.taxon == "herp":
            self.chk_split_herp = QCheckBox("양서류, 파충류 분리 표기")
            self.chk_split_herp.setChecked(True)
            self.chk_split_herp.setStyleSheet(f"QCheckBox {{ color: {_ACCENT}; font-weight: bold; }}")
            self.chk_split_herp.stateChanged.connect(lambda: self._make_sentence())
            btn_row.addSpacing(16)
            btn_row.addWidget(self.chk_split_herp)
            
        btn_row.addStretch()
        sv.addLayout(btn_row); sv.addWidget(self.txt)
        layout.addWidget(grp_s)
        self._make_sentence()

    def _build_loc_widget(self, row, trace_code, selected: set) -> QWidget:
        btn_border = "#94A3B8"
        btn_hover_border = "#64748B"
        btn_soft_blue = "#3B5BDB"
        btn_checked = "#4F6FD8"
        btn_checked_dark = "#3F5FBF"
        w = QWidget()
        w.setObjectName("siteLocCellWidget")
        w.setAutoFillBackground(False)
        w.setAttribute(Qt.WA_TranslucentBackground, True)
        w.setStyleSheet("#siteLocCellWidget{background:transparent;border:none;}")
        h = QHBoxLayout(w); h.setContentsMargins(2,2,2,2); h.setSpacing(4)
        buttons = []
        def _update():
            if self._syncing: return
            loc_item = self.tbl.item(row, 2)
            if loc_item: loc_item.setText("")
            sp = self.tbl.item(row, 0)
            if sp and self._parent_page:
                self._parent_page._rebuild_all(sp.text(), trace_code)
        for name in self._loc_items:
            btn = QToolButton()
            btn.setText(name); btn.setCheckable(True); btn.setChecked(name in selected)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setAutoFillBackground(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(25)
            btn.setMinimumWidth(54)
            btn.setStyleSheet(
                f"QToolButton{{border:1.5px solid {btn_border};border-radius:6px;padding:3px 8px;{FF_KR};font-size:12px;background:transparent;color:{_TXT};}}"
                f"QToolButton:focus{{border:1.5px solid {btn_border};background:transparent;outline:none;}}"
                f"QToolButton:hover{{border:1.5px solid {btn_hover_border};background:#EFF6FF;color:{btn_soft_blue};}}"
                f"QToolButton:pressed{{border:1.5px solid {btn_soft_blue};background:#DBEAFE;color:{btn_soft_blue};padding:4px 7px 2px 9px;}}"
                f"QToolButton:checked{{background:{btn_checked};color:white;border-color:{btn_checked};font-weight:700;}}"
                f"QToolButton:checked:hover{{background:{btn_checked_dark};color:white;border-color:{btn_checked_dark};}}"
                f"QToolButton:checked:pressed{{background:{btn_checked_dark};color:white;border-color:{btn_checked_dark};padding:4px 7px 2px 9px;}}"
                f"QToolButton:checked:focus{{background:{btn_checked};color:white;border-color:{btn_checked};outline:none;}}"
            )
            btn.clicked.connect(_update)
            buttons.append(btn); h.addWidget(btn)
        h.addStretch()
        return w

    def set_loc(self, row: int, locs: list):
        self._syncing = True
        try:
            it = self.tbl.item(row, 2)
            w = self.tbl.cellWidget(row, 2)
            buttons = w.findChildren(QToolButton) if w else []
            if buttons:
                loc_set = set(locs)
                for btn in buttons:
                    btn.setChecked(btn.text() in loc_set)
                if it: it.setText("")
            elif it:
                it.setText(", ".join(locs))
        finally:
            self._syncing = False

    def get_loc_text(self, row: int) -> str:
        it = self.tbl.item(row, 2)
        w  = self.tbl.cellWidget(row, 2)
        if w:
            return ", ".join(b.text() for b in w.findChildren(QToolButton) if b.isChecked())
        return it.text() if it else ""

    def _make_sentence(self):
        from shared import _resolve_iga
        S = SETTINGS
        loc_sp_traces = defaultdict(lambda: defaultdict(set))
        loc_order = []; loc_seen = set()
        sp_has_field = defaultdict(bool); sp_q = defaultdict(int); sp_cam = defaultdict(int)
        for r in range(self.tbl.rowCount()):
            sp   = (self.tbl.item(r,0) or QTableWidgetItem()).text().strip()
            code = (self.tbl.item(r,1) or QTableWidgetItem()).text().strip()  # 대소문자 유지
            loc_raw = self.get_loc_text(r)
            if not sp: continue
            if code == "H": sp_q[sp] += 1; continue  # H = 탐문, 별도 문장 처리
            if code == "C": sp_cam[sp] += 1; continue  # C = 무인센서카메라, 별도 문장 처리
            if code == "B": continue
            if code: sp_has_field[sp] = True
            if not loc_raw: continue
            for loc in [x.strip() for x in loc_raw.split(",") if x.strip()]:
                if loc not in loc_seen: loc_seen.add(loc); loc_order.append(loc)
                for c in _split_trace(code): loc_sp_traces[loc][sp].add(c)

        # 1. 종합 요약 문장 생성
        split_herp = False
        if getattr(self, 'chk_split_herp', None):
            split_herp = self.chk_split_herp.isChecked()

        summary = _build_sentence(self.taxon, self.species_list, self.rns, self.prot_sheet, "field", split_herp)

        # 2. 입지 문장 생성
        trace_map = getattr(self._parent_page, "_trace_map", None)
        lines = []
        if loc_sp_traces:
            parts = []
            for loc in loc_order:
                if loc not in loc_sp_traces: continue
                chunks = [f"{sp}({_fmt_trace(cs, trace_map)})" if cs else sp
                          for sp, cs in sorted(loc_sp_traces[loc].items())]
                if chunks: parts.append(f"{loc}에서 {', '.join(chunks)}")
            if parts:
                pfx = S.site_s1_prefix
                try: pfx = pfx.format(분류군=self.display_name)
                except: pass
                
                # Get ending from global settings
                s1_end = S.field_s1_end
                s1_end_base = s1_end.replace("이 ", "").replace("가 ", "").replace("은 ", "").replace("는 ", "")
                # Find the last species to determine 이/가
                last_word = parts[-1].split("에서 ")[-1].split(", ")[-1].split("(")[0].strip()
                sfx = _resolve_iga(f"이(가) {s1_end_base}", last_word)
                
                lines.append(f"{pfx}{', '.join(parts)}{sfx}")
        if sp_cam:
            cam_list = sorted(sp_cam.keys())
            sp_str   = ", ".join(cam_list)
            s1_end   = getattr(S, "field_s1_end", "이 확인됨")
            for _pfx in ("이 ", "가 ", "은 ", "는 "):
                if s1_end.startswith(_pfx):
                    s1_end = s1_end[len(_pfx):]
                    break
            lines.append(f"무인센서카메라를 통하여 {sp_str} 등이 {s1_end}")

        if sp_q:
            field_and_q = sorted(sp for sp in sp_q if sp_has_field.get(sp))
            q_only      = sorted(sp for sp in sp_q if not sp_has_field.get(sp))
            core_A = S.site_s2_core_A; core_B = S.site_s2_core_B; core_C = S.site_s2_core_C
            현지확인 = ", ".join(field_and_q); 탐문 = ", ".join(q_only)
            try:
                if field_and_q and q_only:   core = core_C.format(현지확인=현지확인, 탐문=탐문)
                elif q_only:                 core = core_B.format(현지확인=현지확인, 탐문=탐문)
                else:                        core = core_A.format(현지확인=현지확인, 탐문=탐문)
            except KeyError:
                core = ""
            
            sfx = getattr(S, "site_s2_suffix", "전언됨")
            last_word = ""
            if q_only:
                last_word = q_only[-1]
            elif field_and_q:
                last_word = field_and_q[-1]
            if last_word:
                sfx = _resolve_iga(sfx, last_word)
            if not core.endswith(" "): core += " "
            lines.append(f"{S.site_s2_prefix}{core}{sfx}")            
        final_lines = [summary]
        for line in lines:
            final_lines.append(f"{line}")
            
        self.txt.setPlainText(_finish_sentence("\n".join(final_lines), ""))


class _SitePage(QWidget):
    def __init__(self, sheet, display_name, prot_sheet, parent_window=None):
        super().__init__()
        self._sheet         = sheet
        self._taxon         = sheet.taxon
        self._display_name  = display_name
        self._prot_sheet    = prot_sheet
        self._parent_window = parent_window
        self._loc_items     = list(_DEFAULT_LOCS)
        self._trace_map     = dict(TRACE_MAP)
        self._syncing       = False
        self._sub_rows      = defaultdict(list)
        self._all_rows      = {}
        self._all_panel     = None
        self._build(sheet)
        
    def _build(self, sheet):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4,4,4,4); lay.setSpacing(4)

        fld_rounds = [r for r in sheet.meta.round_names
                      if "현지" in r and r != "현지_합계"]
        per_tabs = []
        for rname in fld_rounds:
            rows = []
            for sp in sheet.species:
                val = sp.rounds.get(rname)
                if not val or str(val).strip() in ("","None","-","◎"): continue
                for code in _split_trace(str(val).strip()):
                    rows.append((sp.kor_name, code))
            if rows:
                per_tabs.append((rname, rname.replace("현지_",""), rows))

        keys_order = []; seen_k = set()
        for _, _, rows in per_tabs:
            for sp, tr in rows:
                if (sp,tr) not in seen_k:
                    seen_k.add((sp,tr)); keys_order.append((sp,tr))

        self._tab_w = QTabWidget(); self._tab_w.setDocumentMode(True)
        self._tab_w.setStyleSheet(_tab_qss(False))
        
        all_sp = [sp for sp in sheet.species if any(_has_present(sp.rounds.get(r)) for r in fld_rounds)]

        all_panel = _SitePanel(keys_order, self._loc_items, self._display_name,
                               self._taxon, all_sp, fld_rounds, self._prot_sheet,
                               parent_page=self, is_all=True)
        self._all_panel = all_panel
        for r, (sp, tr) in enumerate(keys_order):
            self._all_rows[(sp,tr)] = r

        all_sc = QScrollArea(); all_sc.setWidgetResizable(True); all_sc.setFrameShape(QFrame.NoFrame)
        all_sc.setWidget(all_panel)
        self._tab_w.addTab(all_sc, "전체")

        self._sub_panels = []
        for rname, label, rows in per_tabs:
            sub_sp = [sp for sp in sheet.species if _has_present(sp.rounds.get(rname))]
            panel = _SitePanel(rows, self._loc_items, self._display_name,
                               self._taxon, sub_sp, [rname], self._prot_sheet,
                               parent_page=self, is_all=False)
            self._sub_panels.append(panel)
            for r, (sp, tr) in enumerate(rows):
                self._sub_rows[(sp,tr)].append((panel, r))
            sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame)
            sc.setWidget(panel)
            self._tab_w.addTab(sc, label)

        lay.addWidget(self._tab_w)

        # 전역 문장 설정 변경 시 모든 패널 문장 갱신
        if self._parent_window and hasattr(self._parent_window, "sig_sent_settings"):
            def _refresh_site_sentences():
                for p in self._sub_panels + ([self._all_panel] if self._all_panel else []):
                    p._make_sentence()
            self._parent_window.sig_sent_settings.connect(_refresh_site_sentences)

    def _rebuild_all(self, sp: str, trace: str):
        if self._syncing or self._all_panel is None: return
        key     = (sp, trace)
        all_row = self._all_rows.get(key)
        if all_row is None: return
        merged  = {}
        for panel, r in self._sub_rows.get(key, []):
            for loc in [x.strip() for x in panel.get_loc_text(r).split(",") if x.strip()]:
                if loc not in merged: merged[loc] = True
        self._all_panel.set_loc(all_row, list(merged.keys()))

    def _edit_locs(self):
        dlg = LocEditorDialog(self._loc_items, self)
        if dlg.exec() == QDialog.Accepted:
            self._loc_items = dlg.get()
            self._rebuild_panels()

    def _edit_traces(self):
        dlg = TraceEditorDialog(self._trace_map, self)
        if dlg.exec() == QDialog.Accepted:
            self._trace_map = dlg.get()
            # 모든 패널에서 문장 즉시 갱신
            for p in self._sub_panels + ([self._all_panel] if self._all_panel else []):
                p._make_sentence()

    def _rebuild_panels(self):
        states = {}
        for panel in self._sub_panels:
            for r in range(panel.tbl.rowCount()):
                sp = (panel.tbl.item(r,0) or QTableWidgetItem()).text()
                tr = (panel.tbl.item(r,1) or QTableWidgetItem()).text()
                states[(sp,tr,id(panel),r)] = panel.get_loc_text(r)
        for panel in self._sub_panels:
            panel._loc_items = self._loc_items
            for r in range(panel.tbl.rowCount()):
                sp = (panel.tbl.item(r,0) or QTableWidgetItem()).text()
                tr = (panel.tbl.item(r,1) or QTableWidgetItem()).text()
                if tr in ("H", "C"):  # 탐문/무인센서카메라: 입지 선택 비활성화
                    from PySide6.QtWidgets import QLabel
                    from PySide6.QtCore import Qt as _Qt
                    label_text = "탐문조사 (별도 처리)" if tr == "H" else "무인센서카메라 (별도 처리)"
                    lbl = QLabel(label_text)
                    lbl.setAlignment(_Qt.AlignCenter)
                    lbl.setStyleSheet(f"color:{_SUB};font-size:11px;{FF_KR};font-style:italic;")
                    panel.tbl.setCellWidget(r, 2, lbl)
                else:
                    prev = set(x.strip() for x in
                               states.get((sp,tr,id(panel),r),"").split(",") if x.strip())
                    panel.tbl.setCellWidget(r, 2, panel._build_loc_widget(r, tr, prev))
        for key in self._all_rows:
            self._rebuild_all(key[0], key[1])

    def apply_settings(self, cfg: dict):
        self._settings = cfg
        for p in self._sub_panels + ([self._all_panel] if self._all_panel else []):
            p.apply_settings(cfg)


# ══════════════════════════════════════════════════════════════════════════════
# 메인 빌더
# ══════════════════════════════════════════════════════════════════════════════

def build_land_tab(stats: TaxaStats, sheet: ParsedSheet,
                   prot_sheet: ParsedProtected | None = None,
                   parent_window=None) -> QWidget:
    by_round = _species_by_round(sheet)
    outer    = QWidget(); lay = QVBoxLayout(outer); lay.setContentsMargins(0,0,0,0)

    chart_sig = []
    sent_sig  = []
    if parent_window and hasattr(parent_window, "sig_chart_settings"):
        chart_sig = [parent_window.sig_chart_settings]
    if parent_window and hasattr(parent_window, "sig_sent_settings"):
        sent_sig  = [parent_window.sig_sent_settings]

    top_tabs = QTabWidget(); top_tabs.setDocumentMode(True)
    top_tabs.setStyleSheet(_tab_qss(True))

    fld_dict = by_round.get("field", {})
    if fld_dict:
        all_field_rns_for_groups = [r for r in sheet.meta.round_names
                                    if "현지" in r and "합계" not in r and "종합" not in r]
        field_group_defs = parent_window.get_active_groups(all_field_rns_for_groups) if parent_window and hasattr(parent_window, "get_active_groups") else []
        field_group_entries = []
        used_labels = set(fld_dict.keys())
        for group_name, group_rns in field_group_defs:
            sp_g = [sp for sp in sheet.species if any(_has_present(sp.rounds.get(r)) for r in group_rns)]
            if not sp_g:
                continue
            label = group_name
            if label in used_labels:
                label = f"{label}(그룹)"
            used_labels.add(label)
            field_group_entries.append((label, sp_g, group_rns))

        if stats.taxon in SITE_TAXONS:
            if parent_window and hasattr(parent_window, "step_sub_progress"):
                parent_window.step_sub_progress(f"화면(UI) 생성 중 ({sheet.name}: 현지조사)", 1.0)
            disp = TAXON_LABEL.get(stats.taxon, stats.taxon)
            round_tabs = QTabWidget()
            round_tabs.setDocumentMode(True)
            round_tabs.setStyleSheet(_tab_qss(False))
            all_rns = [r for r in sheet.meta.round_names
                       if "현지" in r and "합계" not in r and "종합" not in r]
            fld_display = OrderedDict()
            rns_by_label = {}
            fld_display["전체"] = fld_dict.get("전체", [])
            for label, sp_g, group_rns in field_group_entries:
                fld_display[label] = sp_g
                rns_by_label[label] = group_rns
            if not field_group_entries:
                for k, v in fld_dict.items():
                    if k != "전체":
                        fld_display[k] = v
            site_panels = _build_round_site_panels(sheet, disp, stats.taxon, fld_display,
                                                   all_rns, prot_sheet, parent_window, rns_by_label=rns_by_label)
            for rname, sp_list in fld_display.items():
                if not sp_list:
                    continue
                rns = rns_by_label.get(rname, all_rns if rname == "전체" else [rname])
                site_panel = site_panels.get(rname)
                if site_panel is None:
                    continue
                round_tabs.addTab(
                    _field_round_full_panel(stats.taxon, sheet, disp, sp_list, rns,
                                            rname, site_panel, prot_sheet, chart_sig, sent_sig),
                    _rn(rname)
                )
            top_tabs.addTab(round_tabs, "🔭  현지조사")
        else:
            sub_f = QTabWidget(); sub_f.setDocumentMode(True)
            sub_f.setStyleSheet(_tab_qss(False))
            fld_display = [("전체", fld_dict.get("전체", []), None)]
            fld_display.extend((label, sp_g, group_rns) for label, sp_g, group_rns in field_group_entries)
            if not field_group_entries:
                fld_display.extend((rname, sp_list, None) for rname, sp_list in fld_dict.items() if rname != "전체")
            _all_fld_sp = fld_dict.get("전체", [])
            num_fld = len([1 for _, sp, _ in fld_display if sp])
            for rname, sp_list, rns_override in fld_display:
                if not sp_list: continue
                if parent_window and hasattr(parent_window, "step_sub_progress"):
                    parent_window.step_sub_progress(f"화면(UI) 생성 중 ({sheet.name}: 현지 - {rname})", 1.0 / max(1, num_fld))
                panel = _field_panel(stats.taxon, sheet, sp_list, prot_sheet,
                                     rname, chart_sig, sent_sig, rns_override=rns_override,
                                     total_rns=all_field_rns_for_groups if rns_override is not None else None,
                                     total_species=_all_fld_sp if rns_override is not None else None)
                sc = QScrollArea(); sc.setWidgetResizable(True)
                sc.setFrameShape(QFrame.NoFrame); sc.setWidget(panel)
                sub_f.addTab(sc, _rn(rname))
            top_tabs.addTab(sub_f, "🔭  현지조사")
    else:
        empty = QWidget(); el = QVBoxLayout(empty)
        el.addWidget(QLabel("현지조사 데이터 없음"))
        top_tabs.addTab(empty, "🔭  현지조사")

    lit_dict = by_round.get("lit", {})
    if lit_dict:
        all_lit_rns_for_groups = [r for r in sheet.meta.round_names
                                  if "문헌" in r and "합계" not in r and "종합" not in r]
        lit_group_defs = parent_window.get_active_groups(all_lit_rns_for_groups) if parent_window and hasattr(parent_window, "get_active_groups") else []
        lit_group_entries = []
        used_lit_labels = set(lit_dict.keys())
        for group_name, group_rns in lit_group_defs:
            sp_g = [sp for sp in sheet.species if any(_has_present(sp.rounds.get(r)) for r in group_rns)]
            if not sp_g:
                continue
            label = group_name if group_name not in used_lit_labels else f"{group_name}(그룹)"
            used_lit_labels.add(label)
            lit_group_entries.append((label, sp_g))
        panel = _lit_panel_all(stats.taxon, lit_dict, prot_sheet, chart_sig, sent_sig, group_entries=lit_group_entries)
        sc    = QScrollArea(); sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame); sc.setWidget(panel)
        top_tabs.addTab(sc, "📚  문헌조사")
    else:
        empty = QWidget(); el = QVBoxLayout(empty)
        el.addWidget(QLabel("문헌조사 데이터 없음"))
        top_tabs.addTab(empty, "📚  문헌조사")

    lay.addWidget(top_tabs)
    return outer
