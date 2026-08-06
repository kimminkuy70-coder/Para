"""updater.py 검증 — OneDrive 저장폴더만 쓰는 순수 A안 자동 업데이트(GUI 비의존).

Windows 전용 .bat 실제 실행은 이 환경(Linux)에서 검증 불가 — 스크립트 **내용**만
확인한다. 실기 실행 검증은 Windows 필요.
"""

import contextlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import localdirs, updater as U  # noqa: E402

PASS = FAIL = 0


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


def _fake_exe(path, content=b"FAKE_EXE_BYTES_" * 100):
    with open(path, "wb") as fh:
        fh.write(content)
    return path


@contextlib.contextmanager
def _save_tree(name="docs"):
    """저장폴더를 **하위 폴더로** 만든다 — 실제 배치(`…\\docs`)와 같게.

    게시 폴더(`프로그램/`)는 저장폴더 옆(형제)에 생기므로, 저장폴더가 임시폴더
    최상단이면 게시본이 임시폴더 **밖**으로 나가 테스트끼리 섞인다.
    """
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, name)
        os.makedirs(d)
        yield d


# --------------------------------------------------------------------------
def test_parse_version_variants():
    assert U.parse_version("3.1.0") == (3, 1, 0)
    assert U.parse_version("v3.1.0") == (3, 1, 0)
    assert U.parse_version("3.1.0-beta") == (3, 1, 0)
    assert U.parse_version("3.1") == (3, 1)
    assert U.parse_version("") == (0,)
    assert U.parse_version("버전없음") == (0,)
    print("  버전 문자열 파싱(접두/접미/빈값) OK")


def test_is_newer_handles_uneven_length():
    assert U.is_newer("3.1.0", "3.0.9") is True
    assert U.is_newer("3.10.0", "3.9.0") is True, "문자열 비교면 틀림(사전식 함정)"
    assert U.is_newer("3.1", "3.1.0") is False, "3.1 == 3.1.0 로 취급"
    assert U.is_newer("3.1.0", "3.1") is False
    assert U.is_newer("3.0.0", "3.1.0") is False
    assert U.is_newer("3.0.0", "3.0.0") is False
    print("  버전 비교(길이 다름·숫자 크기·동일버전) OK")


def test_exe_filename_includes_version():
    """파일명에 버전이 들어간다(사용자 지정). 'v' 중복·금지문자는 정리."""
    assert U.exe_filename("3.1.0") == "Camtek_AOI_Parameter_manage_v3.1.0.exe"
    assert U.exe_filename("1.0") == "Camtek_AOI_Parameter_manage_v1.0.exe"
    # 사용자가 'v' 를 붙여 입력해도 '_vv' 가 되면 안 된다
    assert U.exe_filename("v3.1.0") == "Camtek_AOI_Parameter_manage_v3.1.0.exe"
    assert U.exe_filename("V2.5") == "Camtek_AOI_Parameter_manage_v2.5.exe"
    # 파일명에 못 쓰는 문자 제거
    assert "/" not in U.exe_filename("3/1")
    assert " " not in U.exe_filename("3.1.0 beta")
    print("  버전 포함 파일명 생성(v중복·금지문자 처리) OK")


def test_publish_and_read_manifest_roundtrip():
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        exe = _fake_exe(os.path.join(build, "app.exe"))
        rel = U.publish(save_dir, exe, "3.1.0", changelog="감시 폴더 지정 추가",
                        user="홍길동")
        assert rel.version == "3.1.0"
        assert rel.filename == "Camtek_AOI_Parameter_manage_v3.1.0.exe", rel.filename
        assert rel.size == os.path.getsize(exe)
        assert rel.sha256 == U.file_sha256(exe)
        got = U.read_manifest(save_dir)
        assert got is not None
        assert got.version == "3.1.0" and got.changelog == "감시 폴더 지정 추가"
        assert got.published_by == "홍길동"
        assert got.filename == rel.filename
        # 게시된 exe 가 실제로 저장폴더에 있어야 한다
        assert os.path.isfile(U.published_exe_path(save_dir, got))
    print("  게시(publish) → 매니페스트 왕복(버전 파일명 포함) OK")


