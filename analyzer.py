# analyzer.py — 분류군별 통계 산출
import math
from collections import defaultdict
from dataclasses import dataclass, field
from parser import (
    ParsedSheet, ParsedAquatic, ParsedPlant, ParsedPlantSpecial,
    ParsedProtected, SpeciesRow, AquaticRow, PlantRow, PlantSpecialRow,
)
from shared import _has


# ── 결과 데이터클래스 ─────────────────────────────────────────────────────────
@dataclass
class RoundStat:
    name: str
    count: int          # 종수 (육수는 개체수)

@dataclass
class OrderStat:
    order: str
    total: int
    ratio: float
    round_stats: list   # list[RoundStat]
    family_count: int

@dataclass
class DivStats:
    shannon_h: float
    evenness_e: float
    dominance_di: float
    dominant_order: str
    dominant_count: int
    subdominant_order: str
    subdominant_count: int

@dataclass
class TaxaStats:
    sheet_name: str
    taxon: str
    total_species: int
    total_individuals: int          # 현지 개체수 합 (있으면)
    round_names: list
    round_totals: list              # list[RoundStat]
    order_stats: list               # 종수 내림차순
    order_stats_orig: list          # 원래 목 순서
    family_count: int
    div: DivStats
    lit_only: int
    field_only: int
    both: int
    # 조류 전용
    life_stats: dict = field(default_factory=dict)  # {생활형: 종수}

@dataclass
class AquaticStats:
    sheet_name: str
    taxon: str
    total_species: int
    total_individuals: int
    round_names: list
    round_totals: list              # list[RoundStat] (회차별 개체수)
    order_stats: list
    order_stats_orig: list
    family_count: int
    div: DivStats

@dataclass
class PlantStats:
    sheet_name: str
    taxon: str
    total_species: int
    round_names: list
    round_totals: list
    family_count: int
    lit_only: int
    field_only: int
    both: int

@dataclass
class PlantSpecialStats:
    sheet_name: str
    total_species: int
    by_category: dict   # {희귀식물: n, 특산식물: n}
    round_names: list
    round_totals: list

@dataclass
class ProtectedStats:
    sheet_name: str
    total_species: int
    by_group: dict
    by_grade: dict
    round_names: list
    round_totals: list


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────
def _has_present(v) -> bool:
    """출현 여부 (○, 숫자 모두 True)"""
    if v is None: return False
    if isinstance(v, (int, float)): return v > 0
    s = str(v).strip()
    return s not in ("", "None", "-", "0", "0.0", "x", "X", "×")

def _int(v) -> int:
    try: return int(v or 0)
    except: return 0

def _calc_div(order_counts: dict) -> DivStats:
    total = sum(order_counts.values())
    if not total:
        return DivStats(0,0,0,"",0,"",0)
    H = sum(-( c/total)*math.log(c/total) for c in order_counts.values() if c > 0)
    S = sum(1 for c in order_counts.values() if c > 0)
    E = H / math.log(S) if S > 1 else 0.0
    sorted_c = sorted(order_counts.values(), reverse=True)
    DI = (sorted_c[0] + (sorted_c[1] if len(sorted_c)>1 else 0)) / total
    sorted_o = sorted(order_counts.items(), key=lambda x:-x[1])
    dom = sorted_o[0] if sorted_o else ("",0)
    sub = sorted_o[1] if len(sorted_o)>1 else ("",0)
    return DivStats(
        shannon_h=H, evenness_e=E,
        dominance_di=DI,
        dominant_order=dom[0], dominant_count=dom[1],
        subdominant_order=sub[0], subdominant_count=sub[1],
    )


