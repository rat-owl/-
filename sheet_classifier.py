"""Sheet-name classifier for taxa workbooks."""

SHEET_TYPE_MAP = {
    # 육상동물
    "포유류": "mammal",
    "조류": "bird",
    "양서파충류": "herp",
    "양서·파충류": "herp",
    "양서류·파충류": "herp",
    "양서류파충류": "herp",
    "곤충류": "insect",
    # 육수
    "어류상": "fish",
    "어류": "fish",
    "저서상": "benthos",
    "저서동물상": "benthos",
    "저서성대형무척추동물상": "benthos",
    "저서무척추동물상": "benthos",
    # 식물
    "식물상": "plant",
    "귀화식물": "plant_sub",
    "귀화율식물": "plant_sub",
    "교란생물": "plant_sub",
    "생태계교란생물": "plant_sub",
    "생태계교란야생식물": "plant_sub",
    "멸종위기종": "plant_sub",
    "습생식물": "plant_sub",
    "구계학적특정식물": "plant_sub",
    "구계학적 특정식물": "plant_sub",
    "국가적색목록식물": "plant_special",
    "희귀·특산식물": "plant_special",
    "희귀특산식물": "plant_special",
    "특산식물": "plant_special",
    "희귀식물": "plant_special",
    # 법정보호종
    "법정보호종": "protected",
    "법정보호종목록": "protected",
}


TAXON_LABEL = {
    "mammal": "포유류",
    "bird": "조류",
    "herp": "양서·파충류",
    "insect": "곤충류",
    "fish": "어류상",
    "benthos": "저서상",
    "plant": "식물상",
    "plant_sub": "식물상(보조)",
    "plant_special": "국가적색목록식물",
    "protected": "법정보호종",
}


def _normalize_sheet_name(name: str) -> str:
    return "".join(str(name or "").strip().split())


def classify_sheet(name: str) -> str | None:
    raw = str(name or "").strip()
    norm = _normalize_sheet_name(raw)

    direct = SHEET_TYPE_MAP.get(raw)
    if direct is not None:
        return direct

    direct = SHEET_TYPE_MAP.get(norm)
    if direct is not None:
        return direct

    for key, taxon in SHEET_TYPE_MAP.items():
        key_norm = _normalize_sheet_name(key)
        if norm == key_norm:
            return taxon

    for key, taxon in sorted(SHEET_TYPE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        key_norm = _normalize_sheet_name(key)
        if key_norm and key_norm in norm:
            return taxon

    # 2차 보정: 시트명 변형에 강하게 대응
    if "저서" in norm:
        return "benthos"
    if "어류" in norm:
        return "fish"
    if "교란" in norm:
        return "plant_sub"
    if "귀화" in norm:
        return "plant_sub"
    if "구계학" in norm or "습생" in norm or "멸종" in norm:
        return "plant_sub"
    if "희귀" in norm or "특산" in norm or "적색" in norm:
        return "plant_special"
    if "식물" in norm:
        return "plant"
    if "법정보호" in norm:
        return "protected"

    return None
