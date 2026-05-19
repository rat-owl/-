# aqua_tab.py — 육수생물(어류·저서) 분석 탭
# land_tab의 디자인 시스템 공유
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import math
from collections import OrderedDict, defaultdict
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QLabel, QPlainTextEdit, QPushButton,
    QTabWidget, QTabBar, QScrollArea, QFrame, QSizePolicy,
    QDoubleSpinBox, QSpinBox, QFormLayout, QLineEdit, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from analyzer import AquaticStats, DivStats
from parser   import ParsedAquatic, ParsedProtected
from shared import _s, _has as _base_has
from ui_shared import make_tab_qss, make_scroll_widget, bold_row, set_total_pct_cell as _shared_set_total_pct_cell

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    _MPL = True
except ImportError:
    _MPL = False

# ── 공통 요소 import ────────────────────────────────────
from config import (
    _BG, _CARD, _BORDER, _TXT, _SUB, _PATH,
    _ACCENT, _ACCENT_D, _ACCENT_L, _SUCCESS, _WARN, _ERR,
    _FONT_EN, _FONT_KR, FF_KR, FF_EN, BD, BD1,
    PIE_COLORS, GRAPH_H, SETTINGS
)
from ui_shared import (
    _Canvas, PieCanvas, CanvasGroupBox, ResizableCanvasFrame, CanvasSizeSlider, GraphValueSlider,
    _make_tbl, _item, _auto_fit_table, _tbl_auto_height, _int,
    _fmt, _pct, _korean_font, _apply_mpl, _normalized_percentages, _apply_ratio_correction, _series_palette,
    _get_nice_bounds, _apply_axes_common, _apply_bar_margins, _apply_graph_scale, _gray_palette, make_color_settings_btn, make_copy_graph_btn,
    make_outline_btn_qss, _COPY_BTN_QSS, _OUTLINE_BTN_GREEN,
    lit_result_prefix, lit_shi_prefix,
)
from graph_widgets import (
    apply_graph_default,
    wrap_canvas as _common_wrap_canvas,
    make_settings_below_graph as _common_make_settings_below_graph,
    make_triplet as _common_make_triplet,
    make_pie_settings_panel as _common_make_pie_settings_panel,
    make_bar_settings_panel as _common_make_bar_settings_panel,
    attach_title_controls_to_canvas_group as _attach_title_to_cv,
)
from shared import _has_present, _prot_grade_str, _prot_list_graded, _ecosystem_disturber_list, _apply_title, _resolve_iga, _josa