# ── 육상동물 분석 ─────────────────────────────────────────────────────────────
def analyze_land(sheet: ParsedSheet) -> TaxaStats:
    sp_list    = sheet.species
    rnames     = sheet.meta.round_names
    total      = len(sp_list)

    # 회차별 출현종수
    round_totals = []
    for rn in rnames:
        cnt = sum(1 for s in sp_list if _has_present(s.rounds.get(rn)))
        round_totals.append(RoundStat(name=rn, count=cnt))

    # 현지/문헌 중복
    field_set = {s.sci_name for s in sp_list
                 if any(_has_present(v) for k,v in s.rounds.items() if "현지" in k)}
    lit_set   = {s.sci_name for s in sp_list
                 if any(_has_present(v) for k,v in s.rounds.items() if "문헌" in k)}
    both      = len(field_set & lit_set)

    # 개체수 합 (현지_합계 숫자)
    total_ind = 0
    for s in sp_list:
        v = s.rounds.get("현지_합계")
        if isinstance(v, (int, float)): total_ind += int(v)

    # 목별 집계
    order_map = defaultdict(list)
    for s in sp_list: order_map[s.order].append(s)

    orig_order = []
    seen = set()
    for s in sp_list:
        if s.order not in seen:
            orig_order.append(s.order)
            seen.add(s.order)

    order_stats = []
    for o in orig_order:
        sps = order_map[o]
        fams = set(s.family for s in sps)
        r_stats = [RoundStat(rn, sum(1 for s in sps if _has_present(s.rounds.get(rn))))
                   for rn in rnames]
        order_stats.append(OrderStat(
            order=o, total=len(sps), ratio=len(sps)/total if total else 0,
            round_stats=r_stats, family_count=len(fams),
        ))

    order_sorted = sorted(order_stats, key=lambda x:-x.total)
    order_counts = {o.order: o.total for o in order_stats}
    div = _calc_div(order_counts)

    # 과수
    fam_count = len(set(s.family for s in sp_list if s.family))

    # 생활형 (조류 전용)
    life_stats = {}
    if sheet.taxon == "bird":
        lfc = sheet.meta.field_cols.get("life")
        if lfc is not None:
            for s in sp_list:
                code = str(s.rounds.get("life", "") or "").strip().upper()
                if not code: continue
                for part in code.split("+"):
                    p = part.strip()
                    if p: life_stats[p] = life_stats.get(p,0)+1

    return TaxaStats(
        sheet_name=sheet.name, taxon=sheet.taxon,
        total_species=total, total_individuals=total_ind,
        round_names=rnames, round_totals=round_totals,
        order_stats=order_sorted, order_stats_orig=order_stats,
        family_count=fam_count, div=div,
        lit_only=len(lit_set-field_set),
        field_only=len(field_set-lit_set),
        both=both, life_stats=life_stats,
    )


# ── 수생동물 분석 ─────────────────────────────────────────────────────────────
def analyze_aquatic(sheet: ParsedAquatic) -> AquaticStats:
    sp_list = sheet.species
    rnames  = sheet.meta.round_names
    total   = len(sp_list)

    # 회차별 개체수 합 (현지_N차_종합 컬럼)
    round_totals = []
    for rn in rnames:
        cnt = sum(_int(s.rounds.get(rn)) for s in sp_list)
        round_totals.append(RoundStat(name=rn, count=cnt))

    total_ind = sum(s.total for s in sp_list)

    # 목별
    order_map = defaultdict(list)
    for s in sp_list: order_map[s.order].append(s)

    orig_order = []
    seen = set()
    for s in sp_list:
        if s.order not in seen:
            orig_order.append(s.order)
            seen.add(s.order)

    order_stats = []
    for o in orig_order:
        sps  = order_map[o]
        fams = set(s.family for s in sps)
        r_stats = [RoundStat(rn, sum(_int(s.rounds.get(rn)) for s in sps))
                   for rn in rnames]
        order_stats.append(OrderStat(
            order=o, total=len(sps), ratio=len(sps)/total if total else 0,
            round_stats=r_stats, family_count=len(fams),
        ))

    order_sorted = sorted(order_stats, key=lambda x:-x.total)
    div = _calc_div({o.order: o.total for o in order_stats})
    fam_count = len(set(s.family for s in sp_list if s.family))

    return AquaticStats(
        sheet_name=sheet.name, taxon=sheet.taxon,
        total_species=total, total_individuals=total_ind,
        round_names=rnames, round_totals=round_totals,
        order_stats=order_sorted, order_stats_orig=order_stats,
        family_count=fam_count, div=div,
    )


