# config.py — 전역 디자인 토큰 · 폰트 상수 · 앱 설정
# ══════════════════════════════════════════════════════════════════
# 여기 한 곳에서만 수정하면 모든 탭에 반영됩니다.
# ══════════════════════════════════════════════════════════════════

# ── 색상 토큰 ────────────────────────────────────────────────────
_BG       = "#F2F4F7"   # 앱 배경
_CARD     = "#FFFFFF"   # 카드 / 패널 배경
_BORDER   = "#E2E6EC"   # 테두리
_TXT      = "#111827"   # 본문 텍스트
_SUB      = "#6B7280"   # 보조 텍스트
_PATH     = "#9CA3AF"   # 경로 / 힌트 텍스트
_ACCENT   = "#2563EB"   # 강조 (파랑)
_ACCENT_D = "#1D4ED8"   # 강조 어둡게
_ACCENT_L = "#EFF6FF"   # 강조 연하게
_SUCCESS  = "#059669"   # 성공 / 긍정
_WARN     = "#D97706"   # 경고
_ERR      = "#DC2626"   # 오류

# 별칭 (하위 호환)
ACCENT = _ACCENT
WARN   = _WARN

# ── 폰트 상수 ────────────────────────────────────────────────────
_FONT_EN = "Segoe UI"
_FONT_KR = "맑은 고딕"   # ← 폰트 변경은 여기서만

# CSS 합성 문자열 (f-string 내 따옴표 중첩 방지용)
FF_KR = "font-family: '" + _FONT_KR + "'"
FF_EN = "font-family: '" + _FONT_EN + "', '" + _FONT_KR + "'"
BD    = "border: 1.5px solid " + _BORDER
BD1   = "border: 1px solid "   + _BORDER

# 체크박스/라디오 indicator 공통 QSS
CHK_INDICATOR_QSS = (
    "QCheckBox::indicator, QRadioButton::indicator {"
    " width:12px; height:12px;"
    " }"
    "QCheckBox::indicator {"
    " border:1.5px solid #94A3B8; border-radius:3px; background:#FFFFFF;"
    " }"
    "QCheckBox::indicator:unchecked {"
    " border:1.5px solid #94A3B8; background:#FFFFFF;"
    " }"
    "QCheckBox::indicator:hover {"
    " border-color:#64748B;"
    " }"
    "QCheckBox::indicator:checked {"
    " border:1.5px solid #1D4ED8;"
    " background:qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,"
    " stop:0 #2563EB, stop:0.32 #2563EB, stop:0.33 #FFFFFF, stop:1 #FFFFFF);"
    " }"
    "QCheckBox::indicator:disabled {"
    " border-color:#CBD5E1; background:#F1F5F9;"
    " }"
    "QRadioButton::indicator {"
    " border:1.5px solid #94A3B8; border-radius:7px; background:#FFFFFF;"
    " }"
    "QRadioButton::indicator:hover {"
    " border-color:#64748B;"
    " }"
    "QRadioButton::indicator:checked {"
    " border:1.5px solid #1D4ED8;"
    " background:qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,"
    " stop:0 #2563EB, stop:0.32 #2563EB, stop:0.33 #FFFFFF, stop:1 #FFFFFF);"
    " }"
    "QRadioButton::indicator:disabled {"
    " border-color:#CBD5E1; background:#F1F5F9;"
    " }"
)

# ── 그래프 공통 상수 ─────────────────────────────────────────────
GRAPH_H = 260   # 캔버스 기본 높이(px)

PIE_COLORS = [
    "#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5",
    "#70AD47", "#264478", "#9E480E", "#843C0C", "#255E91",
    "#7030A0", "#C00000", "#00B0F0", "#92D050", "#FF6600",
]

# ── 도메인 상수 (육상동물) ───────────────────────────────────────
LIFE_DISPLAY = [
    ("RES", "텃새(Res)"),  ("SV",  "여름철새(Sv)"),
    ("WV",  "겨울철새(Wv)"), ("PM",  "나그네새(Pm)"), ("VAG", "길잃은새(Vag)"),
]
TRACE_MAP = {
    "V": "목견",    "D": "배설물",   "F": "족흔",   "H": "탐문", "N": "둥지",
    "S": "청음",    "T": "굴",   "C": "무인센서카메라", "d": "사체", "h": "털", "FF": "식흔",
    "E": "난괴",    "L": "유생", "A": "성체", "e": "기타"
}
SITE_TAXONS = {"mammal", "herp"}
TAXON_LABEL = {
    "mammal": "포유류",
    "bird":   "조류",
    "herp":   "양서류 및 파충류",
    "insect": "육상곤충류",
}


