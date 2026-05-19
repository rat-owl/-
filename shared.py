def _s(v) -> str:
    return str(v).strip() if v is not None else ""


def _has(v, false_strings=("", "None", "-"), positive_numeric=True) -> bool:
    if v is None:
        return False
    if positive_numeric and isinstance(v, (int, float)):
        return v > 0
    return _s(v) not in tuple(false_strings)

import re
from config import SETTINGS

def _has_present(v) -> bool:
    if v is None: return False
    if isinstance(v, (int, float)):
        return v > 0
    return str(v).strip() not in ("","None","-","0","0.0","x","X","×")

_SYM_RE = None

def _apply_title(text: str, title: str) -> str:
    global _SYM_RE
    from config import SETTINGS
    add_period = getattr(SETTINGS, "sent_add_period", False)

    if _SYM_RE is None:
        _SYM_RE = re.compile(r'^([◦•·▪○▸▷\-\*]\s*)')
        
    if not title or not title.strip():
        if not add_period:
            return text
        pfx = ""
    else:
        pfx = title.strip() + " "

    out = []
    for line in text.split("\n"):
        if not line.strip():
            out.append(line)
            continue
            
        processed_line = line
        if pfx:
            m = _SYM_RE.match(line)
            if m:
                sym  = m.group(1)
                rest = line[len(sym):]
                processed_line = sym + pfx + rest
            else:
                processed_line = pfx + line
                
        if add_period and not processed_line.rstrip().endswith("."):
            processed_line = processed_line.rstrip() + "."
            
        out.append(processed_line)
    return "\n".join(out)

_LOCAL_REGION_ALIASES = {
    "서울": ("서울", "서울시 보호 야생생물"),
    "서울시": ("서울", "서울시 보호 야생생물"),
    "부산": ("부산", "부산시"),
    "부산시": ("부산", "부산시"),
    "대구": ("대구", "대구시"),
    "대구시": ("대구", "대구시"),
    "인천": ("인천", "인천시"),
    "인천시": ("인천", "인천시"),
    "광주": ("광주", "광주시"),
    "광주시": ("광주", "광주시"),
    "대전": ("대전", "대전시"),
    "대전시": ("대전", "대전시"),
    "울산": ("울산", "울산시"),
    "울산시": ("울산", "울산시"),
    "경기": ("경기", "경기도보호 야생생물"),
    "경기도": ("경기", "경기도보호 야생생물"),
    "강원": ("강원", "강원도"),
    "강원도": ("강원", "강원도"),
    "충북": ("충북", "충청북도"),
    "충청북도": ("충북", "충청북도"),
    "충남": ("충남", "충청남도"),
    "충청남도": ("충남", "충청남도"),
    "전북": ("전북", "전라북도"),
    "전라북도": ("전북", "전라북도"),
    "전남": ("전남", "전라남도"),
    "전라남도": ("전남", "전라남도"),
    "경북": ("경북", "경상북도"),
    "경상북도": ("경북", "경상북도"),
    "경남": ("경남", "경상남도"),
    "경상남도": ("경남", "경상남도"),
    "제주": ("제주", "제주도"),
    "제주도": ("제주", "제주도"),
}

def _local_region(sp) -> tuple[str, str]:
    text = " ".join(str(x or "") for x in (
        getattr(sp, "region", ""),
        getattr(sp, "remark", ""),
        getattr(sp, "group", ""),
        getattr(sp, "monument", ""),
        getattr(sp, "extinction", ""),
    ))
    for key, val in _LOCAL_REGION_ALIASES.items():
        if key in text:
            return val
    return "", ""

def _is_local_protected(sp) -> bool:
    text = " ".join(str(x or "") for x in (
        getattr(sp, "region", ""),
        getattr(sp, "remark", ""),
        getattr(sp, "group", ""),
        getattr(sp, "monument", ""),
        getattr(sp, "extinction", ""),
    ))
    if "시도" in text or "시·도" in text or "시ㆍ도" in text or "시도보호" in text:
        return True
    short_region, full_region = _local_region(sp)
    return bool(short_region or full_region)

def _local_prot_label(sp, mode: str) -> str:
    short_region, full_region = _local_region(sp)
    if mode == "full":
        return f"{full_region}"
    if mode == "short":
        return f"{short_region}"
    return ""

def _prot_grade_str(sp) -> str:
    mode = getattr(SETTINGS, "prot_grade_mode", "short")
    if _is_local_protected(sp):
        return _local_prot_label(sp, mode)
    if mode == "none":
        return ""

    grades = []
    group = str(getattr(sp, "group", "") or "").strip()
    remark = str(getattr(sp, "remark", "") or "").strip()
    mon = str(sp.monument  or "").strip()
    ext = str(sp.extinction or "").strip()

    def _add_once(short, full):
        val = full if mode == "full" else short
        if val and val not in grades:
            grades.append(val)

    # 멸종위기종 (희귀·특산 여부에 관계없이 extinction 값이 있으면 표시)
    if ext and ext not in ("", "None", "-"):
        # "Ⅰ급" / "Ⅱ급" → "Ⅰ" / "Ⅱ" 정규화
        _ext_norm = ext.replace("1급", "Ⅰ").replace("2급", "Ⅱ").replace("급", "").strip()
        if mode == "full":
            if "Ⅰ" in _ext_norm:
                grades.append("멸종위기 야생생물 Ⅰ급")
            elif "Ⅱ" in _ext_norm:
                grades.append("멸종위기 야생생물 Ⅱ급")
            # 등급 불명확하면 표시 생략
        else:
            if "Ⅰ" in _ext_norm:
                grades.append("멸Ⅰ")
            elif "Ⅱ" in _ext_norm:
                grades.append("멸Ⅱ")
            # 등급 불명확하면 표시 생략

    if mon and mon not in ("", "None", "-"):
        _add_once("천", "천연기념물")

    # 희귀식물 (멸종위기와 동시 표시 가능 — 예: 매화마름(멸Ⅱ, 희귀))
    if "희귀" in group:
        _add_once("희귀", "희귀식물")

    # 특산식물
    if "특산" in group:
        _add_once("특산", "특산식물")

    grades.sort(key=lambda x: (0 if "멸" in x else 1 if "천" in x else 2 if "희귀" in x else 3 if "특산" in x else 99))
    return ", ".join(grades)