def test_publish_keeps_two_versions_for_rollback():
    """항상 **신버전 + 직전 구버전 2개**를 남긴다 — 새 버전이 잘못되면 되돌려야 한다.
    그보다 오래된 것은 지워 무한정 쌓이지 않게 한다."""
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        for i, v in enumerate(["3.1.0", "3.2.0", "3.3.0", "3.4.0"]):
            exe = _fake_exe(os.path.join(build, f"a{i}.exe"), b"v" * (500 + i))
            U.publish(save_dir, exe, v)
        exes = U.list_published_exes(save_dir)
        assert len(exes) == U.KEEP_VERSIONS == 2, exes
        assert sorted(exes) == ["Camtek_AOI_Parameter_manage_v3.3.0.exe",
                                "Camtek_AOI_Parameter_manage_v3.4.0.exe"], exes
        got = U.read_manifest(save_dir)
        assert got.version == "3.4.0"
        assert os.path.isfile(U.published_exe_path(save_dir, got))
        # 롤백 후보(직전 버전)가 실제로 남아 있어야 한다
        rollback = [n for n in exes if n != got.filename]
        assert rollback == ["Camtek_AOI_Parameter_manage_v3.3.0.exe"], rollback
        assert os.path.isfile(os.path.join(U.program_dir(save_dir), rollback[0]))
    print("  게시 후 2개 유지(신버전 + 롤백용 직전 버전) OK")


def test_prune_ranks_by_version_not_filetime():
    """어느 것이 '직전 버전'인지는 **버전 번호**로 판단해야 한다.
    OneDrive 동기화로 파일 시각은 뒤바뀔 수 있어 신뢰할 수 없고, 문자열 비교면
    3.10.0 < 3.2.0 으로 잘못 판단한다."""
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        # 일부러 뒤죽박죽 순서로 게시
        for i, v in enumerate(["3.2.0", "3.10.0", "3.9.0"]):
            U.publish(save_dir, _fake_exe(os.path.join(build, f"a{i}.exe"),
                                          b"v" * (300 + i)), v)
        # 마지막 게시는 3.9.0 → 그것 + 남은 것 중 최신 버전(3.10.0)이 남아야 한다
        exes = sorted(U.list_published_exes(save_dir))
        assert exes == ["Camtek_AOI_Parameter_manage_v3.10.0.exe",
                        "Camtek_AOI_Parameter_manage_v3.9.0.exe"], exes
        assert U.version_of_filename("Camtek_AOI_Parameter_manage_v3.10.0.exe") \
            > U.version_of_filename("Camtek_AOI_Parameter_manage_v3.2.0.exe")
    print("  정리 우선순위 = 버전 번호(3.10 > 3.2) OK")


def test_prune_keeps_unrelated_files():
    """`프로그램/` 폴더의 남의 파일까지 지우면 안 된다."""
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        prog = U.program_dir(save_dir)
        other = os.path.join(prog, "사용설명서.pdf")
        with open(other, "w", encoding="utf-8") as fh:
            fh.write("x")
        stray = os.path.join(prog, "다른프로그램.exe")     # 우리 게시물이 아님
        with open(stray, "w", encoding="utf-8") as fh:
            fh.write("x")
        U.publish(save_dir, _fake_exe(os.path.join(build, "a.exe")), "3.1.0")
        assert os.path.isfile(other), "관련 없는 파일을 지우면 안 됨"
        assert os.path.isfile(stray), "우리 게시물이 아닌 exe 를 지우면 안 됨"
    print("  정리 대상은 우리 게시 exe 만 OK")


