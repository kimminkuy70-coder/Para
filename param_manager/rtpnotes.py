"""RTP.txt 설명 → 값 확인 비고(영문 원문 + 한글 번역) — 이슈 #23.

RTP.txt 의 각 파라미터 줄 `키 = 값 ; in {단위} ( 설명~코드 )` 에서 '설명'(영문 원문)을
읽어, ini 파서가 만든 행(Zone, Alg, Parameter, 설정키)에 붙인다. 한글 번역은
번들된 통일안(`data/rtp_template.json` 의 desc_kr — RTP 표시명 기준)에서 찾는다
(런타임 인터넷 번역 없음). 번역이 없으면 영문만.

매칭(같은 config 폴더의 RTP.txt 안에서만):
  이름 = 표시명에서 끝의 단위 괄호(`(µ)`, `(area, µ)`, `[µm]`)를 뗀 정규화 키,
         + coef_detector 의 알려진 (RTP키 ↔ INI키) 쌍, + 원래 설정키.
  순서 = (Zone, Alg, 이름) → (Zone, 이름) → (Alg, 이름) → 이름(설명이 하나뿐일 때만).
  Alg 는 끝의 버전 꼬리(GenesisV12 → genesis)를 무시한다.
원본은 읽기만 한다.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import coef_detector, rtp_parser

_UNIT_TAIL = re.compile(r"\s*(\([^()]*\)|\[[^\[\]]*\])\s*$")
_ALG_VER = re.compile(r"v\d+$")


def name_key(name) -> str:
    s = rtp_parser.display_name(str(name or "").replace("\\_", "_"))
    while True:
        t = _UNIT_TAIL.sub("", s)
        if t == s or not t:
            break
        s = t
    return rtp_parser.norm_key(s)


def alg_key(alg) -> str:
    return _ALG_VER.sub("", rtp_parser.norm_key(str(alg or "").replace("\\_", "_")))


def zone_key(zone) -> str:
    return rtp_parser.norm_key(str(zone or "").replace("\\_", "_"))


# INI 키 → RTP 키 (coef_detector 의 알려진 쌍)
_INI_TO_RTP: dict[tuple[str, str], str] = {}
for _alg, _rules in coef_detector.PAIR_RULES.items():
    for _kind in ("linear", "area"):
        for _rk, _ik in _rules.get(_kind, []):
            _INI_TO_RTP.setdefault((alg_key(_alg), name_key(_ik)), _rk)


class _Index:
    """한 RTP.txt 의 설명 색인."""

    def __init__(self, rows):
        self.zap, self.zp, self.ap, self.p = {}, {}, {}, {}
        for zone, alg, param, desc in rows:
            n = name_key(param)
            if not n or not desc:
                continue
            item = (desc, rtp_parser.display_name(param), zone, alg)
            z, a = zone_key(zone), alg_key(alg)
            self.zap.setdefault((z, a, n), item)
            self.zp.setdefault((z, n), item)
            self.ap.setdefault((a, n), item)
            self.p.setdefault(n, {}).setdefault(desc, item)

    def find(self, zone, alg, names):
        z, a = zone_key(zone), alg_key(alg)
        keys = [n for n in dict.fromkeys(name_key(x) for x in names) if n]
        for table, mk in ((self.zap, lambda n: (z, a, n)), (self.zp, lambda n: (z, n)),
                          (self.ap, lambda n: (a, n))):
            for n in keys:
                if mk(n) in table:
                    return table[mk(n)]
        for n in keys:
            hits = self.p.get(n) or {}
            if len(hits) == 1:
                return next(iter(hits.values()))
        return None


_DIR_CACHE: dict[str, _Index | None] = {}


def read_rtp(path) -> list[tuple[str, str, str, str]]:
    """RTP.txt → [(zone, alg, param_raw, desc_en)] (설명이 있는 줄만)."""
    try:
        rows = rtp_parser.parse_rtp(path)
    except OSError:
        return []
    return [(r.zone, r.alg, r.param_raw, r.desc_en) for r in rows if r.desc_en]


def index_for_dir(config_dir) -> _Index | None:
    """config(레시피) 폴더의 RTP.txt 색인. 없으면 None. 파일 서명으로 캐시."""
    try:
        path = coef_detector.find_rtp(Path(config_dir))
    except OSError:
        path = None
    if not path:
        return None
    try:
        st = path.stat()
        key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        return None
    if key not in _DIR_CACHE:
        rows = read_rtp(path)
        _DIR_CACHE[key] = _Index(rows) if rows else None
    return _DIR_CACHE[key]


# ---- 한글 번역(번들 통일안) --------------------------------------------------
_KR = None


def _kr_index():
    global _KR
    if _KR is None:
        zap, ap, p = {}, {}, {}
        for t in rtp_parser.load_template():
            kr = str(t.get("desc_kr") or "").strip()
            n = name_key(t.get("param"))
            if not kr or not n:
                continue
            z, a = zone_key(t.get("zone")), alg_key(t.get("alg"))
            zap.setdefault((z, a, n), kr)
            ap.setdefault((a, n), kr)
            p.setdefault(n, set()).add(kr)
        _KR = (zap, ap, p)
    return _KR


def translate(zone, alg, param) -> str:
    """RTP 표시명 기준 한글 설명. 없으면 ''."""
    zap, ap, p = _kr_index()
    z, a, n = zone_key(zone), alg_key(alg), name_key(param)
    if (z, a, n) in zap:
        return zap[(z, a, n)]
    if (a, n) in ap:
        return ap[(a, n)]
    hits = p.get(n) or set()
    return next(iter(hits)) if len(hits) == 1 else ""


def note_text(desc_en: str, desc_kr: str = "") -> str:
    """비고 문구 = '영문 원문 / 한글 번역'(번역이 없거나 같으면 영문만)."""
    en, kr = str(desc_en or "").strip(), str(desc_kr or "").strip()
    if not en:
        return ""
    if kr and rtp_parser.norm_key(kr) != rtp_parser.norm_key(en):
        return f"{en} / {kr}"
    return en


def note_for(config_dir, zone, alg, param, section: str = "", key: str = "") -> tuple[str, str]:
    """ini 행 하나 → (desc_en, 비고 문구). RTP.txt 가 없거나 못 찾으면 ('', '')."""
    idx = index_for_dir(config_dir)
    if idx is None:
        return "", ""
    names = [param]
    if key:
        alias = _INI_TO_RTP.get((alg_key(section or alg), name_key(key)))
        if alias:
            names.append(alias)
        names.append(key)
    hit = idx.find(zone, alg, names) or (idx.find(zone, section, names) if section and section != alg else None)
    if not hit:
        return "", ""
    desc, rparam, rzone, ralg = hit
    return desc, note_text(desc, translate(rzone, ralg, rparam))