# ── QSS ─────────────────────────────────────────────────────────
_QSS = f"""
QWidget   {{ background:{_BG}; {FF_KR}; font-size:13px; color:{_TXT}; }}
QGroupBox {{
    {FF_KR}; font-size:12px; font-weight:700; color:{_TXT};
    {BD}; border-radius:10px; margin-top:12px; background:{_CARD}; padding-top:8px;
}}
QGroupBox::title {{
    subcontrol-origin:margin; subcontrol-position:top left;
    left:12px; padding:0 6px; color:{_TXT}; font-size:12px;
}}
QTableWidget {{
    {BD}; border-radius:8px; background:{_CARD};
    gridline-color:{_BORDER}; {FF_KR}; font-size:12px;
}}
QTableWidget::item          {{ padding:3px 6px; }}
QTableWidget::item:selected {{ background:{_ACCENT_L}; color:{_ACCENT}; }}
QHeaderView::section {{
    background:{_BG}; {BD1}; border-right:1px solid {_BORDER};
    padding:5px 6px; {FF_KR}; font-size:11px; font-weight:700; color:{_SUB};
}}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical         {{ background:{_BG}; width:6px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#B0B8C8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""

def _tab_qss(big=True):
    return make_tab_qss(FF_KR, _SUB, _ACCENT, big)


# ── 유틸 ─────────────────────────────────────────────────────────
def _has(v): return _base_has(v, ("","None","-","0","0.0","x","X","×"))

def _bold_row(tbl, row):
    bold_row(tbl, row, _BG)

def _set_total_pct_cell(tbl, row, col, pct_value, pct_formatter=_pct):
    _shared_set_total_pct_cell(
        tbl, row, col, pct_value,
        item_factory=_item, pct_formatter=pct_formatter, err_color=_ERR, decimals=SETTINGS.decimal
    )

def _sc(w):
    return make_scroll_widget(w)

def _wrap_cv(title, cv, h=GRAPH_H, default_size=None):
    g=QGroupBox(title); l=QVBoxLayout(g)
    l.setContentsMargins(6,14,6,6)
    head = QHBoxLayout()
    head.addStretch()
    head.addWidget(make_copy_graph_btn(cv))
    l.addLayout(head)
    if default_size and len(default_size) == 2:
        cv.setMinimumSize(int(default_size[0]), int(default_size[1]))
    else:
        cv.setMinimumHeight(h)
    l.addWidget(cv, alignment=Qt.AlignCenter)
    return g


def _wrap_cv_resizable(title, canvas, default_size=None):
    # 육수생물 그래프는 스크롤 영역 안에서 항상 중앙에 배치한다.
    return _common_wrap_canvas(title, canvas, alignment=Qt.AlignCenter, size_policy_ignored=False, default_size=default_size)



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


def _make_settings_graph(panel_w, cv_grp):
    # 설정/그래프 2분할 구조는 graph_widgets의 공통 레이아웃을 사용한다.
    return _common_make_settings_below_graph(panel_w, cv_grp)


def _make_triplet(tbl_grp, panel_w, cv_grp):
    return _common_make_triplet(
        tbl_grp,
        panel_w,
        cv_grp,
        panel_min=220,
        panel_max=360,
        sizes=(1, 260, 860),
        table_content_width=True,
        settings_position="bottom",
    )


def _make_pie_settings_panel(pie, cv_grp):
    # 파이 공통 항목: 반지름, 글씨 크기, 지시선, 색상, 복사.
    return _common_make_pie_settings_panel(pie, include_title=True, radius_label="반지름")


def _make_bar_settings_panel(canvas, cv_grp):
    # 기본 막대 공통 항목: 막대 너비, 그래프 너비/높이, 글씨 크기.
    return _common_make_bar_settings_panel(canvas, mode="bar")


def _make_dom_settings_panel(canvas, cv_grp, on_pct_change=None):
    # 우점도 그래프는 기준값/방향/정렬/범례까지 공통 패널에서 켠다.
    return _common_make_bar_settings_panel(
        canvas,
        mode="dominance",
        include_title=True,
        include_y_title=True,
        show_direction=True,
        show_legend=True,
        show_sort=True,
        show_dom_pct=True,
        on_pct_change=on_pct_change,
    )

# ── round_name 파싱 "현지_1차_Wa.1" → ("현지","1차","Wa.1") ────
def _prn(rn):
    p=rn.split("_",2)
    return (p[0] if len(p)>0 else ""),\
           (p[1] if len(p)>1 else ""),\
           (p[2] if len(p)>2 else "")

def _round_survey_label(label):
    label = str(label or "").strip()
    if not label:
        return "조사"
    if "".join(label.split()).endswith("조사"):
        return label
    return f"{label} 조사"

def _survey_prefix(survey, rns):
    survey_name = "현지조사" if survey == "field" else "문헌조사"
    intro_mode = getattr(
        SETTINGS,
        "field_intro_mode" if survey == "field" else "lit_intro_mode",
        getattr(SETTINGS, "field_intro_mode", "auto"),
    )
    if intro_mode == "fixed":
        return survey_name
    labels = []
    sites = []
    for r in rns or []:
        _, rnd, site = _prn(r)
        if (site or rnd) in ("종합", "합계"):
            continue
        if site and site not in sites:
            sites.append(site)
        if rnd and rnd not in labels:
            labels.append(rnd)
    if len(sites) == 1:
        return _round_survey_label(sites[0])
    if len(labels) > 1:
        return survey_name
    if len(labels) == 1:
        return _round_survey_label(labels[0])
    return survey_name

def _lit_round_names(sheet):
    special = {"sci", "kor", "remark", "family", "order", "_total", "_ra", "qi_tesb", "qi_aesb"}
    field_set = set(sheet.meta.round_names)
    return [
        k for k in sheet.meta.field_cols
        if k not in special and not k.startswith("_") and k not in field_set
    ]


def _round_groups2(sheet):
    grp = {"현지": OrderedDict(), "문헌": OrderedDict()}
    for rn in sheet.meta.round_names:
        sec, rnd, site = _prn(rn)
        grp.setdefault(sec, OrderedDict())
        grp[sec].setdefault(rnd, []).append(rn)
    for k in _lit_round_names(sheet):
        if "_합계" in k:
            continue
        sec, rnd, site = _prn(k)
        grp["문헌"].setdefault(rnd, []).append(k)
    return grp

def _round_groups(sheet):
    """{"현지":{"1차":[rns],"2차":[rns]}, "문헌":{"1차":[rns]}}"""
    grp={"현지":OrderedDict(),"문헌":OrderedDict()}
    for rn in sheet.meta.round_names:
        sec,rnd,site=_prn(rn)
        if sec not in grp: grp[sec]=OrderedDict()
        grp[sec].setdefault(rnd,[]).append(rn)
    for k in sheet.meta.field_cols:
        if k.startswith("문헌_") and "_합계" not in k:
            sec,rnd,site=_prn(k); grp["문헌"].setdefault(rnd,[]).append(k)
    return grp

def _sp_in_any(species, rns):
    return [sp for sp in species if any(_has(sp.rounds.get(r)) for r in rns)]

def _sp_in_rn(species, rn):
    return [sp for sp in species if _has(sp.rounds.get(rn))]


def _detail_rns(rns):
    # 2단계 키("현지_Wa.1")는 site 부분이 ""이지만 유효한 지점 컬럼이므로 포함
    # 단, 명시적 집계 컬럼("종합", "합계")만 제외
    result = []
    for r in rns:
        _, rnd, site = _prn(r)
        last = site if site else rnd   # 3단계 키면 site, 2단계 키면 rnd가 지점명
        if last not in ("종합", "합계"):
            result.append(r)
    return result


_INSECT_ORDERS = {
    "EPHEMEROPTERA", "ODONATA", "HEMIPTERA", "DIPTERA", "TRICHOPTERA",
    "PLECOPTERA", "COLEOPTERA", "MEGALOPTERA", "LEPIDOPTERA",
}


def _compact_tbl(tbl, row_h=24, h=None):
    tbl.verticalHeader().setDefaultSectionSize(row_h)
    for r in range(tbl.rowCount()):
        tbl.setRowHeight(r, row_h)
    tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    if h is not None:
        tbl.setFixedHeight(h)


def _bind_table_pct_refresh(tbl, pct_col, cnt_col=None, pct_formatter=None):
    from ui_shared import normalize_tbl_pct_col

    if pct_formatter is None:
        pct_formatter = _fmt

    def _refresh():
        normalize_tbl_pct_col(
            tbl,
            pct_col,
            cnt_col=cnt_col,
            pct_formatter=pct_formatter,
            decimals=SETTINGS.decimal,
        )

    tbl._refresh_cb = _refresh
    return tbl


def _family_counts(species):
    data = OrderedDict()
    for sp in species:
        fam = sp.family or "미상"
        data[fam] = data.get(fam, 0) + 1
    return data


def _metric_range_str(values, decimals=2):
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return f"{0:.{decimals}f}"
    lo = min(vals)
    hi = max(vals)
    if math.isclose(lo, hi, abs_tol=10 ** (-decimals) / 2):
        return f"{lo:.{decimals}f}"
    return f"{lo:.{decimals}f}~{hi:.{decimals}f}"


def _site_metric_ranges(species, rns):
    site_rns = _detail_rns(rns)
    if not site_rns:
        div = _calc_local_div(species, rns)
        total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in _detail_rns(rns))
        ri = (len([sp for sp in species if sum(_int(sp.rounds.get(r, 0)) for r in _detail_rns(rns)) > 0]) - 1) / math.log(total_ind) if total_ind > 1 else 0.0
        return [div.dominance_di], [div.shannon_h], [ri], [div.evenness_e]

    divs = []
    hs = []
    ris = []
    es = []
    for rn in site_rns:
        sp_site = _sp_in_rn(species, rn)
        total_ind = sum(_int(sp.rounds.get(rn, 0)) for sp in sp_site)
        if total_ind == 0:
            continue
        div = _calc_local_div(sp_site, [rn])
        ri = (len(sp_site) - 1) / math.log(total_ind) if total_ind > 1 else 0.0
        divs.append(div.dominance_di)
        hs.append(div.shannon_h)
        ris.append(ri)
        es.append(div.evenness_e)

    if not divs:
        total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in _detail_rns(rns))
        if total_ind == 0:
            return [], [], [], []
        div = _calc_local_div(species, rns)
        ri = (len([sp for sp in species if sum(_int(sp.rounds.get(r, 0)) for r in _detail_rns(rns)) > 0]) - 1) / math.log(total_ind) if total_ind > 1 else 0.0
        return [div.dominance_di], [div.shannon_h], [ri], [div.evenness_e]

    return divs, hs, ris, es


def _family_desc_from_items(fam_items, fam_pcts, kor_map):
    grouped = []
    key_to_idx = {}
    tol = 10 ** (-SETTINGS.decimal) / 2
    for (fam, cnt), pct in zip(fam_items, fam_pcts):
        label = kor_map.get(fam) or fam
        pct_txt = _pct(pct)
        key = (cnt, pct_txt)
        if key in key_to_idx:
            grouped[key_to_idx[key]]["labels"].append(label)
            continue

        # 반올림 키가 달라도 허용 오차 내 동일값이면 같은 그룹으로 병합
        merged = False
        for idx, g in enumerate(grouped):
            if g["count"] == cnt and (_pct(g["pct"]) == pct_txt or math.isclose(g["pct"], pct, abs_tol=tol)):
                g["labels"].append(label)
                key_to_idx[key] = idx
                merged = True
                break
        if not merged:
            key_to_idx[key] = len(grouped)
            grouped.append({"labels": [label], "count": cnt, "pct": pct})

    parts = []
    for g in grouped:
        label_txt = ", ".join(g["labels"])
        if len(g["labels"]) > 1:
            parts.append(f"{label_txt} 각각 {g['count']}종({_pct(g['pct'])})")
        else:
            parts.append(f"{label_txt} {g['count']}종({_pct(g['pct'])})")
    return ", ".join(parts)


def _labels_count_pct_desc(items, unit):
    grouped = []
    key_to_idx = {}
    tol = 10 ** (-SETTINGS.decimal) / 2
    for label, count, pct in items:
        pct_txt = _pct(pct)
        key = (count, pct_txt)
        if key in key_to_idx:
            grouped[key_to_idx[key]]["labels"].append(label)
            continue

        merged = False
        for idx, g in enumerate(grouped):
            if g["count"] == count and (_pct(g["pct"]) == pct_txt or math.isclose(g["pct"], pct, abs_tol=tol)):
                g["labels"].append(label)
                key_to_idx[key] = idx
                merged = True
                break
        if not merged:
            key_to_idx[key] = len(grouped)
            grouped.append({"labels": [label], "count": count, "pct": pct})

    parts = []
    for g in grouped:
        label_txt = ", ".join(g["labels"])
        if len(g["labels"]) > 1:
            parts.append(f"{label_txt} 각각 {g['count']:,}{unit}({_pct(g['pct'])})")
        else:
            parts.append(f"{label_txt} {g['count']:,}{unit}({_pct(g['pct'])})")
    return parts


def _index_range_sentence(species, rns, tail=None, include_range_word=True):
    di_vals, h_vals, ri_vals, e_vals = _site_metric_ranges(species, rns)

    if not any([di_vals, h_vals, ri_vals, e_vals]):
        return None

    body = (
        f"군집분석 결과, 우점도지수(DI)는 {_metric_range_str(di_vals)}, "
        f"종다양도지수(H')는 {_metric_range_str(h_vals)}, "
        f"종풍부도지수(RI)는 {_metric_range_str(ri_vals)}, "
        f"균등도지수(EI))는 {_metric_range_str(e_vals)}"
    )
    use_range = include_range_word and len(_detail_rns(rns)) > 1
    tail_txt = tail.strip() if tail else ""

    if use_range:
        # tail이 '로 ...'로 시작하면 '의 범위'까지만 붙여 중복 조사를 방지
        if tail_txt.startswith("로"):
            body += "의 범위"
        else:
            body += "의 범위로"
    else:
        body += "로"

    if tail_txt:
        if body.endswith("범위") and tail_txt.startswith("로"):
            body += tail_txt
        elif body.endswith("로") and tail_txt.startswith("로"):
            tail_txt = tail_txt[1:].lstrip()
            body += f" {tail_txt}" if tail_txt else ""
        else:
            body += f" {tail_txt}"
    return body


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


def _calc_local_div(species, rns=None):
    species_counts = []
    order_counts = OrderedDict()

    for sp in species:
        if rns:
            cnt = sum(_int(sp.rounds.get(r, 0)) for r in _detail_rns(rns))
        else:
            cnt = _int(getattr(sp, "total", 0))
        if cnt <= 0:
            continue
        species_counts.append(cnt)
        order = sp.order or ""
        order_counts[order] = order_counts.get(order, 0) + cnt

    total = sum(species_counts)
    if total <= 0:
        return DivStats(0.0, 0.0, 0.0, "", 0, "", 0)

    h = sum(-(c / total) * math.log(c / total) for c in species_counts if c > 0)
    s = len(species_counts)
    e = h / math.log(s) if s > 1 else 0.0

    sorted_species = sorted(species_counts, reverse=True)
    di = (sorted_species[0] + (sorted_species[1] if len(sorted_species) > 1 else 0)) / total

    sorted_orders = sorted(order_counts.items(), key=lambda x: (-x[1], x[0]))
    dom = sorted_orders[0] if sorted_orders else ("", 0)
    sub = sorted_orders[1] if len(sorted_orders) > 1 else ("", 0)

    return DivStats(
        shannon_h=h,
        evenness_e=e,
        dominance_di=di,
        dominant_order=dom[0],
        dominant_count=dom[1],
        subdominant_order=sub[0],
        subdominant_count=sub[1],
    )


def _family_kor_from_species(species):
    data = OrderedDict()
    for sp in species:
        fam = sp.family or "미상"
        if fam not in data or not data[fam]:
            data[fam] = _s(getattr(sp, "family_kor", ""))
    return data


def _fish_family_data(species):
    items = sorted(_family_counts(species).items(), key=lambda x: (-x[1], x[0]))
    kor_map = _family_kor_from_species(species)
    return OrderedDict((((kor_map.get(fam) or fam), cnt) for fam, cnt in items))


def _fish_family_tbl(species, sort_mode="desc"):
    fams = _family_counts(species)
    kor_map = _family_kor_from_species(species)
    items = sorted(fams.items(), key=lambda x: (-x[1], x[0]))
    if sort_mode == "taxa":
        items = sorted(fams.items(), key=lambda x: (x[0], -x[1]))
    total = sum(cnt for _, cnt in items)
    tbl = _make_tbl(["과명", "국명", "종수", "비율(%)"])
    tbl.setRowCount(len(items) + 1)
    pct_sum = 0.0
    for ri, (fam, cnt) in enumerate(items):
        pct = cnt / total * 100 if total else 0
        tbl.setItem(ri, 0, _item(fam, Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(kor_map.get(fam) or fam, Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(cnt))
        tbl.setItem(ri, 3, _item(_fmt(pct)))
        pct_sum += round(pct, SETTINGS.decimal)
    last = len(items)
    tbl.setItem(last, 0, _item("합계"))
    tbl.setItem(last, 1, _item(""))
    tbl.setItem(last, 2, _item(total))
    _set_total_pct_cell(tbl, last, 3, pct_sum if items else 0, pct_formatter=_fmt)
    _bold_row(tbl, last)
    _auto_fit_table(tbl)
    _compact_tbl(tbl, 24, 34 + 24 * min(tbl.rowCount(), 8))
    return tbl

def _fish_dom_rows(species, rns, limit=7, min_pct=None, force_norm=False):
    rns = _detail_rns(rns)
    rows = []
    for sp in species:
        indiv = sum(_int(sp.rounds.get(r, 0)) for r in rns)
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


def _rebuild_dom_tbl(tbl, species, rns, dom_pct, force_norm=False):
    """기존 테이블 위젯을 dom_pct 기준으로 인플레이스 재구성.
    dom_pct 이상 → 개별 행, 미만 → 기타(N종) 합산 행, 마지막 → 합계 행.
    """
    all_rows = _fish_dom_rows(species, rns, limit=len(species) or 1, min_pct=None, force_norm=force_norm)
    above = [(sp, c, p) for sp, c, p in all_rows if p >= dom_pct]
    below = [(sp, c, p) for sp, c, p in all_rows if p < dom_pct]
    others_n   = len(below)
    others_cnt = sum(c for _, c, _ in below)
    others_pct = sum(p for _, _, p in below)
    total_ind  = sum(c for _, c, _ in all_rows)
    dec = SETTINGS.decimal

    row_count = len(above) + (1 if others_n > 0 else 0) + 1  # +1 합계
    tbl.clearContents()
    tbl.setRowCount(row_count)

    for ri, (sp, indiv, pct) in enumerate(above):
        tbl.setItem(ri, 0, _item(sp.sci_name or "", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(sp.kor_name or "", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(indiv))
        tbl.setItem(ri, 3, _item(f"{pct:.{dec}f}"))

    ri = len(above)
    if others_n > 0:
        tbl.setItem(ri, 0, _item(""))
        tbl.setItem(ri, 1, _item(f"기타({others_n}종)", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(others_cnt))
        tbl.setItem(ri, 3, _item(f"{others_pct:.{dec}f}"))
        ri += 1

    tbl.setItem(ri, 0, _item("합계"))
    tbl.setItem(ri, 1, _item(""))
    tbl.setItem(ri, 2, _item(total_ind))
    tbl.setItem(ri, 3, _item(f"{100.0 if total_ind else 0:.{dec}f}"))
    for c in range(4):
        it = tbl.item(ri, c)
        if it:
            it.setBackground(QColor(_BG))

    _auto_fit_table(tbl)
    _compact_tbl(tbl, 24, 34 + 24 * max(1, tbl.rowCount()))


def _fish_ra_tbl(species, rns, sort_mode="desc"):
    rows = []
    total_ind = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in rns)
    for sp in species:
        indiv = sum(_int(sp.rounds.get(r, 0)) for r in rns)
        rows.append([sp, indiv, sp.ra_pct])
    
    # 정렬 모드에 따라 정렬
    if sort_mode == "taxa":
        rows.sort(key=lambda x: (x[0].family or "", x[0].kor_name or x[0].sci_name))
    else:  # "desc" (상대풍부도 내림차순)
        rows.sort(key=lambda x: (-x[2], -x[1], x[0].kor_name or x[0].sci_name))
    
    if not any(r[2] for r in rows):
        for r in rows:
            if not r[2]: r[2] = r[1] / total_ind * 100 if total_ind else 0
            
    tbl = _make_tbl(["과명", "국명", "학명", "개체수", "상대풍부도(%)"])
    tbl.setRowCount(len(rows) + 1)
    pct_sum = 0.0
    for ri, (sp, indiv, ra) in enumerate(rows):
        tbl.setItem(ri, 0, _item(sp.family or "", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(sp.kor_name or "", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(sp.sci_name or "", Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 3, _item(indiv))
        tbl.setItem(ri, 4, _item(f"{ra:.{SETTINGS.decimal}f}"))
        pct_sum += round(ra, SETTINGS.decimal)
    last = len(rows)
    tbl.setItem(last, 0, _item("합계"))
    tbl.setItem(last, 1, _item(""))
    tbl.setItem(last, 2, _item(""))
    tbl.setItem(last, 3, _item(sum(ind for _, ind, _ in rows)))
    
    from ui_shared import set_total_pct_cell as _shared_set_total_pct_cell
    _shared_set_total_pct_cell(
        tbl, last, 4, pct_sum if rows else 0,
        item_factory=_item,
        pct_formatter=lambda x: f"{float(x):.{SETTINGS.decimal}f}",
        err_color=_ERR,
        decimals=SETTINGS.decimal
    )
    
    _bold_row(tbl, last)
    _auto_fit_table(tbl)
    _compact_tbl(tbl, 24)
    return tbl


def _order_kor_map(species):
    m = {}
    for sp in species:
        if sp.order:
            kor = _s(getattr(sp, "order_kor", ""))
            m[sp.order] = kor if kor else sp.order
    return m

def _benthos_group_name(sp):
    order_eng = _s(sp.order).upper()
    if order_eng in _INSECT_ORDERS:
        kor = _s(getattr(sp, "order_kor", "")) or sp.order
        return sp.order, kor
    return "Non-insecta", "비곤충류"

def _benthos_group_stats(species, rns=None):
    by_group = OrderedDict()
    for sp in species:
        eng, kor = _benthos_group_name(sp)
        if eng not in by_group:
            by_group[eng] = {"eng": eng, "kor": kor, "species": 0, "individuals": 0}
        by_group[eng]["species"] += 1
        if rns:
            by_group[eng]["individuals"] += sum(_int(sp.rounds.get(r, 0)) for r in _detail_rns(rns))
        else:
            by_group[eng]["individuals"] += sp.total
    rows = list(by_group.values())
    non = [row for row in rows if row["eng"] == "Non-insecta"]
    ins = [row for row in rows if row["eng"] != "Non-insecta"]
    return non + ins


def _benthos_pie_data(species, by="species", rns=None):
    key = "species" if by == "species" else "individuals"
    stats = _benthos_group_stats(species, rns)
    return OrderedDict((row["kor"], row[key]) for row in stats if row[key] > 0)


def _benthos_tbl(species, by="species", rns=None, sort_mode="taxa"):
    stats = _benthos_group_stats(species, rns)
    key = "species" if by == "species" else "individuals"
    total_val = sum(row[key] for row in stats)
    hdr = "종수" if by == "species" else "개체수"
    
    # sort_mode에 따라 정렬
    if sort_mode == "desc":
        stats_sorted = sorted(stats, key=lambda x: (-x[key], x["kor"]))
    else:  # "taxa"
        stats_sorted = stats  # 기본 순서: Non-insecta + 곤충류
    
    tbl = _make_tbl(["분류군", "", hdr, "비율(%)"])
    tbl.setRowCount(len(stats_sorted) + 1)
    pct_sum = 0.0
    for ri, row in enumerate(stats_sorted):
        pct = row[key] / total_val * 100 if total_val else 0
        tbl.setItem(ri, 0, _item(row["eng"], Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 1, _item(row["kor"], Qt.AlignLeft | Qt.AlignVCenter))
        tbl.setItem(ri, 2, _item(row[key]))
        tbl.setItem(ri, 3, _item(_fmt(pct)))
        pct_sum += round(pct, SETTINGS.decimal)
    last = len(stats_sorted)
    tbl.setItem(last, 0, _item("합계"))
    tbl.setItem(last, 1, _item(""))
    tbl.setItem(last, 2, _item(sum(row[key] for row in stats)))
    _set_total_pct_cell(tbl, last, 3, pct_sum if stats_sorted else 0, pct_formatter=_fmt)
    _bold_row(tbl, last)
    _auto_fit_table(tbl)
    _compact_tbl(tbl, 24, 34 + 24 * min(tbl.rowCount(), 8))
    return tbl

# ── 테이블: 목별 집계 ────────────────────────────────────────────
def _order_tbl(species, sort_mode="taxa"):
    oc={}
    ok_map = _order_kor_map(species)
    for sp in species: 
        if sp.order not in oc: oc[sp.order]=0
        oc[sp.order]+=1
    total=len(species)
    tbl=_make_tbl(["목(영문)","목(한글)","종수","비율(%)"])
    tbl.setRowCount(len(oc)+1)
    sorted_oc = list(oc.items())
    if sort_mode == "desc":
        sorted_oc.sort(key=lambda x: (-x[1], x[0]))
    pct_sum = 0.0
    for ri, (eng, cnt) in enumerate(sorted_oc):
        pct = cnt/total*100 if total else 0
        tbl.setItem(ri,0,_item(eng, Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri,1,_item(ok_map.get(eng, eng), Qt.AlignLeft|Qt.AlignVCenter))
        tbl.setItem(ri,2,_item(cnt))
        tbl.setItem(ri,3,_item(_fmt(pct)))
        pct_sum += round(pct, SETTINGS.decimal)
    last=len(oc)
    tbl.setItem(last,0,_item("합계")); tbl.setItem(last,1,_item(""))
    tbl.setItem(last,2,_item(total))
    _set_total_pct_cell(tbl, last, 3, pct_sum if oc else 0, pct_formatter=_fmt)
    _bold_row(tbl,last); _auto_fit_table(tbl); return tbl

# ── 테이블: 다양성 지수 ──────────────────────────────────────────
def _div_tbl(div, species, taxon="fish"):
    ok_map = _order_kor_map(species)
    # 어류는 우점도 미포함
    if taxon == "fish":
        rows=[("종다양도지수(H')",f"{div.shannon_h:.2f}"),("균등도지수(EI)",f"{div.evenness_e:.2f}"),
              ("우점목",ok_map.get(div.dominant_order, div.dominant_order)),
              ("준우점목",ok_map.get(div.subdominant_order, div.subdominant_order))]
    else:
        rows=[("종다양도지수(H')",f"{div.shannon_h:.2f}"),("균등도지수(EI)",f"{div.evenness_e:.2f}"),
              ("우점도지수(DI)",f"{div.dominance_di:.2f}"),("우점목",ok_map.get(div.dominant_order, div.dominant_order)),
              ("준우점목",ok_map.get(div.subdominant_order, div.subdominant_order))]
    tbl=_make_tbl(["지수","값"]); tbl.setRowCount(len(rows))
    for ri,(l,v) in enumerate(rows):
        tbl.setItem(ri,0,_item(l,Qt.AlignLeft|Qt.AlignVCenter)); tbl.setItem(ri,1,_item(v))
    _auto_fit_table(tbl); _tbl_auto_height(tbl); return tbl

# ── 테이블: 종 목록 ──────────────────────────────────────────────
def _sp_tbl(species, rns):
    ok_map = _order_kor_map(species)
    site_labels=[_prn(r)[2] for r in rns]
    headers=["목(한글)","과명","국명","학명"]+site_labels+["합계","RA(%)"]
    tbl=_make_tbl(headers)
    rows=[]
    for sp in species:
        total=sum(_int(sp.rounds.get(r,0)) for r in rns)
        if total>0: rows.append([sp,total])
    rows.sort(key=lambda x:-x[1])
    grand=sum(t for _,t in rows)
    tbl.setRowCount(len(rows)+1)
    for ri, (sp, total) in enumerate(rows):
        pct = total/grand*100 if grand else 0
        ci=0
        tbl.setItem(ri,ci,_item(ok_map.get(sp.order, sp.order), Qt.AlignLeft|Qt.AlignVCenter)); ci+=1
        tbl.setItem(ri,ci,_item(sp.family or "",   Qt.AlignLeft|Qt.AlignVCenter)); ci+=1
        tbl.setItem(ri,ci,_item(sp.kor_name or "", Qt.AlignLeft|Qt.AlignVCenter)); ci+=1
        tbl.setItem(ri,ci,_item(sp.sci_name or "", Qt.AlignLeft|Qt.AlignVCenter)); ci+=1
        for r in rns:
            v=_int(sp.rounds.get(r,0)); tbl.setItem(ri,ci,_item(v if v else "")); ci+=1
        tbl.setItem(ri,ci,_item(total)); ci+=1
        tbl.setItem(ri,ci,_item(_fmt(pct)))
    last=len(rows)
    tbl.setItem(last,0,_item("합계"))
    for x in range(1,4): tbl.setItem(last,x,_item(""))
    for ci_off,r in enumerate(rns):
        tbl.setItem(last,4+ci_off,_item(sum(_int(sp.rounds.get(r,0)) for sp,_ in rows)))
    tbl.setItem(last,4+len(rns),_item(grand))
    tbl.setItem(last,4+len(rns)+1,_item(_fmt(100.0) if grand else ""))
    _bold_row(tbl,last); _auto_fit_table(tbl); return tbl

# ── 차트: 목별 파이 ──────────────────────────────────────────────
def _draw_order_pie(canvas, tbl_obj):
    if not _MPL: return
    _apply_mpl()
    d = _extract_pie_data(tbl_obj, 1, 3)
    if not d: return
    labels=list(d.keys()); sizes=list(d.values())
    cols=_series_palette(len(labels), canvas)
    ax=canvas._fig.clf(); ax=canvas._fig.add_subplot(111)
    def exact_autopct(p):
        val = p * sum(sizes) / 100
        return f"{val:.{SETTINGS.decimal}f}%" if val >= 3 else ""

    wedges,_,_=ax.pie(sizes,labels=None,colors=cols,
                      autopct=exact_autopct,
                      startangle=SETTINGS.pie_start_angle,
                      counterclock=False,
                      pctdistance=1-SETTINGS.pie_label_offset,
                      radius=SETTINGS.pie_radius)
    ax.legend(wedges,labels,loc="center left",bbox_to_anchor=(1,0,0.5,1),
              fontsize=SETTINGS.pie_fontsize)
    ax.set_title("목별 구성",fontsize=11,fontweight="bold")
    canvas._fig.tight_layout(); canvas.draw()


# ── 차트: 지점별 막대 ────────────────────────────────────────────
def _draw_site_bar(canvas, tbl_obj, rns, title="지점별 현황"):
    if not _MPL:
        return
    tbl = _get_tbl(tbl_obj)
    if not tbl: return
    data = []
    for ci_off, r in enumerate(rns):
        site = _prn(r)[2]
        if site in ("종합", ""): continue
        c = 4 + ci_off
        sp_cnt = sum(1 for ri in range(tbl.rowCount()-1) if _int(tbl.item(ri, c).text()) > 0)
        ind_cnt = _int(tbl.item(tbl.rowCount()-1, c).text())
        if sp_cnt > 0: data.append((site, sp_cnt, ind_cnt))
    if not data: return

    _apply_mpl()
    ax = canvas._fig.clf(); ax = canvas._fig.add_subplot(111)
    lbs = [d[0] for d in data]
    sp = [d[1] for d in data]
    ind = [d[2] for d in data]
    fs = canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize)
    rot = canvas._cfg.get("x_label_rot", SETTINGS.x_label_rot)
    grid_on = canvas._cfg.get("grid_on", SETTINGS.grid_on)
    grid_color = canvas._cfg.get("grid_color", SETTINGS.grid_color)
    bar_color = canvas._cfg.get("bar_color", SETTINGS.bar_color)
    line_color = canvas._cfg.get("line_color", SETTINGS.line_color)
    bar_v_width = canvas._cfg.get("bar_v_width", SETTINGS.bar_v_width)
    x = list(range(len(lbs)))
    w = max(0.12, min(0.45, bar_v_width / 2))
    ax.bar([i - w for i in x], sp, width=w, label="종수", color=bar_color, alpha=0.9)
    ax.bar([i for i in x], ind, width=w, label="개체수", color=line_color, alpha=0.9)
    for i, v in enumerate(sp):
        if v:
            ax.text(i - w + w / 2, v + 0.2, str(v), ha="center", va="bottom", fontsize=fs)
    for i, v in enumerate(ind):
        if v:
            ax.text(i + w / 2, v + 0.2, str(v), ha="center", va="bottom", fontsize=fs)
    ax.set_xticks(x)
    ax.set_xticklabels(lbs, rotation=rot, ha="right" if rot else "center")
    _apply_axes_common(ax, title=title, ylabel="", xlabel="", fs=fs)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=fs, frameon=False)
    if grid_on:
        ax.grid(axis="y", linestyle="--", alpha=0.5, color=grid_color)
    _apply_bar_margins(canvas._fig, canvas); _apply_graph_scale(canvas._fig, canvas); canvas.draw()

def _draw_div_bar(canvas, tbl_obj):
    if not _MPL:
        return
    tbl = _get_tbl(tbl_obj)
    if not tbl: return
    _apply_mpl()
    ax = canvas._fig.clf(); ax = canvas._fig.add_subplot(111)
    fs = canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize)
    grid_on = canvas._cfg.get("grid_on", SETTINGS.grid_on)
    grid_color = canvas._cfg.get("grid_color", SETTINGS.grid_color)
    div_bar_width = canvas._cfg.get("div_bar_width", SETTINGS.div_bar_width)
    div_bar_gap = canvas._cfg.get("div_bar_gap", SETTINGS.div_bar_gap)
    labels = ["종다양도지수(H')", "균등도지수(E)", "우점도(DI)"]
    vals = []
    for r in range(3):
        try: vals.append(float(tbl.item(r, 1).text().replace(',','')))
        except: vals.append(0.0)
        
    if tbl.rowCount() == 4:
        labels = ["종다양도지수(H')", "균등도지수(EI)"]
        vals = vals[:2]
        
    _cm = getattr(SETTINGS, "color_mode", "auto")
    if _cm == "gray":
        cols = _gray_palette(len(vals))
    elif _cm == "solid":
        cols = [getattr(SETTINGS, "bar_color", "#4472C4")] * len(vals)
    else:
        cols = [SETTINGS.div_color_1, SETTINGS.div_color_2, SETTINGS.div_color_3][:len(vals)]
    _n = len(vals)
    _span = (_n - 1) * div_bar_gap
    _offset = -_span / 2
    x = [i * div_bar_gap + _offset for i in range(_n)]
    bars = ax.bar(x, vals, color=cols, alpha=0.9, width=div_bar_width)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005, f"{v:.2f}", ha="center", va="bottom", fontsize=fs)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    _fixed_half = (_n - 1) * 0.5 + 0.5
    _axis_half = max(_fixed_half, _span / 2 + div_bar_width / 2 + 0.1)
    ax.set_xlim(-_axis_half, _axis_half)
    _apply_axes_common(ax, title="다양성 지수", ylabel=getattr(SETTINGS, "y_axis_title", "지수 값"), xlabel="", fs=fs)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_bounds(-_axis_half, _axis_half)
    ax.spines["bottom"].set_zorder(4)
    ax.spines["left"].set_zorder(4)
    if grid_on:
        ax.grid(axis="y", linestyle="--", alpha=0.5, color=grid_color)
    _apply_bar_margins(canvas._fig, canvas); _apply_graph_scale(canvas._fig, canvas); canvas.draw()

def _draw_fish_dom_bar(canvas, tbl_obj, title="우점도"):
    if not _MPL:
        return
    tbl = _get_tbl(tbl_obj)
    if not tbl: return
    rows = []
    for r in range(tbl.rowCount() - 1):  # 마지막 합계 행 제외
        lbl = tbl.item(r, 1).text().strip()
        if not lbl:
            lbl = tbl.item(r, 0).text().strip()
        try: cnt = _int(tbl.item(r, 2).text().replace(",", ""))
        except: cnt = 0
        try: pct = float(tbl.item(r, 3).text())
        except: pct = 0.0
        rows.append((lbl, cnt, pct))
    if not rows: return

    def _is_others_label(label):
        s = str(label or "").strip()
        return s.startswith("기타(") or s == "기타"

    bar_sort = canvas._cfg.get("bar_sort", getattr(SETTINGS, "bar_sort", "desc"))
    if bar_sort == "desc":
        rows.sort(key=lambda x: (_is_others_label(x[0]), -x[2], x[0]))
    elif bar_sort == "asc":
        rows.sort(key=lambda x: (_is_others_label(x[0]), x[2], x[0]))

    _apply_mpl()
    ax = canvas._fig.clf(); ax = canvas._fig.add_subplot(111)
    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    pcts = [r[2] for r in rows]
    bar_horiz = canvas._cfg.get("bar_horiz", canvas._cfg.get("orientation", "horizontal") == "horizontal")
    bar_h_height = canvas._cfg.get("bar_h_height", SETTINGS.bar_h_height)
    bar_v_width = canvas._cfg.get("bar_v_width", SETTINGS.bar_v_width)
    show_count_label = canvas._cfg.get("bar_count_label_inside", getattr(SETTINGS, "bar_count_label_inside", False))
    fs = canvas._cfg.get("bar_fontsize", SETTINGS.bar_fontsize)
    show_legend = canvas._cfg.get("show_legend", getattr(SETTINGS, "show_legend", True))
    colors = _series_palette(len(labels), canvas)
    grid_on = canvas._cfg.get("grid_on", SETTINGS.grid_on)
    grid_color = canvas._cfg.get("grid_color", SETTINGS.grid_color)
    x_label_rot = canvas._cfg.get("x_label_rot", SETTINGS.x_label_rot)
    decimal = canvas._cfg.get("decimal", SETTINGS.decimal)
    axis_label = getattr(SETTINGS, "y_axis_title", "우점도(%)")
    chart_title = str(getattr(SETTINGS, "chart_title", "") or "").strip() or title
    max_pct = max(pcts) if pcts else 1
    cfg_axis_min = float(canvas._cfg.get("axis_min", SETTINGS.axis_min) or 0)
    cfg_axis_max = float(canvas._cfg.get("axis_max", SETTINGS.axis_max) or 0)
    cfg_axis_step = float(canvas._cfg.get("axis_step", SETTINGS.axis_step) or 0)
    auto_max, auto_step = _get_nice_bounds(max_pct)
    axis_min = cfg_axis_min if cfg_axis_min < (cfg_axis_max or auto_max) else 0
    axis_max = cfg_axis_max if cfg_axis_max > 0 else auto_max
    axis_step = cfg_axis_step if cfg_axis_step > 0 else auto_step

    def _axis_ticks():
        if axis_step <= 0:
            return []
        ticks = []
        cur = axis_min
        guard = 0
        while cur <= axis_max + axis_step * 0.001 and guard < 1000:
            ticks.append(round(cur, 6))
            cur += axis_step
            guard += 1
        if ticks and ticks[-1] < axis_max:
            ticks.append(round(axis_max, 6))
        return ticks

    if bar_horiz:
        y = list(range(len(labels)))
        bars = ax.barh(y, pcts, height=bar_h_height, color=colors, alpha=0.9, label="우점도(%)")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=fs)
        ax.tick_params(axis="x", labelsize=fs)
        ax.set_xlim(axis_min, axis_max)
        ax.set_xticks(_axis_ticks())
        ax.invert_yaxis()
        for i, (bar, cnt, pct) in enumerate(zip(bars, counts, pcts)):
            if show_count_label:
                ax.text(axis_max * 0.012, i, f"{cnt:,}", ha="left", va="center", fontsize=max(6, fs - 1), fontweight="bold")
            ax.text(bar.get_width() + axis_max * 0.015, bar.get_y() + bar.get_height() / 2, f"{pct:.{decimal}f}%", ha="left", va="center", fontsize=max(6, fs - 1), fontweight="bold")
        _apply_axes_common(ax, title=chart_title, ylabel="", xlabel=axis_label, fs=fs)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(True)
        ax.spines["bottom"].set_visible(True)
        if grid_on:
            ax.grid(axis="x", linestyle="--", alpha=0.5, color=grid_color)
        if show_legend:
            ax.legend(loc="upper right", frameon=False, fontsize=max(7, fs - 1))
    else:
        x = list(range(len(labels)))
        bars = ax.bar(x, pcts, width=bar_v_width, color=colors, alpha=0.9, label="우점도(%)")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=x_label_rot, ha="center" if x_label_rot == 0 else "right", fontsize=fs)
        ax.tick_params(axis="y", labelsize=fs)
        ax.set_ylim(axis_min, axis_max)
        ax.set_yticks(_axis_ticks())
        for bar, cnt, pct in zip(bars, counts, pcts):
            if show_count_label:
                ax.text(bar.get_x() + bar.get_width() / 2, axis_max * 0.015, f"{cnt:,}", ha="center", va="bottom", fontsize=max(6, fs - 1), fontweight="bold")
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + axis_max * 0.015, f"{pct:.{decimal}f}%", ha="center", va="bottom", fontsize=max(6, fs - 1), fontweight="bold")
        _apply_axes_common(ax, title=chart_title, ylabel=axis_label, xlabel="", fs=fs)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(True)
        ax.spines["bottom"].set_visible(True)
        if grid_on:
            ax.grid(axis="y", linestyle="--", alpha=0.5, color=grid_color)
        if show_legend:
            ax.legend(loc="upper right", frameon=False, fontsize=max(7, fs - 1))
    _apply_bar_margins(canvas._fig, canvas); _apply_graph_scale(canvas._fig, canvas); canvas.draw()

def _aqua_counts_str(species, taxon="") -> str:
    """SETTINGS 레벨 설정에 따라 수생생물 분류군 수 문자열 생성."""
    parts = []
    if taxon == "benthos" and SETTINGS.sent_show_phylum:
        phylum_n = len(set(getattr(sp, "phylum", "") for sp in species if getattr(sp, "phylum", "")))
        parts.append(f"{phylum_n}문")
    if taxon == "benthos" and SETTINGS.sent_show_class:
        class_n = len(set(getattr(sp, "class_name", "") for sp in species if getattr(sp, "class_name", "")))
        parts.append(f"{class_n}강")
    if taxon == "benthos" or SETTINGS.sent_show_order:
        parts.append(f"{len(set(sp.order for sp in species if sp.order))}목")
    if taxon == "benthos" or SETTINGS.sent_show_family:
        parts.append(f"{len(set(sp.family for sp in species if sp.family))}과")
    if SETTINGS.sent_show_genus:
        parts.append(f"{len(set(sp.sci_name.split()[0] for sp in species if sp.sci_name and sp.sci_name.split()))}속")
    if SETTINGS.sent_show_species or taxon == "benthos":
        parts.append(f"{len(species)}종")
    return " ".join(parts) if parts else f"{len(species)}종"


def _sentence(stats, species, rns, prot_sheet=None, survey="field", force_norm=False, tbl_pcts=None):
    S   = SETTINGS
    kor = {"fish": "어류", "benthos": "저서성 대형 무척추동물"}.get(stats.taxon, stats.taxon)
    ind = sum(sum(_int(sp.rounds.get(r, 0)) for r in _detail_rns(rns)) for sp in species) if rns else sum(sp.total for sp in species)
    div = _calc_local_div(species, rns)

    survey_prefix = _survey_prefix(survey, rns)

    counts = _aqua_counts_str(species, stats.taxon)
    prot_n, prot_clause = _prot_list_graded(stats.taxon, prot_sheet, species)
    disturb_n, disturb_clause = _ecosystem_disturber_list(prot_sheet, species)
    
    is_field = (survey == "field")
    s1_mid = S.field_s1_mid if is_field else S.lit_s1_mid
    s1_end = S.field_s1_end if is_field else S.lit_s1_end
    
    s1_mid_josa = _resolve_iga(s1_mid, f"{ind:,}개체")
        
    s1_end_base = S.end_field if is_field else S.end_lit
    div_end_base = S.end_ana

    prot_none = S.prot_none_field if is_field else S.prot_none_lit
    prot_part = f"{prot_clause} {prot_n}종{s1_end}" if prot_n else f"{prot_none}"
    if disturb_n:
        if prot_n:
            prot_part = f"{prot_clause} {prot_n}종, 생태계교란 생물은 {disturb_clause} {disturb_n}종{s1_end}"
        else:
            prot_part = f"{_prot_none_contrast(prot_none)}, 생태계교란 생물은 {disturb_clause} {disturb_n}종{s1_end}"

    if is_field:
        is_qual_only = (ind == 0)
        lines = []
        if stats.taxon == "fish":
            if is_qual_only:
                lines.append(f"{survey_prefix} 결과, {kor}는 총 {counts}{_resolve_iga(s1_mid, counts)} 법정보호종은 {prot_part}")
            else:
                lines.append(f"{survey_prefix} 결과, {kor}는 총 {counts} {ind:,}개체{s1_mid_josa} 법정보호종은 {prot_part}")

            fams = _family_counts(species)
            kor_map = _family_kor_from_species(species)
            fam_items = sorted(fams.items(), key=lambda x: (-x[1], x[0]))
            fam_counts = [cnt for _, cnt in fam_items]
            fam_total = sum(fam_counts)
            # tbl_pcts가 있으면 표의 보정된 비율 사용, 아니면 계산
            if isinstance(tbl_pcts, dict):
                fam_pcts = tbl_pcts.get("family")
            else:
                fam_pcts = tbl_pcts
            if not fam_pcts and force_norm:
                fam_pcts, _ = _apply_ratio_correction(_normalized_percentages(fam_counts))
            elif not fam_pcts:
                fam_pcts = [c / fam_total * 100 if fam_total else 0 for c in fam_counts]

            fam_desc = _family_desc_from_items(fam_items, fam_pcts, kor_map)
            lines.append(f"분류군별 출현종수 분석 결과, {fam_desc}의 순으로 {div_end_base}")

            if not is_qual_only:
                _dom_pct = tbl_pcts.get("dominance_threshold", SETTINGS.dom_pct) if isinstance(tbl_pcts, dict) else SETTINGS.dom_pct
                dom_rows_from_tbl = tbl_pcts.get("dominance") if isinstance(tbl_pcts, dict) else None
                if dom_rows_from_tbl:
                    total_ind = sum(row["count"] for row in dom_rows_from_tbl)
                    dom = dom_rows_from_tbl[0] if dom_rows_from_tbl else None
                    sub = dom_rows_from_tbl[1] if len(dom_rows_from_tbl) > 1 and not dom_rows_from_tbl[1]["label"].startswith("기타(") else None
                    rest_start = 2 if sub else 1
                    rest_rows = dom_rows_from_tbl[rest_start:]
                    rest_items = [(row["label"], row["count"], row["pct"]) for row in rest_rows if not row["label"].startswith("기타(")]
                    rest_parts = _labels_count_pct_desc(rest_items, "개체")
                    others_row = next((row for row in dom_rows_from_tbl if row["label"].startswith("기타(")), None)
                    others_str = f"{others_row['label']}은 상대풍부도 {_pct(_dom_pct)} 미만" if others_row else ""
                    dom_desc = _resolve_iga(f"{dom['label']}이(가) {dom['count']:,}개체({_pct(dom['pct'])})로 우점종", dom['label']) if dom else ""
                    sub_desc = _resolve_iga(f"{sub['label']}이(가) {sub['count']:,}개체({_pct(sub['pct'])})로 아우점종", sub['label']) if sub else ""
                else:
                    all_dom_rows = _fish_dom_rows(species, rns, len(species) or 1, None, force_norm=force_norm)
                    total_ind = sum(c for _, c, _ in all_dom_rows)
                    above = [r for r in all_dom_rows if r[2] >= _dom_pct]
                    below = [r for r in all_dom_rows if r[2] < _dom_pct]
                    dom = above[0] if above else None
                    sub = above[1] if len(above) > 1 else None

                    dom_label = (dom[0].kor_name or dom[0].sci_name) if dom else ""
                    sub_label = (sub[0].kor_name or sub[0].sci_name) if sub else ""
                    dom_desc = _resolve_iga(f"{dom_label}이(가) {dom[1]:,}개체({_pct(dom[2])})로 우점종", dom_label) if dom else ""
                    sub_desc = _resolve_iga(f"{sub_label}이(가) {sub[1]:,}개체({_pct(sub[2])})로 아우점종", sub_label) if sub else ""
                    rest_sorted = sorted(above[2:], key=lambda x: (-x[1], x[0].kor_name or x[0].sci_name))
                    rest_items = [((sp.kor_name or sp.sci_name), indiv, pct) for sp, indiv, pct in rest_sorted]
                    rest_parts = _labels_count_pct_desc(rest_items, "개체")
                    others_n   = len(below)
                    others_pct = sum(p for _, _, p in below)
                    others_str = f"기타 {others_n}종은 상대풍부도 {_pct(_dom_pct)} 미만" if others_n > 0 else ""
                rest_desc = ", ".join(rest_parts)
                if rest_desc:
                    rest_desc = "그 외 " + rest_desc
                tail_parts = [part for part in (rest_desc, others_str) if part]
                tail_desc = ", ".join(tail_parts)

                lead_desc = f"상대풍부도 분석 결과, {dom_desc}"
                if sub_desc:
                    lead_desc += f", {sub_desc}"

                conn_verb = S.order_verb_f.strip()
                if tail_desc:
                    lines.append(f"{lead_desc}으로 {conn_verb}, {tail_desc}의 순으로 {div_end_base}")
                else:
                    lines.append(f"{lead_desc}으로 {div_end_base}")

                _idx_sent = _index_range_sentence(species, rns, tail=S.div_end, include_range_word=True)
                if _idx_sent is not None:
                    lines.append(_idx_sent)

        else:
            if is_qual_only:
                lines.append(f"{survey_prefix} 결과, {kor}은 총 {counts}{_resolve_iga(s1_mid, counts)} 법정보호종은 {prot_part}")
            else:
                lines.append(f"{survey_prefix} 결과, {kor}은 총 {counts} {ind:,}개체{s1_mid_josa} 법정보호종은 {prot_part}")

            bstats_sp = _benthos_group_stats(species, rns)
            counts_sp = [x["species"] for x in bstats_sp]
            total_sp = sum(counts_sp)
            pcts_from_tbl_sp = tbl_pcts.get("species") if isinstance(tbl_pcts, dict) else None
            if pcts_from_tbl_sp:
                pcts_sp = pcts_from_tbl_sp
            elif force_norm:
                pcts_sp, _ = _apply_ratio_correction(_normalized_percentages(counts_sp))
            else:
                pcts_sp = [c / total_sp * 100 if total_sp else 0 for c in counts_sp]
            non_ins_sp = sum(x["species"] for x in bstats_sp if x["eng"] == "Non-insecta")
            non_ins_pct = 0.0
            # 곤충류 종수 데이터를 내림차순으로 정렬
            ins_rows_sp = [(row, pct) for row, pct in zip(bstats_sp, pcts_sp) if row["eng"] != "Non-insecta" and row["species"] > 0]
            ins_rows_sp.sort(key=lambda x: (-x[0]["species"], x[0]["kor"]))
            ins_parts = []
            for row, pct in ins_rows_sp:
                ins_parts.append(_resolve_iga(f"{row['kor']}이(가) {row['species']}종({_pct(pct)})", row['kor']))
            # non_ins_pct 업데이트
            for row, pct in zip(bstats_sp, pcts_sp):
                if row["eng"] == "Non-insecta": non_ins_pct = pct
            ins_desc = ", ".join(ins_parts)

            lines.append(f"분류군별로 출현종수 분석 결과, 비곤충류는 {non_ins_sp}종({_pct(non_ins_pct)}), 곤충류는 {ins_desc}{_josa(ins_desc, '으로로')} {div_end_base}")

            if not is_qual_only:
                bstats_ind = _benthos_group_stats(species, rns)
                counts_ind = [x["individuals"] for x in bstats_ind]
                total_ind = sum(counts_ind)
                pcts_from_tbl_ind = tbl_pcts.get("individuals") if isinstance(tbl_pcts, dict) else None
                if pcts_from_tbl_ind:
                    pcts_ind = pcts_from_tbl_ind
                elif force_norm:
                    pcts_ind, _ = _apply_ratio_correction(_normalized_percentages(counts_ind))
                else:
                    pcts_ind = [c / total_ind * 100 if total_ind else 0 for c in counts_ind]
                non_ins_ind = sum(x["individuals"] for x in bstats_ind if x["eng"] == "Non-insecta")
                non_ins_ind_pct = 0.0
                # 곤충류 개체수 데이터를 내림차순으로 정렬
                ins_rows_ind = [(row, pct) for row, pct in zip(bstats_ind, pcts_ind) if row["eng"] != "Non-insecta" and row["individuals"] > 0]
                ins_rows_ind.sort(key=lambda x: (-x[0]["individuals"], x[0]["kor"]))
                ins_ind_parts = []
                for row, pct in ins_rows_ind:
                    ins_ind_parts.append(_resolve_iga(f"{row['kor']}이(가) {row['individuals']:,}개체({_pct(pct)})", row['kor']))
                for row, pct in zip(bstats_ind, pcts_ind):
                    if row["eng"] == "Non-insecta": non_ins_ind_pct = pct
                ins_ind_desc = ", ".join(ins_ind_parts)

                lines.append(f"분류군별 출현현황을 살펴보면, 비곤충류는 {non_ins_ind:,}개체({_pct(non_ins_ind_pct)}), 곤충류는 {ins_ind_desc}의 순으로 {div_end_base}")

                dom_rows = _fish_dom_rows(species, rns, 2, None, force_norm=force_norm)
                total_ind_dom = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in _detail_rns(rns))
                dom = dom_rows[0] if dom_rows else None
                sub = dom_rows[1] if len(dom_rows) > 1 else None

                if dom:
                    dom_line = f"우점종은 {(dom[0].kor_name or dom[0].sci_name)}({dom[1]:,}개체, {_pct(dom[2])})"
                    if sub:
                        dom_line += f", 아우점종은 {(sub[0].kor_name or sub[0].sci_name)}({sub[1]:,}개체, {_pct(sub[2])})로 {s1_end_base}"
                    else:
                        dom_line += f"로 {s1_end_base}"
                    lines.append(dom_line)

                _idx_sent = _index_range_sentence(species, rns, tail=S.div_end, include_range_word=False)
                if _idx_sent is not None:
                    lines.append(_idx_sent)

        return _apply_title("\n".join(lines), S.sentence_title)
    else:
        lines = [f"{survey_prefix} 결과, {kor}은 총 {counts}{s1_mid} 법정보호종은 {prot_part}"]
        result_prefix = lit_result_prefix(rns, survey_prefix, comma=True)
        if result_prefix != f"{survey_prefix} 결과,":
            lines[0] = lines[0].replace(f"{survey_prefix} 결과,", result_prefix, 1)
        return _apply_title("\n".join(lines), S.sentence_title)

def _txtbox(text):
    t=QPlainTextEdit(); t.setReadOnly(True); t.setFixedHeight(110)
    t.setStyleSheet(
        f"QPlainTextEdit{{background:{_BG};{BD};border-radius:8px;{FF_KR};font-size:12px;padding:6px;}}")
    t.setPlainText(text); return t

def _sent_txtbox(stats, species, rns, prot_sheet=None, survey="field", force_norm_ref=None, tbl_ref=None,
                 total_rns=None, total_species=None):
    """새로고침 및 복사 버튼이 포함된 문장 위젯.

    tbl_ref: (표객체, pct_col) 튜플 또는 None
             비율 보정 후 표의 현재값을 문장에 반영하기 위해 필요
    """
    w = QWidget()
    w.setObjectName("sentWrap")
    w.setStyleSheet("QWidget#sentWrap{background:#FFFFFF;}")
    lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)

    def _get_tbl_pcts():
        """표에서 현재 비율값 읽기"""
        if not tbl_ref:
            return None
        if isinstance(tbl_ref, dict):
            out = {}
            for key, ref in tbl_ref.items():
                if callable(ref):
                    out[key] = ref()
                    continue
                if len(ref) >= 4:
                    tbl, label_col, pct_col, cnt_col = ref[:4]
                    vals = []
                    for r in range(tbl.rowCount() - 1):
                        label_it = tbl.item(r, label_col)
                        pct_it = tbl.item(r, pct_col)
                        cnt_it = tbl.item(r, cnt_col)
                        if not pct_it:
                            continue
                        label = label_it.text().strip() if label_it else ""
                        pct_txt = pct_it.text().replace("%", "").replace(",", "").strip()
                        cnt_txt = cnt_it.text().replace(",", "").strip() if cnt_it else "0"
                        try:
                            pct_val = float(pct_txt)
                        except ValueError:
                            pct_val = 0.0
                        try:
                            cnt_val = int(float(cnt_txt))
                        except ValueError:
                            cnt_val = 0
                        vals.append({"label": label, "pct": pct_val, "count": cnt_val})
                else:
                    tbl, pct_col = ref
                    vals = []
                    for r in range(tbl.rowCount() - 1):
                        it = tbl.item(r, pct_col)
                        if it:
                            txt = it.text().replace("%", "").replace(",", "").strip()
                            try:
                                vals.append(float(txt))
                            except ValueError:
                                vals.append(0.0)
                if vals:
                    out[key] = vals
            return out or None
        tbl, pct_col = tbl_ref
        pcts = []
        for r in range(tbl.rowCount() - 1):  # 마지막 합계행 제외
            it = tbl.item(r, pct_col)
            if it:
                txt = it.text().replace("%", "").replace(",", "").strip()
                try:
                    pcts.append(float(txt))
                except ValueError:
                    pcts.append(0.0)
        return pcts if pcts else None

    def _get_s():
        fn = force_norm_ref[0] if force_norm_ref else False
        tbl_pcts = _get_tbl_pcts()
        group_s = _sentence(stats, species, rns, prot_sheet, survey, force_norm=fn, tbl_pcts=tbl_pcts)
        if total_rns and total_species:
            total_s = _sentence(stats, total_species, total_rns, prot_sheet, survey, force_norm=False)
            return "\n".join(filter(None, [total_s, group_s]))
        return group_s

    txt = _txtbox(_get_s())
    txt._sent_refresh_fn = lambda: txt.setPlainText(_get_s())
    w._sent_refresh_fn   = txt._sent_refresh_fn   # 외부에서 w로 접근 가능하게

    btn_copy = QPushButton("📋  복사"); btn_copy.setFixedHeight(30)
    btn_copy.setStyleSheet(_COPY_BTN_QSS)
    def _do_copy():
        QApplication.clipboard().setText(txt.toPlainText())
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_copy)
    btn_copy.clicked.connect(_do_copy)

    br = QHBoxLayout(); br.addWidget(btn_copy); br.addStretch()
    lay.addLayout(br); lay.addWidget(txt)
    return w

def _fish_panel(stats, species, rns, prot_sheet=None, survey="field"):
    w=QWidget(); w.setStyleSheet(_QSS)
    lay=QVBoxLayout(w); lay.setContentsMargins(6,6,6,6); lay.setSpacing(8)

    spl=QSplitter(Qt.Horizontal); spl.setChildrenCollapsible(False)
    is_norm_sent = [False]
    txt_sent_ref = [None]

    def _on_norm():
        is_norm_sent[0] = True
        if txt_sent_ref[0]: txt_sent_ref[0]._sent_refresh_fn()

    grp_f=QGroupBox("과별 출현비율"); lf=QVBoxLayout(grp_f)
    
    # 정렬 모드: 기본값 "desc"
    _fam_sort_mode = ["desc"]
    
    def _rebuild_fam_tbl():
        fish_fam_tbl = _fish_family_tbl(species, _fam_sort_mode[0])
        _bind_table_pct_refresh(fish_fam_tbl, 3, cnt_col=2, pct_formatter=_fmt)
        _replace_tbl(grp_f, fish_fam_tbl)
        if pie_cv._refresh_cb: pie_cv._refresh_cb()
    
    fish_fam_tbl = _fish_family_tbl(species)
    _bind_table_pct_refresh(fish_fam_tbl, 3, cnt_col=2, pct_formatter=_fmt)
    
    # 정렬 버튼
    btn_sort_desc = QPushButton("↓ 내림차순"); btn_sort_desc.setFixedHeight(24)
    btn_sort_desc.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa = QPushButton("☰ 분류군순"); btn_sort_taxa.setFixedHeight(24)
    btn_sort_taxa.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row = QHBoxLayout(); _sort_row.setContentsMargins(0, 0, 0, 2); _sort_row.setSpacing(4)
    _sort_row.addWidget(btn_sort_desc); _sort_row.addWidget(btn_sort_taxa); _sort_row.addStretch()
    
    def _on_sort_desc():
        _fam_sort_mode[0] = "desc"; _rebuild_fam_tbl()
    def _on_sort_taxa():
        _fam_sort_mode[0] = "taxa"; _rebuild_fam_tbl()
    btn_sort_desc.clicked.connect(_on_sort_desc)
    btn_sort_taxa.clicked.connect(_on_sort_taxa)
    
    lf.setContentsMargins(6,12,6,6)
    lf.insertLayout(0, _sort_row)
    _add_tbl_with_btn(lf, fish_fam_tbl, pct_col=3, cnt_col=2, on_normalize=lambda: (pie_cv._refresh_cb() if pie_cv._refresh_cb else None, _on_norm()))
    spl.addWidget(grp_f)

    pie_cv=PieCanvas()
    pie_cv._setting_mode="pie"
    pie_cv._preview_data_provider = lambda: _extract_pie_data(grp_f, 1, 3)
    pie_cv.draw_pie(pie_cv._preview_data_provider())
    pie_cv._refresh_cb = lambda: pie_cv.draw_pie(pie_cv._preview_data_provider())
    cv_grp = _wrap_cv_resizable("과별 출현비율", pie_cv)
    _pie_panel = _make_pie_settings_panel(pie_cv, cv_grp)
    _attach_title_to_cv(cv_grp, _pie_panel._title_controls)
    spl.addWidget(_make_settings_graph(_pie_panel, cv_grp))
    spl.setStretchFactor(0, 0); spl.setStretchFactor(1, 1)
    spl.setSizes([520, 1200])
    lay.addWidget(spl)

    # 우점도 섹션 제거 (어류는 우점도 필요 없음)
    grp_ra=QGroupBox("종별 상대풍부도"); lr=QVBoxLayout(grp_ra)
    
    # 정렬 모드
    _ra_sort_mode = ["desc"]
    
    def _rebuild_ra_tbl():
        fish_ra_tbl = _fish_ra_tbl(species, rns, _ra_sort_mode[0])
        _bind_table_pct_refresh(
            fish_ra_tbl,
            4,
            cnt_col=3,
            pct_formatter=lambda v: f"{float(v):.{SETTINGS.decimal}f}",
        )
        _replace_tbl(grp_ra, fish_ra_tbl)
    
    fish_ra_tbl = _fish_ra_tbl(species, rns)
    _bind_table_pct_refresh(
        fish_ra_tbl,
        4,
        cnt_col=3,
        pct_formatter=lambda v: f"{float(v):.{SETTINGS.decimal}f}",
    )
    
    # 정렬 버튼
    btn_sort_desc_ra = QPushButton("↓ 내림차순"); btn_sort_desc_ra.setFixedHeight(24)
    btn_sort_desc_ra.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa_ra = QPushButton("☰ 분류군순"); btn_sort_taxa_ra.setFixedHeight(24)
    btn_sort_taxa_ra.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row_ra = QHBoxLayout(); _sort_row_ra.setContentsMargins(0, 0, 0, 2); _sort_row_ra.setSpacing(4)
    _sort_row_ra.addWidget(btn_sort_desc_ra); _sort_row_ra.addWidget(btn_sort_taxa_ra); _sort_row_ra.addStretch()
    
    def _on_sort_desc_ra():
        _ra_sort_mode[0] = "desc"; _rebuild_ra_tbl()
    def _on_sort_taxa_ra():
        _ra_sort_mode[0] = "taxa"; _rebuild_ra_tbl()
    btn_sort_desc_ra.clicked.connect(_on_sort_desc_ra)
    btn_sort_taxa_ra.clicked.connect(_on_sort_taxa_ra)
    
    lr.setContentsMargins(6,12,6,6)
    lr.insertLayout(0, _sort_row_ra)
    _add_tbl_with_btn(lr, fish_ra_tbl, True)
    lay.addWidget(grp_ra, stretch=1)

    _is_qual_only = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in _detail_rns(rns)) == 0
    if _is_qual_only:
        qual_lbl = QLabel("※ 정성조사만 진행되었음")
        qual_lbl.setStyleSheet(f"{FF_KR}; font-size:12px; color:#D97706; padding:8px;")
        qual_lbl.setAlignment(Qt.AlignLeft)
        lay.addWidget(qual_lbl)

    def _refresh_sent_from_current_tbl():
        txt = txt_sent_ref[0]
        if txt and hasattr(txt, "_sent_refresh_fn"):
            txt._sent_refresh_fn()

    grp_s=QGroupBox("문장"); grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}"); sv=QVBoxLayout(grp_s)
    txt_sent = _sent_txtbox(stats, species, rns, prot_sheet, survey, force_norm_ref=is_norm_sent, tbl_ref=(fish_fam_tbl, 3))
    txt_sent_ref[0] = txt_sent
    sv.setContentsMargins(8,8,8,8); sv.addWidget(txt_sent)
    lay.addWidget(grp_s)

    # 기존 문장 위젯을 최신 표 참조(callable) 방식으로 교체
    txt_sent_new = _sent_txtbox(
        stats,
        species,
        rns,
        prot_sheet,
        survey,
        force_norm_ref=is_norm_sent,
        tbl_ref={
            "family": lambda: [
                float(((_get_tbl(grp_f).item(r, 3).text() if _get_tbl(grp_f).item(r, 3) else "0").replace("%", "").replace(",", "").strip()) or 0)
                for r in range(max((_get_tbl(grp_f).rowCount() if _get_tbl(grp_f) else 0) - 1, 0))
            ],
        },
    )
    txt_sent_ref[0] = txt_sent_new
    sv.removeWidget(txt_sent)
    txt_sent.setParent(None)
    sv.addWidget(txt_sent_new)

    _orig_rebuild_fam_tbl = _rebuild_fam_tbl
    def _rebuild_fam_tbl_with_sent():
        _orig_rebuild_fam_tbl()
        _refresh_sent_from_current_tbl()
    _rebuild_fam_tbl = _rebuild_fam_tbl_with_sent

    return w

def _benthos_panel(stats, species, rns=None, prot_sheet=None, survey="field", total_rns=None, total_species=None, parent_window=None):
    w = QWidget(); w.setStyleSheet(_QSS)
    lay = QVBoxLayout(w); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(8)

    gtabs = QTabWidget(); gtabs.setDocumentMode(True)
    gtabs.setStyleSheet(_tab_qss(True))

    is_norm_sent = [False]
    txt_sent_ref = [None]

    def _on_norm(pie):
        if pie._refresh_cb: pie._refresh_cb()
        is_norm_sent[0] = True
        if txt_sent_ref[0]: txt_sent_ref[0]._sent_refresh_fn()

    # 정렬 모드
    _benthos_sort_mode = ["taxa"]
    
    # ── Tab1: 분류군 현황 - 종수 ──────────────────────────────────────
    def _rebuild_benthos_sp_tbl():
        tbl_benthos_sp = _benthos_tbl(species, "species", rns, _benthos_sort_mode[0])
        _bind_table_pct_refresh(tbl_benthos_sp, 3, cnt_col=2, pct_formatter=_fmt)
        _replace_tbl(grp_s, tbl_benthos_sp)
        if pie_s._refresh_cb: pie_s._refresh_cb()
    
    def _rebuild_benthos_ind_tbl():
        tbl_benthos_ind = _benthos_tbl(species, "individuals", rns, _benthos_sort_mode[0])
        _bind_table_pct_refresh(tbl_benthos_ind, 3, cnt_col=2, pct_formatter=_fmt)
        _replace_tbl(grp_i, tbl_benthos_ind)
        if pie_i._refresh_cb: pie_i._refresh_cb()

    grp_s = QGroupBox("분류군(목별) 현황 - 종수"); ls = QVBoxLayout(grp_s)

    # 정렬 버튼
    btn_sort_desc_sp = QPushButton("↓ 내림차순"); btn_sort_desc_sp.setFixedHeight(24)
    btn_sort_desc_sp.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa_sp = QPushButton("☰ 분류군순"); btn_sort_taxa_sp.setFixedHeight(24)
    btn_sort_taxa_sp.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row_sp = QHBoxLayout(); _sort_row_sp.setContentsMargins(0, 0, 0, 2); _sort_row_sp.setSpacing(4)
    _sort_row_sp.addWidget(btn_sort_desc_sp); _sort_row_sp.addWidget(btn_sort_taxa_sp); _sort_row_sp.addStretch()
    
    def _on_sort_desc_sp():
        _benthos_sort_mode[0] = "desc"; _rebuild_benthos_sp_tbl(); _rebuild_benthos_ind_tbl()
    def _on_sort_taxa_sp():
        _benthos_sort_mode[0] = "taxa"; _rebuild_benthos_sp_tbl(); _rebuild_benthos_ind_tbl()
    btn_sort_desc_sp.clicked.connect(_on_sort_desc_sp)
    btn_sort_taxa_sp.clicked.connect(_on_sort_taxa_sp)
    
    tbl_benthos_sp = _benthos_tbl(species, "species", rns)
    _bind_table_pct_refresh(tbl_benthos_sp, 3, cnt_col=2, pct_formatter=_fmt)
    ls.setContentsMargins(6, 12, 6, 6)
    ls.insertLayout(0, _sort_row_sp)
    _add_tbl_with_btn(ls, tbl_benthos_sp, pct_col=3, cnt_col=2, on_normalize=lambda: _on_norm(pie_s))
    pie_s = PieCanvas(); pie_s._setting_mode = "pie"
    apply_graph_default(parent_window, pie_s, "pie_order")
    pie_s._preview_data_provider = lambda: _extract_pie_data(grp_s, 1, 3)
    pie_s.draw_pie(pie_s._preview_data_provider())
    pie_s._refresh_cb = lambda: pie_s.draw_pie(pie_s._preview_data_provider())
    cv_grp_s = _wrap_cv_resizable("종수 비율", pie_s)
    _ps_panel = _make_pie_settings_panel(pie_s, cv_grp_s)
    _attach_title_to_cv(cv_grp_s, _ps_panel._title_controls)
    tab1_w = QWidget(); t1l = QVBoxLayout(tab1_w); t1l.setContentsMargins(0, 0, 0, 0)
    t1l.addWidget(_make_triplet(grp_s, _ps_panel, cv_grp_s), stretch=1)
    gtabs.addTab(tab1_w, "📊 분류군 현황(종수)")

    grp_i = QGroupBox("분류군(목별) 현황 - 개체수"); li = QVBoxLayout(grp_i)
    
    tbl_benthos_ind = _benthos_tbl(species, "individuals", rns)
    _bind_table_pct_refresh(tbl_benthos_ind, 3, cnt_col=2, pct_formatter=_fmt)
    
    # 정렬 버튼 (개체수 탭용)
    btn_sort_desc_ind = QPushButton("↓ 내림차순"); btn_sort_desc_ind.setFixedHeight(24)
    btn_sort_desc_ind.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa_ind = QPushButton("☰ 분류군순"); btn_sort_taxa_ind.setFixedHeight(24)
    btn_sort_taxa_ind.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row_ind = QHBoxLayout(); _sort_row_ind.setContentsMargins(0, 0, 0, 2); _sort_row_ind.setSpacing(4)
    _sort_row_ind.addWidget(btn_sort_desc_ind); _sort_row_ind.addWidget(btn_sort_taxa_ind); _sort_row_ind.addStretch()
    
    def _on_sort_desc_ind():
        _benthos_sort_mode[0] = "desc"; _rebuild_benthos_sp_tbl(); _rebuild_benthos_ind_tbl()
    def _on_sort_taxa_ind():
        _benthos_sort_mode[0] = "taxa"; _rebuild_benthos_sp_tbl(); _rebuild_benthos_ind_tbl()
    btn_sort_desc_ind.clicked.connect(_on_sort_desc_ind)
    btn_sort_taxa_ind.clicked.connect(_on_sort_taxa_ind)
    
    li.setContentsMargins(6, 12, 6, 6)
    li.insertLayout(0, _sort_row_ind)
    _add_tbl_with_btn(li, tbl_benthos_ind, pct_col=3, cnt_col=2, on_normalize=lambda: _on_norm(pie_i))
    pie_i = PieCanvas(); pie_i._setting_mode = "pie"
    apply_graph_default(parent_window, pie_i, "pie_order")
    pie_i._preview_data_provider = lambda: _extract_pie_data(grp_i, 1, 3)
    pie_i.draw_pie(pie_i._preview_data_provider())
    pie_i._refresh_cb = lambda: pie_i.draw_pie(pie_i._preview_data_provider())
    cv_grp_i = _wrap_cv_resizable("개체수 비율", pie_i)
    _pi_panel = _make_pie_settings_panel(pie_i, cv_grp_i)
    _attach_title_to_cv(cv_grp_i, _pi_panel._title_controls)
    tab2_w = QWidget(); t2l = QVBoxLayout(tab2_w); t2l.setContentsMargins(0, 0, 0, 0)
    t2l.addWidget(_make_triplet(grp_i, _pi_panel, cv_grp_i), stretch=1)
    gtabs.addTab(tab2_w, "📈 분류군 현황(개체수)")

    lay.addWidget(gtabs, stretch=1)

    _is_qual_only = sum(_int(sp.rounds.get(r, 0)) for sp in species for r in _detail_rns(rns)) == 0
    if _is_qual_only:
        qual_lbl = QLabel("※ 정성조사만 진행되었음")
        qual_lbl.setStyleSheet(f"{FF_KR}; font-size:12px; color:#D97706; padding:8px;")
        qual_lbl.setAlignment(Qt.AlignLeft)
        lay.addWidget(qual_lbl)
    grp_t = QGroupBox("문장"); grp_t.setStyleSheet("QGroupBox{background:#FFFFFF;}"); lt = QVBoxLayout(grp_t)
    txt_sent = _sent_txtbox(
        stats, species, rns, prot_sheet, survey,
        force_norm_ref=is_norm_sent,
        tbl_ref={
            "species": lambda: [
                float(((_get_tbl(grp_s).item(r, 3).text() if _get_tbl(grp_s).item(r, 3) else "0").replace("%", "").replace(",", "").strip()) or 0)
                for r in range(max((_get_tbl(grp_s).rowCount() if _get_tbl(grp_s) else 0) - 1, 0))
            ],
            "individuals": lambda: [
                float(((_get_tbl(grp_i).item(r, 3).text() if _get_tbl(grp_i).item(r, 3) else "0").replace("%", "").replace(",", "").strip()) or 0)
                for r in range(max((_get_tbl(grp_i).rowCount() if _get_tbl(grp_i) else 0) - 1, 0))
            ],
        },
        total_rns=total_rns,
        total_species=total_species,
    )
    txt_sent_ref[0] = txt_sent
    lt.setContentsMargins(8, 8, 8, 8); lt.addWidget(txt_sent)
    lay.addWidget(grp_t)

    _orig_rebuild_benthos_sp_tbl = _rebuild_benthos_sp_tbl
    _orig_rebuild_benthos_ind_tbl = _rebuild_benthos_ind_tbl
    def _rebuild_benthos_sp_tbl_with_sent():
        _orig_rebuild_benthos_sp_tbl()
        if txt_sent_ref[0]:
            txt_sent_ref[0]._sent_refresh_fn()
    def _rebuild_benthos_ind_tbl_with_sent():
        _orig_rebuild_benthos_ind_tbl()
        if txt_sent_ref[0]:
            txt_sent_ref[0]._sent_refresh_fn()
    _rebuild_benthos_sp_tbl = _rebuild_benthos_sp_tbl_with_sent
    _rebuild_benthos_ind_tbl = _rebuild_benthos_ind_tbl_with_sent

    w.gtabs = gtabs
    return w

def _fish_panel_clean(stats, species, rns, prot_sheet=None, survey="field", total_rns=None, total_species=None, parent_window=None):
    w = QWidget(); w.setStyleSheet(_QSS)
    lay = QVBoxLayout(w); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(8)

    gtabs = QTabWidget(); gtabs.setDocumentMode(True)
    gtabs.setStyleSheet(_tab_qss(True))

    is_norm_sent = [False]
    txt_sent_ref = [None]

    def _on_norm(pie_or_cv):
        if pie_or_cv._refresh_cb: pie_or_cv._refresh_cb()
        is_norm_sent[0] = True
        if txt_sent_ref[0]: txt_sent_ref[0]._sent_refresh_fn()

    # 정렬 모드
    _fam_clean_sort_mode = ["desc"]
    
    # ── Tab1: 과별 출현비율 ──────────────────────────────────────
    def _rebuild_fam_clean_tbl():
        fish_fam_tbl_clean = _fish_family_tbl(species, _fam_clean_sort_mode[0])
        _bind_table_pct_refresh(fish_fam_tbl_clean, 3, cnt_col=2, pct_formatter=_fmt)
        _replace_tbl(grp_f, fish_fam_tbl_clean)
        if pie_cv._refresh_cb: pie_cv._refresh_cb()
    
    grp_f = QGroupBox("과별 출현비율"); lf = QVBoxLayout(grp_f)

    # 정렬 버튼
    btn_sort_desc_fam = QPushButton("↓ 내림차순"); btn_sort_desc_fam.setFixedHeight(24)
    btn_sort_desc_fam.setStyleSheet(make_outline_btn_qss(_ACCENT, _ACCENT_L))
    btn_sort_taxa_fam = QPushButton("☰ 분류군순"); btn_sort_taxa_fam.setFixedHeight(24)
    btn_sort_taxa_fam.setStyleSheet(make_outline_btn_qss(_SUB, "#F3F4F6"))

    _sort_row_fam = QHBoxLayout(); _sort_row_fam.setContentsMargins(0, 0, 0, 2); _sort_row_fam.setSpacing(4)
    _sort_row_fam.addWidget(btn_sort_desc_fam); _sort_row_fam.addWidget(btn_sort_taxa_fam); _sort_row_fam.addStretch()
    
    def _on_sort_desc_fam():
        _fam_clean_sort_mode[0] = "desc"; _rebuild_fam_clean_tbl()
    def _on_sort_taxa_fam():
        _fam_clean_sort_mode[0] = "taxa"; _rebuild_fam_clean_tbl()
    btn_sort_desc_fam.clicked.connect(_on_sort_desc_fam)
    btn_sort_taxa_fam.clicked.connect(_on_sort_taxa_fam)
    
    fish_fam_tbl_clean = _fish_family_tbl(species)
    _bind_table_pct_refresh(fish_fam_tbl_clean, 3, cnt_col=2, pct_formatter=_fmt)
    lf.setContentsMargins(6, 12, 6, 6)
    lf.insertLayout(0, _sort_row_fam)
    _add_tbl_with_btn(lf, fish_fam_tbl_clean, pct_col=3, cnt_col=2, on_normalize=lambda: _on_norm(pie_cv))
    pie_cv = PieCanvas(); pie_cv._setting_mode = "pie"
    apply_graph_default(parent_window, pie_cv, "pie_order")
    pie_cv._preview_data_provider = lambda: _extract_pie_data(grp_f, 1, 3)
    pie_cv.draw_pie(pie_cv._preview_data_provider())
    pie_cv._refresh_cb = lambda: pie_cv.draw_pie(pie_cv._preview_data_provider())
    pie_grp = _wrap_cv_resizable("과별 출현비율 그래프", pie_cv)
    _pf_panel = _make_pie_settings_panel(pie_cv, pie_grp)
    _attach_title_to_cv(pie_grp, _pf_panel._title_controls)
    tab1_w = QWidget(); t1l = QVBoxLayout(tab1_w); t1l.setContentsMargins(0, 0, 0, 0)
    t1l.addWidget(_make_triplet(grp_f, _pf_panel, pie_grp), stretch=1)
    gtabs.addTab(tab1_w, "📊 과별 출현비율")

    # ── Tab2: 우점도 ──────────────────────────────────────
    grp_dom = QGroupBox(f"우점도 ≥{SETTINGS.dom_pct:.1f}%"); ld = QVBoxLayout(grp_dom)
    ld.setContentsMargins(6, 12, 6, 6)
    dom_tbl = _make_tbl(["학명", "국명", "개체수", "우점도(%)"])
    dom_pct_state = [SETTINGS.dom_pct]
    def _refresh_dom_tbl(apply_norm=False):
        _rebuild_dom_tbl(dom_tbl, species, rns, dom_pct_state[0])
        if apply_norm:
            from ui_shared import normalize_tbl_pct_col
            normalize_tbl_pct_col(dom_tbl, 3, cnt_col=2, pct_formatter=_fmt, decimals=SETTINGS.decimal)
    _refresh_dom_tbl()
    dom_tbl._refresh_cb = lambda: _refresh_dom_tbl(True)
    
    # 우점도 표에는 정렬 버튼 추가 안 함 (우점도 기준으로 정렬되어 있음)
    _add_tbl_with_btn(ld, dom_tbl, pct_col=3, cnt_col=2, on_normalize=lambda: _on_norm(dom_cv))
    dom_cv = _Canvas(6, 4); dom_cv._setting_mode = "bar"
    dom_cv._cfg["dom_pct"] = SETTINGS.dom_pct
    dom_cv._cfg["bar_horiz"] = SETTINGS.bar_horiz
    dom_cv._cfg["bar_h_height"] = SETTINGS.bar_h_height
    dom_cv._cfg["bar_v_width"] = SETTINGS.bar_v_width
    dom_cv._cfg["bar_sort"] = getattr(SETTINGS, "bar_sort", "desc")
    dom_cv._cfg["show_legend"] = getattr(SETTINGS, "show_legend", True)
    dom_cv._cfg["orientation"] = "horizontal"
    apply_graph_default(parent_window, dom_cv, "bar_dominance")
    _draw_fish_dom_bar(dom_cv, grp_dom, "")
    dom_cv._preview_draw = lambda target: _draw_fish_dom_bar(target, grp_dom, "")
    dom_cv._refresh_cb = lambda: _draw_fish_dom_bar(dom_cv, grp_dom, "")
    dom_grp = _wrap_cv_resizable("우점도 그래프", dom_cv, default_size=(960, 520))

    def _on_dom_pct_change(new_pct):
        dom_pct_state[0] = new_pct
        _refresh_dom_tbl(True)
        grp_dom.setTitle(f"우점도 ≥{new_pct:.1f}%")
        if txt_sent_ref[0]:
            txt_sent_ref[0]._sent_refresh_fn()

    _dom_panel = _make_dom_settings_panel(dom_cv, dom_grp, on_pct_change=_on_dom_pct_change)
    _attach_title_to_cv(dom_grp, _dom_panel._title_controls)
    tab2_w = QWidget(); t2l = QVBoxLayout(tab2_w); t2l.setContentsMargins(0, 0, 0, 0)
    t2l.addWidget(_make_triplet(grp_dom, _dom_panel, dom_grp), stretch=1)
    gtabs.addTab(tab2_w, "👑 우점도")

    lay.addWidget(gtabs, stretch=1)

    grp_s = QGroupBox("문장"); grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}"); sv = QVBoxLayout(grp_s)
    txt_sent = _sent_txtbox(
        stats,
        species,
        rns,
        prot_sheet,
        survey,
        force_norm_ref=is_norm_sent,
        tbl_ref={
            "family": lambda: [
                float((dom_txt.replace("%", "").replace(",", "").strip()) or 0)
                for dom_txt in [(_get_tbl(grp_f).item(r, 3).text() if _get_tbl(grp_f) and _get_tbl(grp_f).item(r, 3) else "0")
                                for r in range(max((_get_tbl(grp_f).rowCount() if _get_tbl(grp_f) else 0) - 1, 0))]
            ],
            "dominance": lambda: [
                {
                    "label": (_get_tbl(grp_dom).item(r, 1).text().strip() if _get_tbl(grp_dom).item(r, 1) else ""),
                    "pct": float(((_get_tbl(grp_dom).item(r, 3).text() if _get_tbl(grp_dom).item(r, 3) else "0").replace("%", "").replace(",", "").strip()) or 0),
                    "count": int(float(((_get_tbl(grp_dom).item(r, 2).text() if _get_tbl(grp_dom).item(r, 2) else "0").replace(",", "").strip()) or 0)),
                }
                for r in range(max((_get_tbl(grp_dom).rowCount() if _get_tbl(grp_dom) else 0) - 1, 0))
                if _get_tbl(grp_dom) and _get_tbl(grp_dom).item(r, 1)
            ],
            "dominance_threshold": lambda: dom_pct_state[0],
        },
        total_rns=total_rns,
        total_species=total_species,
    )
    txt_sent_ref[0] = txt_sent
    sv.setContentsMargins(8, 8, 8, 8); sv.addWidget(txt_sent)
    lay.addWidget(grp_s)

    _orig_rebuild_fam_clean_tbl = _rebuild_fam_clean_tbl
    def _rebuild_fam_clean_tbl_with_sent():
        _orig_rebuild_fam_clean_tbl()
        if txt_sent_ref[0]:
            txt_sent_ref[0]._sent_refresh_fn()
    _rebuild_fam_clean_tbl = _rebuild_fam_clean_tbl_with_sent

    w.gtabs = gtabs
    return w

def _build_site_tabs_clean(stats, sheet, rns, species, prot_sheet=None, total_rns=None, total_species=None, parent_window=None):
    site_rns = [r for r in rns if _prn(r)[2] not in ("종합", "합계", "")]
    if len(site_rns) <= 1:
        base_rns = site_rns if site_rns else _detail_rns(rns)
        return _sc(_site_panel(stats, sheet, species, base_rns, prot_sheet, total_rns=total_rns, total_species=total_species, parent_window=parent_window))
    tab = QTabWidget(); tab.setDocumentMode(True); tab.setStyleSheet(_tab_qss(False))
    tab.addTab(_sc(_site_panel(stats, sheet, species, site_rns, prot_sheet, total_rns=total_rns, total_species=total_species, parent_window=parent_window)), "전체")
    for r in site_rns:
        site = _prn(r)[2]
        sp_s = _sp_in_rn(species, r)
        if sp_s:
            tab.addTab(_sc(_site_panel(stats, sheet, sp_s, [r], prot_sheet, parent_window=parent_window)), site)
    return tab

def _field_widget_clean(stats, sheet, fld_groups, prot_sheet=None, parent_window=None):
    if not fld_groups:
        e = QWidget(); l = QVBoxLayout(e); l.addWidget(QLabel("현지 데이터 없음")); return e
    all_rns = [r for rns in fld_groups.values() for r in _detail_rns(rns)]
    all_sp = _sp_in_any(sheet.species, all_rns)
    rnd_tab = QTabWidget(); rnd_tab.setDocumentMode(True); rnd_tab.setStyleSheet(_tab_qss(False))
    
    group_defs = parent_window.get_active_groups(all_rns) if parent_window and hasattr(parent_window, "get_active_groups") else []
    total_steps = 1 + (len(group_defs) if group_defs else len(fld_groups))
    if parent_window and hasattr(parent_window, "step_sub_progress"):
        parent_window.step_sub_progress(f"화면(UI) 생성 중 ({sheet.name}: 현지 - 전체)", 1.0 / total_steps)

    rnd_tab.addTab(_sc(_site_panel(stats, sheet, all_sp, all_rns, prot_sheet, parent_window=parent_window)), "전체")

    for group_name, group_rns in group_defs:
        sp_g = _sp_in_any(sheet.species, group_rns)
        if sp_g:
            if parent_window and hasattr(parent_window, "step_sub_progress"):
                parent_window.step_sub_progress(f"화면(UI) 생성 중 ({sheet.name}: 그룹 - {group_name})", 1.0 / total_steps)
            rnd_tab.addTab(_build_site_tabs_clean(stats, sheet, group_rns, sp_g, prot_sheet,
                                                  total_rns=all_rns, total_species=all_sp, parent_window=parent_window), group_name)

    if group_defs:
        return rnd_tab
    
    for rnd_label, rns in fld_groups.items():
        if parent_window and hasattr(parent_window, "step_sub_progress"):
            parent_window.step_sub_progress(f"화면(UI) 생성 중 ({sheet.name}: 현지 - {rnd_label})", 1.0 / total_steps)
            
        detail_rns = _detail_rns(rns)
        sp_r = _sp_in_any(sheet.species, detail_rns)
        if sp_r:
            site_labels = []
            for r in detail_rns:
                site = _prn(r)[2]
                if site and site not in site_labels:
                    site_labels.append(site)
            tab_label = site_labels[0] if len(site_labels) == 1 else rnd_label
            rnd_tab.addTab(_build_site_tabs_clean(stats, sheet, detail_rns, sp_r, prot_sheet, parent_window=parent_window), tab_label)
    return rnd_tab

# ── 지점 패널 ────────────────────────────────────────────────────
def _site_panel(stats, sheet, species, rns, prot_sheet=None, total_rns=None, total_species=None, parent_window=None):
    if stats.taxon == "fish":
        return _fish_panel_clean(stats, species, rns, prot_sheet, "field", total_rns=total_rns, total_species=total_species, parent_window=parent_window)
    if stats.taxon == "benthos":
        return _benthos_panel(stats, species, rns, prot_sheet, "field", total_rns=total_rns, total_species=total_species, parent_window=parent_window)
    w=QWidget(); w.setStyleSheet(_QSS)
    lay=QVBoxLayout(w); lay.setContentsMargins(6,6,6,6); lay.setSpacing(8)

    # Splitter: 목별 | 다양성 | 그래프탭
    spl=QSplitter(Qt.Horizontal); spl.setChildrenCollapsible(False)

    grp_o=QGroupBox("목별 종수"); gl=QVBoxLayout(grp_o)
    order_tbl = _order_tbl(species)
    _bind_table_pct_refresh(order_tbl, 3, cnt_col=2, pct_formatter=_fmt)
    gl.setContentsMargins(6,12,6,6); _add_tbl_with_btn(gl, order_tbl, pct_col=3, cnt_col=2); spl.addWidget(grp_o)

    grp_d=QGroupBox("다양성 지수"); gd=QVBoxLayout(grp_d)
    gd.setContentsMargins(6,18,6,6); gd.addWidget(_div_tbl(_calc_local_div(species, rns), species)); gd.addStretch()
    spl.addWidget(grp_d)

    gt=QTabWidget(); gt.setDocumentMode(True); gt.setStyleSheet(_tab_qss(False))
    # 목별 파이
    pie_cv=_Canvas(6,4); pie_cv._setting_mode="pie"
    apply_graph_default(parent_window, pie_cv, "pie_order")
    _draw_order_pie(pie_cv, grp_o)
    pie_cv._preview_data_provider = lambda: _extract_pie_data(grp_o, 1, 3)
    pie_cv._refresh_cb = lambda: _draw_order_pie(pie_cv, grp_o)
    tbl_o = _get_tbl(grp_o)
    if tbl_o: tbl_o.on_normalize = lambda: _draw_order_pie(pie_cv, grp_o)
    gt.addTab(_wrap_cv("목별",pie_cv),"🥧 목별")
    
    bar_cv=_Canvas(6,4); bar_cv._setting_mode="bar"
    apply_graph_default(parent_window, bar_cv, "bar_basic")
    
    # 다양성 막대
    div_cv=_Canvas(4,4); div_cv._setting_mode="diversity"
    apply_graph_default(parent_window, div_cv, "bar_diversity")
    _draw_div_bar(div_cv, grp_d); div_cv._preview_draw = lambda target: _draw_div_bar(target, grp_d); div_cv._refresh_cb = lambda: _draw_div_bar(div_cv, grp_d); gt.addTab(_wrap_cv("다양성",div_cv, default_size=(820, 480)),"📈 다양성")
    spl.addWidget(gt)
    spl.setStretchFactor(0, 0); spl.setStretchFactor(1, 0); spl.setStretchFactor(2, 1)
    spl.setSizes([520, 260, 900])
    lay.addWidget(spl)

    # 종 목록
    grp_sp=QGroupBox("종 목록"); gs=QVBoxLayout(grp_sp)
    gs.setContentsMargins(6,12,6,6)
    sp_tbl = _sp_tbl(species,rns)
    _bind_table_pct_refresh(sp_tbl, 4 + len(rns) + 1, cnt_col=4 + len(rns), pct_formatter=_fmt)
    _add_tbl_with_btn(gs, sp_tbl, True)
    lay.addWidget(grp_sp,stretch=1)
    
    _draw_site_bar(bar_cv, grp_sp, rns); bar_cv._refresh_cb = lambda: _draw_site_bar(bar_cv, grp_sp, rns); gt.insertTab(1, _wrap_cv("지점별",bar_cv, default_size=(960, 520)),"📊 지점별")

    grp_s=QGroupBox("문장"); grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}"); sv=QVBoxLayout(grp_s)
    sv.setContentsMargins(8,8,8,8); sv.addWidget(_sent_txtbox(stats,species,rns,prot_sheet,"field"))
    lay.addWidget(grp_s)
    return w

# ── 지점 서브탭 ──────────────────────────────────────────────────
def _build_site_tabs(stats, sheet, rns, species, prot_sheet=None):
    site_rns=[r for r in rns if _prn(r)[2] not in ("종합","")]
    if len(site_rns)<=1:
        base_rns = site_rns if site_rns else _detail_rns(rns)
        return _sc(_site_panel(stats,sheet,species,base_rns,prot_sheet))
    tab=QTabWidget(); tab.setDocumentMode(True); tab.setStyleSheet(_tab_qss(False))
    tab.addTab(_sc(_site_panel(stats,sheet,species,site_rns if site_rns else _detail_rns(rns),prot_sheet)),"전체")
    for r in site_rns:
        site=_prn(r)[2]; sp_s=_sp_in_rn(species,r)
        if sp_s: tab.addTab(_sc(_site_panel(stats,sheet,sp_s,[r],prot_sheet)),site)
    return tab

# ── 현지 탭 위젯 ─────────────────────────────────────────────────
def _field_widget(stats, sheet, fld_groups, prot_sheet=None):
    if not fld_groups:
        e=QWidget(); l=QVBoxLayout(e); l.addWidget(QLabel("현지 데이터 없음")); return e
    all_rns=[r for rns in fld_groups.values() for r in _detail_rns(rns)]
    all_sp=_sp_in_any(sheet.species,all_rns)
    rnd_tab=QTabWidget(); rnd_tab.setDocumentMode(True); rnd_tab.setStyleSheet(_tab_qss(False))
    rnd_tab.addTab(_sc(_site_panel(stats,sheet,all_sp,all_rns,prot_sheet)),"전체")
    for rnd_label,rns in fld_groups.items():
        detail_rns = _detail_rns(rns)
        sp_r=_sp_in_any(sheet.species,detail_rns)
        if sp_r: rnd_tab.addTab(_build_site_tabs(stats,sheet,detail_rns,sp_r,prot_sheet),rnd_label)
    return rnd_tab

# ── 문헌 패널 ────────────────────────────────────────────────────
def _lit_panel(stats, sheet, prot_sheet=None):
    lit_rns = [k for k in _lit_round_names(sheet) if "_합계" not in k]
    sp_lit  = _sp_in_any(sheet.species, lit_rns)
    return _lit_panel_simple(stats, sp_lit, lit_rns, prot_sheet)


def _lit_panel_simple(stats, sp_lit, lit_rns, prot_sheet=None):
    """문헌조사 패널: 문헌별 요약표 + 기재 문장."""
    w = QWidget(); w.setStyleSheet(_QSS)
    lay = QVBoxLayout(w); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(8)

    ind_rns = [r for r in lit_rns if "_합계" not in r]
    kor = {"fish": "어류", "benthos": "저서성 대형무척추동물"}.get(stats.taxon, stats.taxon)

    def _rn_lbl(r):
        return r.replace("문헌_", "").replace("현지_", "")

    def _sp_of(rk):
        return sp_lit if rk == "_all" else [sp for sp in sp_lit if _has(sp.rounds.get(rk))]

    def _row_data():
        rows = []
        if ind_rns:
            for rk in ind_rns:
                rows.append((_rn_lbl(rk), _sp_of(rk), False))
            rows.append(("전체", sp_lit, True))
        else:
            rows.append(("문헌조사", sp_lit, False))
        return rows

    # ── 1) 문헌별 요약표 ──────────────────────────────────────────────
    grp_t = QGroupBox("문헌별 요약")
    gt = QVBoxLayout(grp_t); gt.setContentsMargins(6, 12, 6, 6); gt.setSpacing(4)

    tbl = _make_tbl(["구분", "분류군 현황", "법정보호종"])
    tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _fill_tbl():
        rows = _row_data()
        tbl.setRowCount(len(rows))
        for ri, (lbl, sp_rn, is_total) in enumerate(rows):
            prot_n, prot_clause = _prot_list_graded(stats.taxon, prot_sheet, sp_rn)
            tbl.setItem(ri, 0, _item(lbl,                         Qt.AlignLeft | Qt.AlignVCenter))
            tbl.setItem(ri, 1, _item(_aqua_counts_str(sp_rn, stats.taxon)))
            tbl.setItem(ri, 2, _item(prot_clause if prot_n else "-", Qt.AlignLeft | Qt.AlignVCenter))
            if is_total:
                for c in range(3):
                    it = tbl.item(ri, c)
                    if it:
                        it.setBackground(QColor(_BG))
                        f = it.font(); f.setBold(True); it.setFont(f)
        _tbl_auto_height(tbl)

    _fill_tbl()
    _auto_fit_table(tbl)
    _add_tbl_with_btn(gt, tbl)
    lay.addWidget(grp_t, 0)

    # ── 2) 문헌조사 기재 문장 ────────────────────────────────────────
    _TXT_QSS = (
        f"QPlainTextEdit{{background:{_BG};{BD};border-radius:8px;{FF_KR};font-size:12px;padding:6px;}}"
    )

    def _build_lit_lines():
        S = SETTINGS
        lines = []
        if len(ind_rns) > 1:
            counts = _aqua_counts_str(sp_lit, stats.taxon)
            prot_n, prot_clause = _prot_list_graded(stats.taxon, prot_sheet, sp_lit)
            disturb_n, disturb_clause = _ecosystem_disturber_list(prot_sheet, sp_lit)
            prot_part = (f"{prot_clause} {prot_n}종{S.lit_s1_end}"
                         if prot_n else f"{S.prot_none_lit}")
            if disturb_n:
                if prot_n:
                    prot_part = f"{prot_clause} {prot_n}종, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
                else:
                    prot_part = f"{_prot_none_contrast(S.prot_none_lit)}, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
            prefix = "문헌조사"
            lines.append(f"{prefix} 결과, {kor}은 총 {counts}{S.lit_s1_mid} 법정보호종은 {prot_part}")

        for lbl, sp_rn, is_total in _row_data():
            if is_total:
                continue
            counts = _aqua_counts_str(sp_rn, stats.taxon)
            prot_n, prot_clause = _prot_list_graded(stats.taxon, prot_sheet, sp_rn)
            disturb_n, disturb_clause = _ecosystem_disturber_list(prot_sheet, sp_rn)
            prot_part = (f"{prot_clause} {prot_n}종{S.lit_s1_end}"
                         if prot_n else f"{S.prot_none_lit}")
            if disturb_n:
                if prot_n:
                    prot_part = f"{prot_clause} {prot_n}종, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
                else:
                    prot_part = f"{_prot_none_contrast(S.prot_none_lit)}, 생태계교란 생물은 {disturb_clause} {disturb_n}종{S.lit_s1_end}"
            if getattr(S, "lit_intro_mode", getattr(S, "field_intro_mode", "auto")) == "fixed":
                prefix = "문헌조사 결과,"
            else:
                prefix = lit_result_prefix([lbl], _round_survey_label(lbl), comma=True)
            lines.append(f"{prefix} {kor}은 총 {counts}{S.lit_s1_mid} 법정보호종은 {prot_part}")
        return _apply_title("\n".join(lines), S.sentence_title)

    grp_s = QGroupBox("문헌조사 기재 문장")
    grp_s.setStyleSheet("QGroupBox{background:#FFFFFF;}")
    sv = QVBoxLayout(grp_s); sv.setContentsMargins(8, 8, 8, 8); sv.setSpacing(6)
    n_lit = max(len(ind_rns) + (1 if len(ind_rns) > 1 else 0), 1)
    txt = QPlainTextEdit(); txt.setReadOnly(True)
    txt.setFixedHeight(min(n_lit * 42 + 20, 320))
    txt.setStyleSheet(_TXT_QSS)
    txt.setPlainText(_build_lit_lines())

    btn_copy = QPushButton("📋 복사"); btn_copy.setFixedHeight(24)
    btn_copy.setStyleSheet(_COPY_BTN_QSS)

    def _do_lit_copy():
        QApplication.clipboard().setText(txt.toPlainText())
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_copy)
    btn_copy.clicked.connect(_do_lit_copy)

    def _refresh_all():
        _fill_tbl()
        txt.setPlainText(_build_lit_lines())

    txt._sent_refresh_fn = _refresh_all

    br = QHBoxLayout(); br.addWidget(btn_copy); br.addStretch()
    sv.addLayout(br); sv.addWidget(txt)
    lay.addWidget(grp_s, 0)

    lay.addStretch()
    return w

# ── 메인 빌더 ────────────────────────────────────────────────────
def build_aqua_tab(stats, sheet, prot_sheet=None, parent_window=None):
    outer = QWidget(); outer.setStyleSheet(_QSS)
    lay = QVBoxLayout(outer); lay.setContentsMargins(0, 0, 0, 0)
    top = QTabWidget(); top.setDocumentMode(True); top.setStyleSheet(_tab_qss())
    groups = _round_groups2(sheet)
    fld = groups.get("현지", {}) or groups.get("문헌", {})
    lit_rns = _lit_round_names(sheet)

    top.addTab(_field_widget_clean(stats, sheet, fld, prot_sheet, parent_window), "🔭  현지조사")
    if lit_rns:
        top.addTab(_sc(_lit_panel(stats, sheet, prot_sheet)), "📚  문헌조사")

    lay.addWidget(top)

    if parent_window:
        from PySide6.QtWidgets import QPlainTextEdit
        def _refresh_sents():
            for w in outer.findChildren(QPlainTextEdit):
                fn = getattr(w, "_sent_refresh_fn", None)
                if fn:
                    fn()
        def _refresh_charts():
            for tbl in outer.findChildren(QTableWidget):
                cb = getattr(tbl, "_refresh_cb", None)
                if callable(cb) and bool(getattr(tbl, "_is_normalized", False)):
                    cb()
            _refresh_sents()
            for w in outer.findChildren(QWidget):
                if isinstance(w, QTableWidget):
                    continue
                cb = getattr(w, "_refresh_cb", None)
                if callable(cb):
                    cb()
        if hasattr(parent_window, "sig_sent_settings"):
            parent_window.sig_sent_settings.connect(_refresh_sents)
        if hasattr(parent_window, "sig_chart_settings"):
            parent_window.sig_chart_settings.connect(_refresh_charts)

    return outer

def _get_tbl(obj):
    if isinstance(obj, QTableWidget): return obj
    if hasattr(obj, "findChild"):
        return obj.findChild(QTableWidget)
    return None

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

def _add_tbl_with_btn(lay, tbl, use_sc=False, pct_col=None, cnt_col=None, on_normalize=None):
    from ui_shared import normalize_tbl_pct_col
    from PySide6.QtWidgets import QLabel
    btn_row = QHBoxLayout()
    btn_row.setContentsMargins(0, 0, 0, 0)
    btn_row.addStretch()

    hint_lbl = None
    if pct_col is not None:
        tbl._pct_col = pct_col
        tbl._cnt_col = cnt_col
        if not hasattr(tbl, "_is_normalized"):
            tbl._is_normalized = False

    if pct_col is not None:
        btn_norm = QPushButton("∑ 비율 보정")
        btn_norm.setFixedHeight(24)
        btn_norm.setStyleSheet(_OUTLINE_BTN_GREEN)
        btn_norm.setToolTip("비율(%) 합계를 100.00으로 자동 보정하고 변경 내역을 표시합니다.")

        hint_lbl = QLabel("")
        hint_lbl.setStyleSheet(
            f"font-size: 11px; color: #B45309; {FF_KR}; "
            "background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 4px; "
            "padding: 3px 8px;"
        )
        hint_lbl.setWordWrap(True)
        hint_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hint_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        hint_lbl.hide()

        def _do_norm():
            hint = normalize_tbl_pct_col(tbl, pct_col, cnt_col=cnt_col, pct_formatter=_fmt)
            tbl._is_normalized = True
            if hint:
                hint_lbl.setText(hint)
                hint_lbl.setFixedHeight(hint_lbl.sizeHint().height() + 6)
                hint_lbl.show()
            else:
                hint_lbl.setFixedHeight(0)
                hint_lbl.hide()
            if hasattr(tbl, 'on_normalize') and tbl.on_normalize:
                tbl.on_normalize()
            elif on_normalize:
                on_normalize()
        btn_norm.clicked.connect(_do_norm)
        btn_row.addWidget(btn_norm)

    btn_copy = QPushButton("📋 표 복사")
    btn_copy.setFixedHeight(24)
    btn_copy.setStyleSheet(_COPY_BTN_QSS)

    def _copy_tbl():
        tbl.copy_selection()
        from ui_shared import apply_button_feedback
        apply_button_feedback(btn_copy)
    btn_copy.clicked.connect(_copy_tbl)

    btn_row.addWidget(btn_copy)
    lay.addLayout(btn_row)
    if hint_lbl is not None:
        lay.addWidget(hint_lbl)
    if use_sc:
        lay.addWidget(_sc(tbl))
    else:
        lay.addWidget(tbl)
