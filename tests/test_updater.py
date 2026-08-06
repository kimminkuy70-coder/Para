"""updater.py 검증 — OneDrive 저장폴더만 쓰는 순수 A안 자동 업데이트(GUI 비의존).

Windows 전용 .bat 실제 실행은 이 환경(Linux)에서 검증 불가 — 스크립트 **내용**만
확인한다. 실기 실행 검증은 Windows 필요.
"""

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


def test_publish_and_read_manifest_roundtrip():
    with tempfile.TemporaryDirectory() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        exe = _fake_exe(os.path.join(build, "app.exe"))
        rel = U.publish(save_dir, exe, "3.1.0", changelog="감시 폴더 지정 추가",
                        user="홍길동")
        assert rel.version == "3.1.0"
        assert rel.size == os.path.getsize(exe)
        assert rel.sha256 == U.file_sha256(exe)
        got = U.read_manifest(save_dir)
        assert got is not None
        assert got.version == "3.1.0" and got.changelog == "감시 폴더 지정 추가"
        assert got.published_by == "홍길동"
        # 게시된 exe 가 실제로 저장폴더에 있어야 한다
        assert os.path.isfile(U.published_exe_path(save_dir, got))
    print("  게시(publish) → 매니페스트 왕복 OK")


def test_publish_overwrites_no_accumulation():
    """버전마다 파일이 쌓이면 안 된다 — 항상 exe 1개만 존재."""
    with tempfile.TemporaryDirectory() as save_dir, \
         tempfile.TemporaryDirectory() as build:
        exe1 = _fake_exe(os.path.join(build, "a.exe"), b"v1" * 500)
        exe2 = _fake_exe(os.path.join(build, "b.exe"), b"v2_bigger" * 500)
        U.publish(save_dir, exe1, "3.1.0")
        U.publish(save_dir, exe2, "3.2.0")
        prog = U.program_dir(save_dir)
        exes = [f for f in os.listdir(prog) if f.lower().endswith(".exe")]
        assert len(exes) == 1, f"exe 가 누적됨: {exes}"
        got = U.read_manifest(save_dir)
        assert got.version == "3.2.0"
        assert got.sha256 == U.file_sha256(exe2)
    print("  재게시 시 exe 누적 없음(고정 파일명 덮어쓰기) OK")


def test_read_manifest_missing_or_corrupt_is_none():
    with tempfile.TemporaryDirectory() as save_dir:
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
    with tempfile.TemporaryDirectory() as save_dir, \
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
    with tempfile.TemporaryDirectory() as save_dir, \
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
    with tempfile.TemporaryDirectory() as save_dir:
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


def test_swap_script_contains_required_steps():
    """실제 실행은 Windows 필요 — 생성된 스크립트에 필수 단계가 있는지만 확인."""
    with tempfile.TemporaryDirectory() as local:
        script = U.build_swap_script(local, pid=12345,
                                     current_exe=r"C:\Apps\Para\PI_Param_Manager.exe",
                                     new_exe=r"C:\Users\a\AppData\Local\CamtekAOI\Temp\x\PI_Param_Manager.exe",
                                     backup_path=r"C:\Users\a\AppData\Local\CamtekAOI\PI_Param_Manager_이전버전.exe")
        assert os.path.isfile(script)
        body = open(script, encoding="utf-8").read()
        assert "12345" in body, "PID 대기 로직에 PID 가 들어가야 함"
        assert "tasklist" in body.lower(), "프로세스 종료 대기 로직 필요"
        assert "PI_Param_Manager_이전버전.exe" in body, "백업 경로 필요"
        assert body.count("copy") >= 2, "백업 복사 + 교체 복사 둘 다 있어야 함"
        assert "start" in body.lower(), "재실행 명령 필요"
        assert "del" in body.lower(), "자기 삭제(정리) 필요"
    print("  교체 스크립트 필수 단계(대기·백업·교체·재실행·자기삭제) 포함 OK")


def test_is_frozen_false_in_dev():
    assert U.is_frozen() is False, "테스트는 소스 실행이라 항상 False"
    print("  소스 실행 시 is_frozen()=False OK")


if __name__ == "__main__":
    for t in [test_parse_version_variants, test_is_newer_handles_uneven_length,
              test_publish_and_read_manifest_roundtrip,
              test_publish_overwrites_no_accumulation,
              test_read_manifest_missing_or_corrupt_is_none,
              test_verify_download_detects_incomplete_sync,
              test_download_to_local_goes_to_local_not_onedrive,
              test_publish_rejects_bad_inputs,
              test_swap_script_contains_required_steps,
              test_is_frozen_false_in_dev]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