def test_legacy_manifest_without_filename():
    """구 버전(고정 파일명 시절) 매니페스트도 계속 읽혀야 한다."""
    import json
    with _save_tree() as save_dir:
        os.makedirs(U.program_dir(save_dir), exist_ok=True)
        with open(U.manifest_path(save_dir), "w", encoding="utf-8") as fh:
            json.dump({"version": "3.0.0", "sha256": "ab" * 32, "size": 123}, fh)
        got = U.read_manifest(save_dir)
        assert got is not None
        assert got.filename == U.LEGACY_EXE_NAME, got.filename
    print("  구 매니페스트(파일명 없음) 하위호환 OK")


def test_read_manifest_missing_or_corrupt_is_none():
    with _save_tree() as save_dir:
        assert U.read_manifest(save_dir) is None          # 아예 없음
        os.makedirs(U.program_dir(save_dir), exist_ok=True)
        with open(U.manifest_path(save_dir), "w", encoding="utf-8") as fh:
            fh.write("{깨진 JSON")
        assert U.read_manifest(save_dir) is None           # 깨짐
        with open(U.manifest_path(save_dir), "w", encoding="utf-8") as fh:
            fh.write('{"version": ""}')                    # 필수값 없음
        assert U.read_manifest(save_dir) is None
    print("  매니페스트 없음/깨짐/불완전 → 예외 없이 None OK")


