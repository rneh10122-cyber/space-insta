"""사용해도 되는 사진인지 출처 표기를 보고 판단합니다.

원칙: NASA 등 공공 우주기관 크레딧만 있는 사진은 사용, 개인 사진가나 저작권 표시(©)가 있으면 건너뜁니다.
애매하면 건너뛰는 쪽으로 동작합니다(올리지 못한 게시물은 로그에 이유가 남습니다).
"""
import re

AGENCIES = [
    r"NASA", r"JPL", r"Caltech", r"JPL-Caltech", r"ESA", r"CSA", r"STScI", r"AURA",
    r"GSFC", r"Goddard", r"JSC", r"KSC", r"MSFC", r"LaRC", r"ARC", r"Ames",
    r"JHUAPL", r"APL", r"SwRI", r"ASU", r"MSSS", r"LANL", r"CNES", r"IRAP",
    r"NOAA", r"USGS", r"SDO", r"SOHO", r"Hubble", r"Webb", r"JWST", r"Chandra",
    r"CXC", r"SAO", r"ISS", r"Expedition\s*\d+", r"NSF", r"NOIRLab", r"NRAO",
    r"University of Arizona", r"UArizona", r"Johns Hopkins APL", r"Space Science Institute",
    r"ESA/Hubble", r"ESA/Webb", r"Roscosmos",
]
_AGENCY_RE = re.compile(r"^(?:%s)$" % "|".join(AGENCIES), re.I)
_PERSON_RE = re.compile(r"^[A-Z][a-zA-Z.'\-]*(?:\s+[A-Z][a-zA-Z.'\-]*){0,3}$")


def _tokens(credit: str) -> list[str]:
    credit = re.sub(r"\(.*?\)", "", credit)            # 괄호 속 소속 표기 제거
    parts = re.split(r"\s*(?:/|,|;|&|\band\b)\s*", credit)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def check(item) -> tuple[bool, str, str]:
    """(사용 가능 여부, 이유, 게시물에 표기할 출처)"""
    if item.source == "apod" and item.copyright:
        return False, f"APOD 제3자 저작물(© {item.copyright})", ""

    credit = (item.credit_raw or "").strip()
    if item.source == "apod":
        return True, "APOD NASA 제공", credit or "NASA"

    if not credit:
        return False, "캡션에 출처 표기가 없음", ""
    if re.search(r"©|copyright|all rights reserved|getty|reuters|\bAP\b|AFP", credit, re.I):
        return False, f"저작권 표시가 있는 출처: {credit}", ""

    toks = _tokens(credit)
    if not toks:
        return False, "출처를 해석할 수 없음", ""
    if all(_AGENCY_RE.match(t) for t in toks):
        return True, "공공기관 크레딧", credit
    # "NASA/Bill Ingalls" 처럼 NASA 소속 사진가 표기
    if _AGENCY_RE.match(toks[0]) and toks[0].upper().startswith("NASA") and all(
        _AGENCY_RE.match(t) or _PERSON_RE.match(t) for t in toks[1:]
    ):
        return True, "NASA 소속 사진가 크레딧", credit
    return False, f"제3자가 포함된 출처: {credit}", ""
