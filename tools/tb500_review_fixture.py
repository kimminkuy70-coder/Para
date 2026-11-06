"""TB500_Review.html 시험용 합성 자료(Para #40) — 실제 고객 데이터 아님.
OneDrive 캐시공유(Camtek BatchReport_캐시 zip + 캐시정보.json, KLA_캐시 zip + KLA캐시정보.json) 와
Conder Scan 폴더 트리를 만들어 JSON({경로: base64})으로 표준출력에 쓴다. 형식은 Para version_v12 의
desktop_batch._build_cache_zip · desktop_kla.cache_publish 와 같다."""
import base64, hashlib, io, json, sys, zipfile

def zbytes(files, big=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()

def report(job, setup, sm, day, start, n=25, fail=0):
    fname = f"{job}_{setup}_{sm}_{day}_({start.replace(':', '.')})_BatchReport.htm"
    yy, mon, d = day.split("-")
    hh = int(start[:2])
    ampm = "PM" if hh >= 12 else "AM"
    h12 = hh - 12 if hh > 12 else (12 if hh == 0 else hh)
    meta = [["Batch Start", f"{d}-{mon}-{yy} {h12:02d}:{start[3:]} {ampm}"], ["Job/Setup", f"{job}/{setup}"], ["Wafers Scanned", str(n)]]
    wafers = [{"Lot": sm, "Wafer ID": f"W{i:02d}", "Pass/Fail": "Scan 2D Error. Aborted." if i < fail else "Pass"} for i in range(n)]
    return fname, {"signature": [1, 1], "digest": "x" * 64, "report": {"file_name": fname, "metadata": meta, "wafers": wafers, "table_count": 2}}

def camtek_zip():
    m21 = dict([report("TB500_RDL1-Multi", "Setup1", "CMS-RDL1", "26-Oct-20", "09:10:00", fail=3),
                report("TB500_RDL3-Multi", "Setup1", "CMS", "26-Oct-18", "13:00:00"),
                report("TB500_RDL1-Multi", "Setup1", "WGB-RDL3", "26-Oct-22", "11:23:53")])
    m22 = dict([report("TB500_RDL1-Multi", "Setup1", "CMS RE", "26-Oct-21", "22:05:00", 2),
                report("TB500_PI4-Multi", "Setup1", "CMS", "26-Oct-15", "08:00:00")])
    files = {"누적/AOI-21_aaaaaaaa.json": json.dumps({"schema": 1, "machine": "AOI-21", "folder": "P:\\AOI-21\\Reports", "entries": m21}),
             "누적/AOI-22_bbbbbbbb.json": json.dumps({"schema": 1, "machine": "AOI-22", "folder": "P:\\AOI-22\\Reports", "entries": m22}),
             "manifest.json": json.dumps({"schema": 1, "cache_schema": 1, "machines": 2, "reports": 5})}
    return zbytes(files)

def kla_zip():
    idx = {"schema": 1, "updated_at": "2026-11-06 08:00:00", "sources": [
        {"machine": "AOI-K6", "path": "P:\\AOI-K6", "backup": False, "dates": {
            "2026-11-05": {"mtime": 1, "read_at": "2026-11-06 08:00:00", "lots": {
                "TB500.INT1041@6324_RAW": ["2026-11-05-10-02_2", "2026-11-05-10-00_1"],
                "TB500.INT948@6326_RAW": ["2026-11-05-11-00_1"]}}}},
        {"machine": "AOI-K2", "path": "P:\\AOI-K2", "backup": False, "dates": {
            "2026-11-04": {"mtime": 1, "read_at": "2026-11-06 08:00:00", "lots": {"TB500.INT1041@6314_RAW": ["2026-11-04-07-30_5"]}}}}]}
    return zbytes({"KLA색인.json": json.dumps(idx, ensure_ascii=False), "manifest.json": json.dumps({"schema": 1, "kind": "kla"})})

def info(name, data, extra=None):
    item = {"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "exported_at": "2026-11-06 09:00:00", "cache_schema": 1}
    item.update(extra or {})
    return json.dumps({"schema": 1, "items": [item]}, ensure_ascii=False).encode()

def main():
    out = {}
    cz, kz = camtek_zip(), kla_zip()
    out["share/BatchReport_캐시_20261106_090000.zip"] = cz
    out["share/캐시정보.json"] = info("BatchReport_캐시_20261106_090000.zip", cz)
    out["share/KLA_캐시_20261106_090100.zip"] = kz
    out["share/KLA캐시정보.json"] = info("KLA_캐시_20261106_090100.zip", kz)
    lot = "conder/976. TB500.INT1041 (CMS)/"
    layers = {"1-1. RDL4_재리뷰": ["m1.txt", "m2.txt", "x.jpg"], "1. RDL4": ["TB500_a.jpg"], "1. RDL4_재스캔 (#24,25)": ["a.txt"],
              "2. PIDS3": ["TB500_b.jpg"], "2. PIDS3_재리뷰": ["s/m1.txt"], "3-1. RDL3_재리뷰": ["m.txt"], "3. RDL3 (#23X)": ["TB500_c.jpg"],
              "3. RDL3_재스캔 All": ["q.txt"], "4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)": ["k.txt"],
              "5. RDL2": ["sub/ABC123_1_2_3_4.jpg"], "6. PIDS7_Skip (RDL2 재리뷰 결과 나오면 맵만 수정해 주세요)": ["k.txt"],
              "7. RDL1": ["TB500_RDL1 - Multi_x.jpg"], "메모": ["note.txt"]}
    for folder, files in layers.items():
        for f in files:
            out[lot + folder + "/" + f] = b"x"
    out["conder/977. TB500.INT10412 (ZZZ)/1. RDL4/TB500_z.jpg"] = b"x"
    out["local/다른파일.txt"] = b"keep"
    out["local/TB500리뷰_Camtek색인_20200101_000000.json"] = b"{}"
    json.dump({k: base64.b64encode(v).decode() for k, v in out.items()}, sys.stdout, ensure_ascii=False)

if __name__ == "__main__":
    main()
