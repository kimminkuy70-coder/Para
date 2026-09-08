"""namestore 헤드리스 테스트 — 장비 화면 항목 이름 기억/자동 채움.

같은 alg·같은 원본 파라미터면 지난번 저장한 장비 화면 이름을 자동으로 불러오는지,
기존 양식 수정 때는 그 양식 이름을 유지하는지(회귀 방지) 검증.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import namestore as ns          # noqa: E402
from param_manager import editor_model as em        # noqa: E402

PASS = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"[PASS] {msg}")


def _pivot(alg, key, param, use=True):
    return {"zone": alg, "alg": alg, "mag": "PI", "param": param,
            "raws": {"AOI-1": "1"}, "use": use,
            "extract": {"key": key, "section": alg, "transform": "RAW"}}


def test_apply_and_lookup_roundtrip():
    rows = []
    # 표시 이름을 실제로 바꾼 것만 기억(이름==원본키면 저장 안 함)
    n = ns.apply_records(
        rows,
        [{"Alg": "Genesis", "Parameter": "밝기 민감도"},
         {"Alg": "Surface", "Parameter": "EdgeUncert_Bright"}],   # 안 바꿈 → 무시
        [{"key": "BrightSeedTh"}, {"key": "EdgeUncert_Bright"}])
    assert n == 1 and len(rows) == 1
    d = tempfile.mkdtemp()
    p = os.path.join(d, ns.NAME_FILENAME)
    ns.save(p, rows)
    back = ns.load(p)
    assert ns.lookup(back, "Genesis", "BrightSeedTh") == "밝기 민감도"
    # 대소문자·구분자 무시 매칭
    assert ns.lookup(back, "genesis", "bright_seed_th") == "밝기 민감도"
    ok("apply_records(바뀐 것만)·파일 왕복·정규화 lookup")


def test_new_form_autofill_but_edit_keeps():
    rows = [{"Alg": "Genesis", "원본항목": "BrightSeedTh",
             "장비화면이름": "밝기 민감도", "비고": ""}]
    cb = ns.make_lookup(rows)
    pivot = [_pivot("Genesis", "BrightSeedTh", "Bright Sensitivity")]
    # 새 양식(base_keys=None) → 기억한 이름으로 자동 채움
    ents_new = em.build_entries(pivot, base_keys=None, name_lookup=cb)
    assert ents_new[0]["name"] == "밝기 민감도"
    assert ents_new[0]["orig"] == "BrightSeedTh"     # 원본은 실제 ini 키 유지
    # 기존 양식 수정(base_keys 지정) → 자동 채움 안 함(양식 이름 유지)
    ents_edit = em.build_entries(
        pivot, base_keys={("genesis", "genesis", "brightsensitivity")}, name_lookup=cb)
    assert ents_edit[0]["name"] == "Bright Sensitivity"
    ok("새 양식=자동 채움 / 기존 양식 수정=이름 유지")


def test_upsert_last_write_wins():
    rows = []
    ns.upsert(rows, "Surface", "EdgeUncert_Bright", "밝기 불확실")
    ns.upsert(rows, "Surface", "EdgeUncert_Bright", "밝기 언서튼티")  # 마지막 승
    assert len(rows) == 1 and rows[0]["장비화면이름"] == "밝기 언서튼티"
    ok("upsert 마지막 저장 우선(같은 키 1행)")


if __name__ == "__main__":
    for t in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        t()
    print(f"\n==== {PASS}/{PASS} passed ====")