def test_verify_download_detects_incomplete_sync():
    """OneDrive 동기화가 덜 끝난(잘린) 파일을 그대로 쓰면 안 된다."""
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build, \
         tempfile.TemporaryDirectory() as local:
        exe = _fake_exe(os.path.join(build, "app.exe"))
        release = U.publish(save_dir, exe, "3.1.0")
        good = U.download_to_local(save_dir, release, local)
        ok, reason = U.verify_download(good, release)
        assert ok is True, reason

        truncated = os.path.join(local, "broken.exe")
        with open(good, "rb") as fh:
            data = fh.read()
        with open(truncated, "wb") as fh:
            fh.write(data[: len(data) // 2])          # 절반만 = 동기화 중 상태 흉내
        ok2, reason2 = U.verify_download(truncated, release)
        assert ok2 is False and "크기" in reason2, reason2

        corrupted = os.path.join(local, "corrupted.exe")
        with open(corrupted, "wb") as fh:
            fh.write(data[:-1] + b"\x00")              # 크기는 같은데 내용만 다름
        ok3, reason3 = U.verify_download(corrupted, release)
        assert ok3 is False and "일치하지" in reason3, reason3
    print("  다운로드 검증: 잘림/손상 모두 거부 OK")


def test_download_to_local_goes_to_local_not_onedrive():
    with _save_tree() as save_dir, \
         tempfile.TemporaryDirectory() as build, \
         tempfile.TemporaryDirectory() as local:
        exe = _fake_exe(os.path.join(build, "app.exe"))
        release = U.publish(save_dir, exe, "3.1.0")
        got = U.download_to_local(save_dir, release, local)
        assert got.startswith(os.path.join(local, localdirs.TEMP)), got
        assert not got.startswith(save_dir), "저장폴더(OneDrive)에 쓰면 안 됨"
        ok, _ = U.verify_download(got, release)
        assert ok is True
    print("  받은 exe 는 로컬 Temp 에만(OneDrive 아님) OK")


def test_publish_rejects_bad_inputs():
    with _save_tree() as save_dir:
        try:
            U.publish(save_dir, "/없는/경로/x.exe", "3.1.0")
            assert False, "없는 파일인데 예외가 안 남"
        except FileNotFoundError:
            pass
        with tempfile.TemporaryDirectory() as build:
            exe = _fake_exe(os.path.join(build, "a.exe"))
            try:
                U.publish(save_dir, exe, "버전아님")
                assert False, "숫자 없는 버전인데 예외가 안 남"
            except ValueError:
                pass
    print("  게시 입력 검증(없는 파일/잘못된 버전) OK")


def _script_body(path):
    """생성된 .bat 은 cmd.exe 가 읽는 시스템 ANSI(한국어=cp949)로 기록된다."""
    raw = open(path, "rb").read()
    return raw.decode("cp949")


def _commands(body):
    """주석(rem)을 뺀 실제 명령 줄만."""
    return [l.strip() for l in body.splitlines()
            if l.strip() and not l.strip().lower().startswith("rem")]


def test_swap_script_contains_required_steps():
    """실제 실행은 Windows 필요 — 생성된 스크립트에 필수 단계가 있는지만 확인."""
    with tempfile.TemporaryDirectory() as local:
        script = U.build_swap_script(
            local, pid=12345,
            current_exe=r"C:\Apps\Para\Camtek_AOI_Parameter_manage_v3.0.0.exe",
            new_exe=r"C:\Users\a\AppData\Local\CamtekAOI\Temp\update_x\Camtek_AOI_Parameter_manage_v3.1.0.exe",
            backup_path=r"C:\Users\a\AppData\Local\CamtekAOI\Camtek_AOI_Parameter_manage_v3.0.0_prev.exe",
            target_exe=r"C:\Apps\Para\Camtek_AOI_Parameter_manage_v3.1.0.exe")
        assert os.path.isfile(script)
        body = _script_body(script)
        cmds = "\n".join(_commands(body))
        assert "_prev.exe" in cmds, "롤백 백업 경로 필요"
        assert cmds.count("copy") >= 2, "백업 복사 + 교체 복사 둘 다 있어야 함"
        assert "start" in cmds.lower(), "재실행 명령 필요"
        assert "del" in cmds.lower(), "자기 삭제(정리) 필요"
        assert "v3.1.0" in cmds, "새 버전 파일명으로 교체해야 함"
    print("  교체 스크립트 필수 단계(백업·교체·재실행·자기삭제) 포함 OK")


def test_swap_script_avoids_console_and_locale_traps():
    """detached 실행·한글 Windows 에서 실제로 깨졌던 함정 3가지를 막았는지.

      · `timeout` 은 콘솔이 없으면 즉시 실패한다 → `ping` 을 써야 한다.
      · `tasklist | find "<PID>"` 는 메모리 열 숫자와 우연히 일치해 영원히 대기할
        수 있다 → 복사 재시도로 종료를 판정해야 한다.
      · 교체가 끝내 실패하면 기존 exe 를 되살려야 한다(사용자가 빈손이 되지 않게).
    """
    import re
    with tempfile.TemporaryDirectory() as local:
        script = U.build_swap_script(
            local, pid=12345, current_exe=r"C:\A\a_v3.0.0.exe",
            new_exe=os.path.join(local, "n.exe"),
            backup_path=os.path.join(local, "b_prev.exe"),
            target_exe=r"C:\A\a_v3.1.0.exe")
        cmds = _commands(_script_body(script))
        assert not [c for c in cmds if re.match(r"^timeout\b", c, re.I)], \
            "timeout 은 detached 에서 실패한다"
        assert any(re.match(r"^ping\b", c, re.I) for c in cmds), "ping 대기 필요"
        assert not [c for c in cmds if "tasklist" in c.lower()], \
            "PID 문자열 매칭은 오탐 위험"
        joined = "\n".join(cmds)
        assert "goto copyloop" in joined, "복사 재시도(=종료 판정) 필요"
        assert 'if exist "%OLD%" start "" "%OLD%"' in joined, \
            "실패 시 기존 exe 복구 필요"
    print("  detached/로케일 함정 회피(ping·복사재시도·실패복구) OK")


def test_swap_script_is_cp949_and_keeps_korean_paths():
    """cmd.exe 는 .bat 을 UTF-8 이 아니라 시스템 ANSI 로 읽는다. UTF-8 로 쓰면
    한글 경로가 깨져 엉뚱한 파일을 건드린다(되돌릴 수 없는 파일 조작이라 치명적)."""
    with tempfile.TemporaryDirectory() as local:
        cur = r"C:\Users\홍길동\바탕 화면\Camtek_AOI_Parameter_manage_v3.0.0.exe"
        script = U.build_swap_script(
            local, pid=1, current_exe=cur,
            new_exe=os.path.join(local, "n.exe"),
            backup_path=os.path.join(local, "b_prev.exe"),
            target_exe=r"C:\Users\홍길동\바탕 화면\Camtek_AOI_Parameter_manage_v3.1.0.exe")
        raw = open(script, "rb").read()
        body = raw.decode("cp949")            # cp949 로 읽혀야 정상
        assert "홍길동" in body and "바탕 화면" in body, "한글 경로가 보존돼야 함"
        # 우리가 넣는 문구는 전부 ASCII — 한 글자라도 cp949 밖이면 파일 전체가
        # UTF-8 로 물러나 위 보장이 깨진다(실제로 em-dash 때문에 깨졌었다).
        for line in _commands(body):
            if not line.startswith("set "):   # set 줄에는 사용자 경로가 들어감
                assert line.isascii(), f"명령 줄에 비ASCII: {line!r}"
    print("  bat 인코딩 cp949 + 한글 경로 보존 + 문구 ASCII OK")


def test_local_target_uses_new_version_name():
    """업데이트하면 로컬 exe 이름도 새 버전으로 바뀐다(같은 폴더)."""
    rel = U.ReleaseInfo("3.1.0", U.exe_filename("3.1.0"), "ab" * 32, 10)
    cur = os.path.join("folder", "Camtek_AOI_Parameter_manage_v3.0.0.exe")
    target = U.local_target_path(cur, rel)
    assert os.path.dirname(target) == os.path.dirname(os.path.abspath(cur))
    assert os.path.basename(target) == "Camtek_AOI_Parameter_manage_v3.1.0.exe"
    print("  업데이트 후 로컬 파일명도 새 버전 OK")


def test_backup_name_is_ascii():
    """백업 경로는 배치스크립트에 들어가므로 ASCII 여야 안전하다."""
    with tempfile.TemporaryDirectory() as local:
        p = U.backup_path_for(local, os.path.join("x",
                                                  "Camtek_AOI_Parameter_manage_v3.0.0.exe"))
        assert os.path.basename(p).isascii(), p
        assert os.path.basename(p).endswith("_prev.exe"), p
    print("  롤백 백업 파일명 ASCII OK")


def test_is_frozen_false_in_dev():
    assert U.is_frozen() is False, "테스트는 소스 실행이라 항상 False"
    print("  소스 실행 시 is_frozen()=False OK")


def test_program_dir_is_sibling_of_save_dir():
    """게시 폴더는 저장폴더 **옆**(형제). 저장폴더를 `…\\docs` 로 지정해도
    배포 exe 가 문서 폴더 안에 묻히면 안 된다(2026-08 사용자 지정)."""
    with tempfile.TemporaryDirectory() as root, \
         tempfile.TemporaryDirectory() as build:
        save_dir = os.path.join(root, "docs")
        os.makedirs(save_dir)
        assert U.resolve_program_dir(save_dir) == \
            os.path.join(root, U.PROGRAM_DIRNAME)
        rel = U.publish(save_dir, _fake_exe(os.path.join(build, "a.exe")), "3.1.0")
        # 실제 게시물도 docs 안이 아니라 docs 옆에 있어야 한다
        assert os.path.isfile(os.path.join(root, U.PROGRAM_DIRNAME, rel.filename))
        assert not os.path.exists(os.path.join(save_dir, U.PROGRAM_DIRNAME)), \
            "저장폴더(docs) 안에는 만들지 않는다"
        assert U.read_manifest(save_dir).version == "3.1.0"
        assert U.list_published_exes(save_dir) == [rel.filename]
    print("  게시 폴더 = 저장폴더의 형제(docs 옆) OK")


def test_old_inside_publish_still_readable_then_migrated():
    """구 위치(저장폴더 안)에 게시된 버전은 **계속 읽히고**, 다시 게시하면
    정식 위치(형제)로 옮겨져 배포물이 두 곳에 나뉘지 않아야 한다."""
    import json
    with tempfile.TemporaryDirectory() as root, \
         tempfile.TemporaryDirectory() as build:
        save_dir = os.path.join(root, "docs")
        inside = os.path.join(save_dir, U.PROGRAM_DIRNAME)
        os.makedirs(inside)
        old_exe = os.path.join(inside, U.exe_filename("3.0.0"))
        _fake_exe(old_exe, b"old" * 50)
        with open(os.path.join(inside, U.MANIFEST_NAME), "w", encoding="utf-8") as fh:
            json.dump({"version": "3.0.0", "filename": os.path.basename(old_exe),
                       "sha256": U.file_sha256(old_exe),
                       "size": os.path.getsize(old_exe)}, fh)
        # ① 아직 새 위치에 게시본이 없으므로 구 위치를 읽는다
        assert U.active_program_dir(save_dir) == inside
        got = U.read_manifest(save_dir)
        assert got.version == "3.0.0" and os.path.isfile(
            U.published_exe_path(save_dir, got))

        # ② 새로 게시하면 구버전까지 형제 폴더로 옮겨진다
        U.publish(save_dir, _fake_exe(os.path.join(build, "a.exe")), "3.1.0")
        canon = os.path.join(root, U.PROGRAM_DIRNAME)
        assert U.active_program_dir(save_dir) == canon
        assert sorted(U.list_published_exes(save_dir)) == [
            U.exe_filename("3.0.0"), U.exe_filename("3.1.0")], \
            "롤백용 구버전도 새 폴더로 따라와야 한다"
        assert not os.path.exists(inside), "구 폴더는 비워져 사라진다"
    print("  구 위치 게시본 읽기 → 재게시 시 형제 폴더로 이동 OK")


def test_program_dir_falls_back_when_no_parent():
    """부모 폴더를 쓸 수 없으면(루트 등) 예전처럼 저장폴더 안에 만든다."""
    root = os.path.abspath(os.sep)
    assert U.resolve_program_dir(root) == os.path.join(root, U.PROGRAM_DIRNAME)
    with tempfile.TemporaryDirectory() as tmp:
        missing = os.path.join(tmp, "없는폴더", "저장")
        assert U.resolve_program_dir(missing) == \
            os.path.join(missing, U.PROGRAM_DIRNAME)
    print("  부모 폴더 없음 → 저장폴더 안으로 폴백 OK")


if __name__ == "__main__":
    for t in [test_parse_version_variants, test_is_newer_handles_uneven_length,
              test_exe_filename_includes_version,
              test_publish_and_read_manifest_roundtrip,
              test_publish_keeps_two_versions_for_rollback,
              test_prune_ranks_by_version_not_filetime,
              test_prune_keeps_unrelated_files,
              test_legacy_manifest_without_filename,
              test_read_manifest_missing_or_corrupt_is_none,
              test_verify_download_detects_incomplete_sync,
              test_download_to_local_goes_to_local_not_onedrive,
              test_publish_rejects_bad_inputs,
              test_swap_script_contains_required_steps,
              test_swap_script_avoids_console_and_locale_traps,
              test_swap_script_is_cp949_and_keeps_korean_paths,
              test_local_target_uses_new_version_name,
              test_backup_name_is_ascii,
              test_is_frozen_false_in_dev,
              test_program_dir_is_sibling_of_save_dir,
              test_old_inside_publish_still_readable_then_migrated,
              test_program_dir_falls_back_when_no_parent]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
