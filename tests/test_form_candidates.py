"""'기존 양식 수정하기'의 후보 목록('원본') 감지·복구 규칙.

배경: 확정 양식에는 **체크해서 살린 항목만** 들어 있어서, 그것만으로 다시 열면
파라미터를 빼는 것만 되고 예전에 뺀 항목을 다시 넣을 수 없었다.
회차 폴더의 `관련파일/…_원본_….xlsx`(초안)에 전체 후보가 들어 있으므로 그것을
찾아 쓰고, 어느 버전에 그 파일이 있는지 사람에게 미리 알려 준다.

여기서 고정하는 것:
  ① 회차 폴더에서 후보 파일을 찾는다(_원본_ 우선, 없으면 _수정본_)
  ② 레시피/버전별로 '항목 추가 가능한가'를 판정해 안내할 수 있다
  ③ 앞으로 만드는 양식은 **화면 편집기로 확정해도** 원본을 남긴다(소스 규칙)
"""

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import formbuilder, ini_parser, workdirs  # noqa: E402

PASS = FAIL = 0
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "param_manager")

GLOBAL_RTP = """[GLOBAL_RTP]
MaxFaultsPerWafer = 3000
ApplyDieCalib = 1
"""
ZONE_INI = """[General]
ZoneName = PI Opening
[Surface]
High_Delta = 25
BrightLength = 5
"""


def run(fn):
    global PASS, FAIL
    print(f"[RUN] {fn.__name__}")
    try:
        fn()
        PASS += 1
        print(f"[PASS] {fn.__name__}\n")
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        import traceback
        print(f"[FAIL] {fn.__name__}: {e}")
        traceback.print_exc()
        print()