# ── 식물 분석 ─────────────────────────────────────────────────────────────────
def analyze_plant(sheet: ParsedPlant) -> PlantStats:
    sp_list = sheet.species
    rnames  = sheet.meta.round_names
    total   = len(sp_list)

    round_totals = []
    for rn in rnames:
        cnt = sum(1 for s in sp_list if _has_present(s.rounds.get(rn)))
        round_totals.append(RoundStat(name=rn, count=cnt))

    field_set = {s.sci_name for s in sp_list
                 if any(_has_present(v) for k,v in s.rounds.items() if "현지" in k)}
    lit_set   = {s.sci_name for s in sp_list
                 if any(_has_present(v) for k,v in s.rounds.items() if "문헌" in k)}

    fam_count = len(set(s.family for s in sp_list if s.family))

    return PlantStats(
        sheet_name=sheet.name, taxon=sheet.taxon,
        total_species=total, round_names=rnames, round_totals=round_totals,
        family_count=fam_count,
        lit_only=len(lit_set - field_set),
        field_only=len(field_set - lit_set),
        both=len(field_set & lit_set),
    )


# ── 희귀특산 분석 ─────────────────────────────────────────────────────────────
def analyze_plant_special(sheet: ParsedPlantSpecial) -> PlantSpecialStats:
    sp_list = sheet.species
    rnames  = sheet.meta.round_names

    by_cat = defaultdict(int)
    for s in sp_list:
        for c in s.category.split("\n"):
            c = c.strip()
            if c: by_cat[c] += 1

    round_totals = []
    for rn in rnames:
        cnt = sum(1 for s in sp_list if _has_present(s.rounds.get(rn)))
        round_totals.append(RoundStat(name=rn, count=cnt))

    return PlantSpecialStats(
        sheet_name=sheet.name, total_species=len(sp_list),
        by_category=dict(by_cat),
        round_names=rnames, round_totals=round_totals,
    )


# ── 법정보호종 분석 ───────────────────────────────────────────────────────────
def analyze_protected(sheet: ParsedProtected) -> ProtectedStats:
    sp_list = sheet.species

    by_group = defaultdict(int)
    by_grade = defaultdict(int)
    unique_sp = set()
    
    for s in sp_list:
        # 전체조사차수 중 어느 하나라도 발견된 경우만 카운트
        if any(_has_present(s.rounds.get(rn)) for rn in sheet.round_names):
            if s.kor_name not in unique_sp:
                unique_sp.add(s.kor_name)
                by_group[s.group] += 1
                if s.extinction:
                    grade = "멸종위기 야생생물 Ⅰ급" if s.extinction in ("Ⅰ","Ⅰ급") else "멸종위기 야생생물 Ⅱ급"
                    by_grade[grade] += 1
                if s.monument:
                    by_grade["천연기념물"] += 1

    round_totals = []
    for rn in sheet.round_names:
        cnt = sum(1 for s in sp_list if _has_present(s.rounds.get(rn)))
        round_totals.append(RoundStat(name=rn, count=cnt))

    return ProtectedStats(
        sheet_name=sheet.name, total_species=len(unique_sp),
        by_group=dict(by_group), by_grade=dict(by_grade),
        round_names=sheet.round_names, round_totals=round_totals,
    )


# ── 전체 분석 ─────────────────────────────────────────────────────────────────
def analyze_all(parsed: dict) -> dict:
    result = {}
    for name, obj in parsed.items():
        if isinstance(obj, ParsedSheet):
            result[name] = analyze_land(obj)
        elif isinstance(obj, ParsedAquatic):
            result[name] = analyze_aquatic(obj)
        elif isinstance(obj, ParsedPlant):
            result[name] = analyze_plant(obj)
        elif isinstance(obj, ParsedPlantSpecial):
            result[name] = analyze_plant_special(obj)
        elif isinstance(obj, ParsedProtected):
            result[name] = analyze_protected(obj)
    return result