# ── 앱 전역 설정 ─────────────────────────────────────────────────
class AppSettings:
    """
    프로그램 전체에서 공유하는 설정 값입니다.
    SETTINGS.속성 = 값  형식으로 런타임 변경 가능합니다.
    """
    # ── 수치 표시 ────────────────────────────────────
    decimal     : int   = 1        # 소수점 자릿수

    # ── 파이 차트 ────────────────────────────────────
    pie_fontsize  : int   = 9      # 라벨 글씨 크기(pt)
    pie_radius    : float = 0.85   # 반지름 (0.35 ~ 2.0)
    pie_start_angle   : float = 90.0
    pie_label_offset  : float = 0.35
    pie_edge_width    : float = 1.2
    pie_leader_width  : float = 0.9
    pie_leader_gap    : float = 0.25
    pie_show_leaders  : bool  = True   # 지시선 표시 여부

    # ── 막대 차트 ────────────────────────────────────
    bar_fontsize  : int   = 9
    bar_horiz     : bool  = True   # True = 가로 막대
    bar_h_height  : float = 0.60   # 가로 막대 높이 비율
    bar_v_width   : float = 0.60   # 세로 막대 너비 비율
    div_bar_width : float = 0.50   # 다양도 막대 너비
    div_bar_gap   : float = 1.00   # 다양도 막대 간격 (항목 중심 간격)
    bar_count_label_inside : bool = False  # 개체수·우점도 그래프 개체수 라벨 표시
    bar_margin_left   : float = 0.15
    bar_margin_right  : float = 0.95
    bar_margin_bottom : float = 0.15
    bar_margin_top    : float = 0.90

    # ── 선 차트 ─────────────────────────────────────
    line_color    : str   = "#ff0000"
    marker_size   : int   = 5
    line_width    : float = 1.8

    # ── 색상 · 그리드 ────────────────────────────────
    bar_color   : str   = "#4472C4"
    div_color_1 : str   = "#4472C4"
    div_color_2 : str   = "#ED7D31"
    div_color_3 : str   = "#70AD47"
    color_mode  : str   = "auto"   # "auto" | "gray" | "custom"
    grid_on     : bool  = False
    grid_color  : str   = "#e6e6e6"

    # ── 축 ──────────────────────────────────────────
    x_label_rot : int   = 0
    axis_min    : float = 0.0
    axis_max    : float = 0.0      # 0 = 자동
    axis_step   : float = 0.0      # 0 = 자동

    # ── 레이아웃 ─────────────────────────────────────
    graph_height     : int   = 340
    graph_width_auto : bool  = True
    graph_width      : int   = 900

    # ── 레이블 · 범례 ────────────────────────────────
    chart_title  : str  = ""
    y_axis_title : str  = "우점도(%)"
    label_mode   : str  = "none"   # "none" | "pct" | "count" | "both"
    show_legend  : bool = True
    legend_pos   : str  = "bottom" # "top" | "bottom" | "left" | "right"
    bar_sort     : str  = "desc"   # "desc" | "asc" | "none"

    # ── 지배종 기준 ──────────────────────────────────
    dom_pct : float = 5.0

    # ── 종 나열 개수 제한 ─────────────────────────────
    sent_species_limit : int = 3
    plant_life_item_format : str = "count_pct"  # "count_pct" | "pct_count"
    plant_sent_list_limits : dict = {}          # {"문장키": 3, 0이면 전체 나열}
    plant_floristic_high_grade_notice : bool = True
    plant_floristic_notice_grade_v : bool = True
    plant_floristic_notice_grade_iv : bool = True

    # ── 자동 생성 문장 템플릿 (핵심 종결 어미) ─────────────────────────
    end_field : str = "확인됨"
    end_lit   : str = "기록됨"
    end_ana   : str = "분석됨"
    end_prb   : str = "전언됨"
    
    order_next : str = "그 다음으로"
    prot_grade_mode : str = "short"  # "none" | "short" | "full"
    field_intro_mode : str = "auto"  # "auto" | "fixed" | "lit_title"
    lit_intro_mode : str = "auto"    # "auto" | "fixed" | "lit_title"
    lit_title_map : dict = {}        # {"1": "문헌 제목", ...}
    lit_title_source_path : str = ""

    def _make_mid(self, base: str) -> str:
        import re
        s = base
        s = re.sub(r'됨|되었음|되었다', '되었으며', s)
        s = re.sub(r'함|하였음|하였다|했음|했다', '하였으며', s)
        s = re.sub(r'남|났음|났다', '났으며', s)
        s = re.sub(r'음$|다$', '으며', s)
        return s

    def _make_negative(self, base: str) -> str:
        import re
        s = base
        s = re.sub(r'되었음', '되지 않았음', s)
        s = re.sub(r'되었다', '되지 않았다', s)
        s = re.sub(r'됨', '되지 않음', s)
        
        s = re.sub(r'하였음|했음', '하지 않았음', s)
        s = re.sub(r'하였다|했다', '하지 않았다', s)
        s = re.sub(r'함', '하지 않음', s)
        
        s = re.sub(r'났음', '나지 않았음', s)
        s = re.sub(r'났다', '나지 않았다', s)
        s = re.sub(r'남', '나지 않음', s)
        
        # 기본 폴백
        if s == base:
            s = re.sub(r'음$', '지 않음', s)
            s = re.sub(r'다$', '지 않다', s)
        return s

    @property
    def prot_none_field(self): return self._make_negative(self.end_field)
    @property
    def prot_none_lit(self): return self._make_negative(self.end_lit)

    @property
    def field_s1_end(self): return "이 " + self.end_field
    @property
    def lit_s1_end(self): return "이 " + self.end_lit
    @property
    def div_end(self): return "로 " + self.end_ana
    @property
    def site_s2_suffix(self): return self.end_prb
    @property
    def field_s1_mid(self): return "이 " + self._make_mid(self.end_field) + ","
    @property
    def lit_s1_mid(self): return "이 " + self._make_mid(self.end_lit) + ","
    @property
    def order_verb_f(self): return self._make_mid(self.end_field)
    @property
    def order_verb_l(self): return self._make_mid(self.end_lit)
    @property
    def mammal_order_first(self): return "로 가장 다양하게 " + self._make_mid(self.end_field)
    @property
    def mammal_order_end(self): return "의 순으로 " + self.end_field

    # 식물 전용 별칭 (호환성 유지)
    @property
    def plant_field_s1_end(self): return self.field_s1_end
    @property
    def plant_lit_s1_end(self): return self.lit_s1_end
    @property
    def plant_field_s1_mid(self): return self.field_s1_mid
    @property
    def plant_lit_s1_mid(self): return self.lit_s1_mid
    @property
    def plant_order_verb_f(self): return self.order_verb_f
    @property
    def plant_order_next(self): return self.order_next

    # ── 입지별 출현현황 템플릿 (포유류/양서파충류) ─────────────────
    site_s1_prefix : str = "조사된 {분류군}의 입지별 출현현황을 정리하면, 조사지역의 "
    site_s2_prefix : str = "지역주민의 탐문조사에서는 "
    site_s2_core_A : str = "현지조사시 확인된 {현지확인}의 서식이 "
    site_s2_core_B : str = "{탐문}의 서식이 "
    site_s2_core_C : str = "현지조사시 확인된 {현지확인} 이외에 {탐문}의 서식이 "

    # ── 문장 제목 및 분류군 레벨 표시 선택 ─────────────────────────
    sentence_title   : str  = ""     # 문장 앞 제목 (예: "2023년 봄철 ")
    sent_show_phylum : bool = True   # 문 수 표시(저서상)
    sent_show_class  : bool = True   # 강 수 표시(저서상)
    sent_show_order  : bool = False  # 목 수 표시
    sent_show_family : bool = True   # 과 수 표시
    sent_show_genus  : bool = True   # 속 수 표시
    sent_show_species: bool = True   # 종 수 표시
    # 식물 전용 하위 분류군
    sent_show_var    : bool = True   # 변종
    sent_show_forma  : bool = True   # 품종
    sent_show_subsp  : bool = True   # 아종
    sent_show_taxa   : bool = True   # 총분류군수
    sent_add_period  : bool = False  # 문장 끝 마침표 추가

    # JSON 저장 허용 키(런타임 공유 설정만 직렬화)
    SERIALIZABLE_KEYS = [
        "decimal",
        "pie_fontsize", "pie_radius", "pie_start_angle", "pie_label_offset", "pie_edge_width", "pie_leader_width", "pie_leader_gap", "pie_show_leaders",
        "bar_fontsize", "bar_horiz", "bar_h_height", "bar_v_width", "div_bar_width", "div_bar_gap", "bar_count_label_inside",
        "bar_margin_left", "bar_margin_right", "bar_margin_bottom", "bar_margin_top",
        "line_color", "marker_size", "line_width",
        "bar_color", "div_color_1", "div_color_2", "div_color_3", "color_mode", "grid_on", "grid_color",
        "x_label_rot", "axis_min", "axis_max", "axis_step",
        "graph_height", "graph_width_auto", "graph_width",
        "chart_title", "y_axis_title", "label_mode", "show_legend", "legend_pos", "bar_sort",
        "dom_pct", "sent_species_limit", "plant_life_item_format", "plant_sent_list_limits",
        "plant_floristic_high_grade_notice", "plant_floristic_notice_grade_v", "plant_floristic_notice_grade_iv",
        "end_field", "end_lit", "end_ana", "end_prb", "order_next", "prot_grade_mode", "field_intro_mode", "lit_intro_mode",
        "lit_title_map", "lit_title_source_path",
        "site_s1_prefix", "site_s2_prefix", "site_s2_core_A", "site_s2_core_B", "site_s2_core_C",
        "sentence_title", "sent_show_phylum", "sent_show_class", "sent_show_order", "sent_show_family",
        "sent_show_genus", "sent_show_species", "sent_show_var", "sent_show_forma", "sent_show_subsp",
        "sent_show_taxa", "sent_add_period",
    ]

    def to_dict(self, keys=None):
        keys = keys or self.SERIALIZABLE_KEYS
        out = {}
        for k in keys:
            if hasattr(self, k):
                out[k] = getattr(self, k)
        return out

    def from_dict(self, data: dict, keys=None):
        if not isinstance(data, dict):
            return
        keys_set = set(keys or self.SERIALIZABLE_KEYS)
        for k, v in data.items():
            if k in keys_set and hasattr(self, k):
                setattr(self, k, v)


# 싱글턴 — 모든 모듈이 이 객체를 공유합니다
SETTINGS = AppSettings()