def _prot_group_matches(taxon: str, group: str, sp=None) -> bool:
    g = str(group or "").strip()
    if not g:
        return True
    aliases = {
        "mammal": ("포유류", "포유"),
        "bird": ("조류", "새류", "조강"),
        "herp": ("양서류", "파충류", "양서", "파충", "양서류·파충류", "양서·파충류", "양서파충류"),
        "insect": ("곤충류", "곤충", "육상곤충류", "육상곤충"),
        "fish": ("어류", "담수어류", "어류상"),
        "benthos": ("저서", "저서성", "대형무척추", "무척추"),
    }
    explicit = []
    for vals in aliases.values():
        explicit.extend(vals)
    if any(x in g for x in aliases.get(taxon, ())):
        return True
    if any(x in g for x in explicit):
        return False
    # 시도보호종 행처럼 구분 칸에 지역명만 있는 경우는 종명 매칭으로 판단한다.
    return _is_local_protected(sp) if sp is not None else False


def _prot_list_graded(taxon, prot_sheet, species_list, all_groups=False):
    if not prot_sheet: return 0, ""
    tmap = {"mammal":"포유류","bird":"조류",
            "herp":"양서류·파충류","insect":"곤충류"}
    my = "" if all_groups else tmap.get(taxon, "")
    names = {sp.kor_name for sp in species_list}
    prot  = [sp for sp in prot_sheet.species
             if sp.kor_name in names and (all_groups or _prot_group_matches(taxon, sp.group, sp))]
    if not prot: return 0, ""
    by_name = {}
    for sp in prot:
        by_name.setdefault(sp.kor_name, [])
        g = _prot_grade_str(sp)
        if g and g not in by_name[sp.kor_name]:
            by_name[sp.kor_name].append(g)
    parts = []
    for name, grades in by_name.items():
        parts.append(f"{name}({', '.join(grades)})" if grades else name)
    return len(by_name), ", ".join(parts)


def _ecosystem_disturber_list(prot_sheet, species_list):
    # 호환을 위해 prot_sheet 인자는 유지하되, 판정은 생물상 species_list만 사용한다.
    if not species_list:
        return 0, ""
    found = []

    def _is_disturber_from_species(sp) -> bool:
        group_txt = str(getattr(sp, "group", "") or "")
        remark_txt = str(getattr(sp, "remark", "") or "")
        text = f"{group_txt} {remark_txt}"

        # 명시 표기 우선: 생태계교란/교란
        if "생태계교란" in text or "교란" in text:
            return True

        # 비고/구분의 단독 코드 표기(예: "교")도 교란생물로 간주
        marker_text = f"{group_txt},{remark_txt}"
        return re.search(r"(^|[\s,;/()\[\]{}|])교($|[\s,;/()\[\]{}|])", marker_text) is not None

    for sp in species_list:
        if not _is_disturber_from_species(sp):
            continue
        name = str(getattr(sp, "kor_name", "") or getattr(sp, "sci_name", "")).strip()
        if not name:
            continue
        if name not in found:
            found.append(name)
    return len(found), ", ".join(found)


def _last_hangul_char(text: str) -> str:
    for ch in reversed(str(text or "")):
        if 0xAC00 <= ord(ch) <= 0xD7A3:
            return ch
    return ""


def _has_batchim(text: str) -> bool:
    ch = _last_hangul_char(text)
    if not ch:
        return False
    return (ord(ch) - 0xAC00) % 28 != 0


def _resolve_iga(template: str, subject: str = "") -> str:
    s = str(template or "")
    if "이(가)" in s:
        return s.replace("이(가)", "이" if _has_batchim(subject) else "가")
    return s


_JOSA_TABLE = {
    "이가": ("이", "가"), "은는": ("은", "는"),
    "을를": ("을", "를"), "과와": ("과", "와"),
}

def _josa(subject: str, type: str) -> str:
    """받침 유무에 따라 올바른 조사를 반환.
    type: '이가' | '은는' | '을를' | '과와' | '으로로'
    '으로로': 받침 없음·ㄹ받침 → '로', 그 외 받침 → '으로'
    """
    if type == "으로로":
        ch = _last_hangul_char(subject)
        if not ch:
            return "로"
        jong = (ord(ch) - 0xAC00) % 28
        return "으로" if (jong != 0 and jong != 8) else "로"
    return _JOSA_TABLE[type][0 if _has_batchim(subject) else 1]