def _src(name: str) -> str:
    with open(os.path.join(SRC_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def _pivot(tmp):
    recipe = Path(tmp) / "R_TB500_PI3" / "PI"
    recipe.mkdir(parents=True, exist_ok=True)
    (recipe / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
    (recipe / "Zones").mkdir(exist_ok=True)
    (recipe / "Zones" / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")
    cfgs = ini_parser.scan_tree(Path(tmp) / "R_TB500_PI3", default_equipment="AOI-13")
    rows, _machines = ini_parser.build_pivot(cfgs)
    return rows


def _make_version(save_dir, st, rows, with_original=True, with_draft=False):
    """회차 하나를 만든다 — 확정본 + (선택) 관련파일의 원본/수정본."""
    run_dir = workdirs.form_run_dir(save_dir, "PI3", st)
    init = os.path.join(tempfile.mkdtemp(), "init.xlsx")
    formbuilder.build_initial_workbook(rows, init, level="PI3")
    final = workdirs.form_final_path(run_dir, "PI3", "AOI-13", st)
    formbuilder.build_final_from_initial(init, final, level="PI3", aoi="AOI-13")
    rel = workdirs.related_dir(run_dir)
    if with_original:
        formbuilder.build_initial_workbook(
            rows, workdirs.form_original_path(rel, "PI3", "AOI-13", st), level="PI3")
    if with_draft:
        formbuilder.build_initial_workbook(
            rows, workdirs.form_draft_path(rel, "PI3", "AOI-13", st), level="PI3")
    return run_dir, final


# --------------------------------------------------------------------------
def test_candidate_lookup_prefers_original():
    """후보 파일은 `_원본_` 우선 — `_수정본_` 은 엑셀에서 행을 지웠을 수 있어 2순위."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = _pivot(tmp)
        save = os.path.join(tmp, "저장")
        run_dir, _f = _make_version(save, "20260811_1000", rows,
                                    with_original=True, with_draft=True)
        got = workdirs.form_candidate_path(run_dir)
        assert got and "_원본_" in os.path.basename(got), got

        # 원본을 지우면 수정본으로 폴백
        os.remove(got)
        got2 = workdirs.form_candidate_path(run_dir)
        assert got2 and "_수정본_" in os.path.basename(got2), got2

        # 둘 다 없으면 None (= 항목 추가 불가)
        os.remove(got2)
        assert workdirs.form_candidate_path(run_dir) is None
        # 관련파일 폴더 자체가 없어도 조용히 None
        empty = workdirs.form_run_dir(save, "PI3", "20260811_0900")
        assert workdirs.form_candidate_path(empty) is None
    print("  후보 파일 탐색(_원본_ 우선 → _수정본_ → 없음) OK")


def test_version_status_flags_addable_versions():
    """버전마다 '항목 추가 가능'인지 판정해 안내할 수 있어야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = _pivot(tmp)
        save = os.path.join(tmp, "저장")
        _make_version(save, "20260811_1000", rows, with_original=False)   # 구 회차
        _make_version(save, "20260811_1200", rows, with_original=True)    # 새 회차
        st = workdirs.form_version_status(save, "PI3")
        assert [v["stamp"] for v in st] == ["20260811_1200", "20260811_1000"], st
        assert st[0]["has_candidate"] is True and st[0]["kind"] == "원본"
        assert st[1]["has_candidate"] is False and st[1]["kind"] == ""
        assert os.path.isfile(st[0]["final"])
        # 고른 버전에 원본이 없어도 같은 레시피의 다른 회차에서 빌려올 수 있다
        borrowed = workdirs.any_candidate_for(save, "PI3")
        assert borrowed and "20260811_1200" in borrowed, borrowed
        # 후보가 하나도 없는 레시피는 None
        _make_version(save, "20260811_1300", rows, with_original=False)
        assert workdirs.any_candidate_for(save, "RDL1") is None
    print("  버전별 '원본 있음' 판정 + 다른 회차 빌려오기 OK")


def test_status_survives_recipe_without_versions():
    """확정본이 없는 레시피 폴더에서도 예외 없이 빈 목록."""
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장")
        workdirs.form_recipe_dir(save, "PI3")
        assert workdirs.form_version_status(save, "PI3") == []
        assert workdirs.any_candidate_for(save, "PI3") is None
        assert workdirs.form_version_status(save, "없는레시피") == []
    print("  확정본 없는 레시피도 안전 OK")


def test_editor_always_saves_original():
    """화면 편집기로 **바로 확정**해도 원본(전체 후보)을 남겨야 한다.

    이걸 빼면 그 회차는 나중에 '기존 양식 수정하기'로 열어도 항목을 다시 넣을
    수 없다(실제로 그래서 문제가 됐다). 소스 수준에서 고정한다.
    """
    src = _src("equip_app.py")
    m = re.search(r"def _form_param_editor.*?(?=\n    def _)", src, re.S)
    assert m, "_form_param_editor 를 찾지 못함"
    body = m.group(0)
    conf = re.search(r"\n        def confirm\(\).*?(?=\n        def |\Z)", body, re.S)
    assert conf, "confirm() 을 찾지 못함"
    cbody = conf.group(0)
    # ① 다른 저장 경로(on_confirm)로 넘어가기 전에 원본을 남긴다
    assert "_save_candidate_snapshot" in cbody, \
        "on_confirm 경로에서 원본(전체 후보)을 저장하지 않음"
    # ② 기본(양식 만들기) 경로도 확정과 함께 원본을 남긴다
    assert "form_original_path" in cbody and "build_initial_workbook" in cbody, \
        "기본 확정 경로에서 원본(전체 후보)을 저장하지 않음"
    # 저장 실패가 확정을 막으면 안 된다(비치명 로그)
    assert "_logerr" in cbody, "원본 저장 실패를 치명적으로 다루고 있음"
    print("  화면 편집기 확정도 원본을 남긴다 OK")


def test_edit_existing_form_uses_candidates():
    """'기존 양식 수정하기'가 후보 목록을 쓰고, 없으면 사람에게 알리고 물어본다."""
    src = _src("equip_app.py")
    m = re.search(r"def _edit_existing_form.*?(?=\n    def )", src, re.S)
    assert m, "_edit_existing_form 를 찾지 못함"
    body = m.group(0)
    assert "form_version_status" in body, "버전별 원본 유무를 조사하지 않음"
    assert "initial_to_pivot" in body and "merge_form_into_candidates" in body, \
        "후보 목록으로 열지 않음(확정본만 쓰면 빼기만 가능)"
    assert "_ask_edit_source" in body, "무엇을 기준으로 열지 고르는 단계가 없음"
    # 원본이 있든 없든 '장비/로컬에서 다시 읽기'로 갈 수 있어야 한다 —
    # 파서 규칙이 바뀌면 저장된 스냅샷에는 반영되지 않기 때문.
    assert re.search(r'choice in \("EQUIP", "LOCAL"\)', body), \
        "다시 읽기 경로로 분기하지 않음"
    assert "_recollect_for_edit" in body
    # 후보로 열 때 default_use=True 면 전부 체크돼 '무엇이 빠졌는지'가 사라진다
    assert re.search(r"default_use=\(None if cand else True\)", body), \
        "후보 목록을 열면서 사용 상태를 덮어쓰고 있음"
    print("  기존 양식 수정 — 후보 사용 + 없을 때 안내 OK")


def test_edit_source_dialog_always_offers_recollect():
    """'다시 읽어 합치기'는 원본이 있어도 **항상** 고를 수 있어야 한다.

    파서 규칙(예: OpticPreset target 선택)이 바뀌어도 저장된 원본 스냅샷에는
    반영되지 않는다. 항목 구성까지 최신으로 맞추려면 장비/로컬에서 다시 읽어
    합치는 길이 늘 열려 있어야 한다.
    """
    src = _src("equip_app.py")
    d = re.search(r"def _ask_edit_source.*?(?=\n    def )", src, re.S)
    assert d, "_ask_edit_source 를 찾지 못함"
    body = d.group(0)
    # 네 갈래: 저장된 원본 / 장비 다시 읽기 / 로컬 다시 읽기 / 확정본만
    assert ", cand, primary=True)" in body, "저장된 원본 선택지가 없음"
    assert '"EQUIP"' in body and '"LOCAL")' in body, "다시 읽기 선택지가 없음"
    assert '확정본만으로 열기' in body and '"")' in body, "확정본만 열기가 없음"
    assert "any_candidate_for" in body, "원본이 없을 때 다른 회차 빌려오기가 없음"

    # 다시 읽기 선택지는 **cand 조건문 밖**에서 만들어져야 한다(원본이 있어도 노출)
    cond = re.search(r"\n        if cand:\n(.*?)\n        elif other:\n(.*?)"
                     r"\n        opt\(", body, re.S)
    assert cond, "선택지 구성이 예상과 다름(if cand / elif other / 공통 opt)"
    assert '"EQUIP"' not in cond.group(1) and '"EQUIP"' not in cond.group(2), \
        "다시 읽기가 원본 유무 조건 안에 갇혀 있음"

    # 고른 소스가 그대로 재수집 함수로 전달된다
    r = re.search(r"def _recollect_for_edit.*?(?=\n    def )", src, re.S)
    assert r, "_recollect_for_edit 를 찾지 못함"
    rb = r.group(0)
    assert 'source="EQUIP"' in rb, "소스 인자가 없음"
    assert 'if source == "LOCAL":' in rb, "로컬 경로가 분리되지 않음"
    assert "_local_pick_sources" in rb and "_collect_dialog" in rb
    # 재수집 staging 은 **반드시 로컬**(OneDrive 동기화 폭주 방지)
    assert "localdirs.new_temp_run(self.local_dir" in rb, \
        "장비 수집 staging 이 로컬이 아님"

    # 호출측이 EQUIP/LOCAL 을 그대로 넘긴다
    e = re.search(r"def _edit_existing_form.*?(?=\n    def )", src, re.S)
    assert re.search(r"_recollect_for_edit\([^)]*source=choice", e.group(0), re.S), \
        "고른 소스를 넘기지 않음"
    print("  '다시 읽어 합치기' 항상 선택 가능 + 소스 전달 OK")


if __name__ == "__main__":
    for t in [test_candidate_lookup_prefers_original,
              test_version_status_flags_addable_versions,
              test_status_survives_recipe_without_versions,
              test_editor_always_saves_original,
              test_edit_existing_form_uses_candidates,
              test_edit_source_dialog_always_offers_recollect]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
