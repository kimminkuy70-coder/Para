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
    # 새로 파싱해 만드는 양식(name_lookup 넘김·base_keys 유무 무관) → 기억한 이름으로 자동 채움
    ents_new = em.build_entries(pivot, base_keys=None, name_lookup=cb)
    assert ents_new[0]["name"] == "밝기 민감도"
    assert ents_new[0]["orig"] == "BrightSeedTh"     # 원본은 실제 ini 키 유지
    # 기존 레시피 활용(base_keys 지정)이어도 새로 파싱한 양식이면 자동 채움된다
    ents_based = em.build_entries(
        pivot, base_keys={("genesis", "genesis", "brightsensitivity")}, name_lookup=cb)
    assert ents_based[0]["name"] == "밝기 민감도"
    # 기존 양식을 그대로 여는 경로(호출측이 name_lookup 안 넘김) → 원 이름 유지
    ents_edit = em.build_entries(pivot, base_keys=None, name_lookup=None)
    assert ents_edit[0]["name"] == "Bright Sensitivity"
    ok("새로 파싱=자동 채움(base 유무 무관) / 기존 양식 그대로 열기=이름 유지")


def test_use_checkbox_memory():
    """확정한 체크박스 상태(사용 Y/N)를 기억해 새 양식에서 파서 기본값을 덮어쓴다."""
    rows = []
    selected = [
        {"alg": "Genesis", "ext": {"key": "BrightSeedTh"},
         "name": "밝기 민감도", "reco": "Bright Sensitivity", "use": True},
        {"alg": "Surface", "ext": {"key": "Elongation"},
         "name": "Elongation", "reco": "Elongation", "use": False},
    ]
    assert ns.apply_selected(rows, selected) == 2
    assert rows[0]["사용"] == "Y" and rows[1]["사용"] == "N"
    # 파일 왕복 후에도 사용 상태 보존
    d = tempfile.mkdtemp()
    p = os.path.join(d, ns.NAME_FILENAME)
    ns.save(p, rows)
    back = ns.load(p)
    assert ns.use_of(back, "Genesis", "BrightSeedTh") is True
    assert ns.use_of(back, "Surface", "Elongation") is False
    assert ns.use_of(back, "Surface", "NeverSeen") is None
    # 새 양식: 파서 기본값과 반대라도 기억한 체크 상태가 우선
    pivot = [_pivot("Genesis", "BrightSeedTh", "Bright Sensitivity", use=False),
             _pivot("Surface", "Elongation", "Elongation", use=True)]
    ents = em.build_entries(pivot, base_keys=None,
                            name_lookup=ns.make_lookup(back),
                            use_lookup=ns.make_use_lookup(back))
    assert ents[0]["use"] is True and ents[0]["name"] == "밝기 민감도"
    assert ents[1]["use"] is False
    ok("체크박스 상태 기억·파일 왕복·새 양식 자동 적용(파서 기본값 덮어씀)")


def test_use_overrides_base_keys():
    """기존 레시피 활용(base_keys)로 체크될 항목도 기억한 사용=N 이면 해제된다."""
    rows = [{"Alg": "Surface", "원본항목": "Elongation", "장비화면이름": "Elongation",
             "사용": "N", "비고": ""}]
    pivot = [_pivot("Surface", "Elongation", "Elongation")]
    ents = em.build_entries(
        pivot, base_keys={("surface", "surface", "elongation")},
        name_lookup=ns.make_lookup(rows), use_lookup=ns.make_use_lookup(rows))
    assert ents[0]["use"] is False       # base_keys 로는 체크지만 기억이 우선
    ok("기억한 사용 상태가 base_keys 보다 우선")


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
