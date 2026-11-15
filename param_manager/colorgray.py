"""Color · Gray 매칭 — AOI Color 이미지마다 같은 위치의 Gray 스캔 프레임을 찾아 잘라 붙인다.

Port of the stand-alone "AOI Color-Gray Matcher Final v16" (pywebview + Pillow) into
Para. The matching maths is unchanged; what differs is *where the pixels are
handled*: Para may not add packages (openpyxl only), so decoding, cropping,
thumbnails and JPEG encoding run in the app's own WebView (canvas), and this
module does everything else:

* find wafer folders under a Lot/Wafer folder (`discover`),
* parse `ColorImageGrabingInfo.ini`, `ScanResultImageList.txt` and
  `frameToChuckPlane.ini`, pick the gray frame that contains each color fault
  (`plan_wafer` / `choose_frame`) and the crop size (`crop_size`),
* write the comparison workbook with the thumbnails the UI produced
  (`build_workbook` — JPEG bytes embedded without Pillow via `JpegImage`).

The source folders are only read. Results go to a separate output folder.
"""
from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

RESULT_FOLDER = "AOI_Color_Gray_Matching_Result"
MAX_WAFERS = 25
TW, TH = 360, 270                      # Excel thumbnail canvas
GW, GH, GP = 3168, 1024, 0.769644115336745   # gray frame size (px) and gray pixel size (µm)
CROPS, THUMBS = "_crop_images", "_excel_thumbnails"
SKIP = {RESULT_FOLDER.lower(), CROPS, THUMBS, "_metadata", "$recycle.bin", "system volume information"}


# ---------------------------------------------------------------- discovery
WAFER_FILES = ("ColorImageGrabingInfo.ini", "ScanResultImageList.txt")
TRANSFORM_NAME = "frameToChuckPlane.ini"
# 실제 장비 폴더의 이름은 frameToChuckPlane.ini (Para #49). 예전 판의 frameToChuckPlane.<번호>.ini 도 받는다.
TRANSFORM_RE = re.compile(r"^frametochuckplane(\..+)?\.ini$", re.I)
LONG_PATH = 240                 # Windows MAX_PATH(260) 가까이면 \\?\ 확장 경로로 연다


def long_path(p) -> str:
    """Path string usable for long Windows paths (Para #48).

    네트워크 드라이브 · UNC 의 깊은 Scanresult 경로는 260자를 넘기 쉽다. 그러면
    Windows 가 stat/open 을 '경로 없음'으로 거절해 파일이 있어도 없다고 판단했다.
    길면 확장 경로(드라이브 · UNC 형식)로 바꾼다(Windows 만, 짧으면 그대로)."""
    s = str(p)
    if os.name != "nt" or len(s) < LONG_PATH or s.startswith("\\\\?\\"):
        return s
    s = os.path.abspath(s)
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s


def file_names(p) -> dict:
    """{소문자 이름: 실제 이름} of the files directly in p (one directory listing).

    파일마다 전체 경로로 묻지 않고 폴더 목록 1번으로 본다 — 긴 경로 · 대소문자가 다른
    이름(NAS) · 네트워크 드라이브에서도 같은 결과(Para #48)."""
    try:
        with os.scandir(long_path(p)) as entries:
            names = {}
            for e in entries:
                try:
                    if e.is_file():
                        names[e.name.lower()] = e.name
                except OSError:
                    continue
            return names
    except OSError:
        return {}


def transform_files(p: Path, names: dict | None = None) -> dict:
    """{레시피 번호 또는 None: 변환 파일} (Para #49).

    `frameToChuckPlane.ini` = 모든 레시피 공통(None), `frameToChuckPlane.<번호>.ini` = 그 레시피."""
    names = file_names(p) if names is None else names
    out = {}
    for low, real in sorted(names.items()):
        if not TRANSFORM_RE.match(low):
            continue
        mid = low[len("frametochuckplane"):-len(".ini")].strip(".")
        out[int(mid) if mid.isdigit() else (None if not mid else mid)] = Path(p) / real
    return out


def transform_for(files: dict, recipe):
    """그 레시피의 변환 파일: 번호가 맞는 것 → 공통(.ini) → 첫 번째."""
    if recipe in files:
        return files[recipe]
    if None in files:
        return files[None]
    return files[sorted(files, key=str)[0]] if files else None


def transform_file(p: Path, names: dict | None = None):
    names = file_names(p) if names is None else names
    exact = names.get(TRANSFORM_NAME.lower())
    if exact:                       # frameToChuckPlane.ini 가 있으면 그것을 쓴다(Para #49)
        return Path(p) / exact
    hits = sorted(real for low, real in names.items() if TRANSFORM_RE.match(low))
    return Path(p) / hits[0] if hits else None


def wafer_file(p: Path, name: str, names: dict | None = None) -> Path:
    """The real file for one of the fixed names (case as on disk)."""
    names = file_names(p) if names is None else names
    return Path(p) / names.get(name.lower(), name)


def missing_files(p: Path, names: dict | None = None) -> list:
    """Which of the three wafer files are not directly in p (화면 안내용)."""
    names = file_names(p) if names is None else names
    out = [n for n in WAFER_FILES if n.lower() not in names]
    if transform_file(p, names) is None:
        out.append(TRANSFORM_NAME)
    return out


def is_wafer(p: Path) -> bool:
    return not missing_files(Path(p))


def child_dirs(p: Path):
    try:
        with os.scandir(long_path(p)) as entries:
            out = []
            for e in entries:
                try:
                    # follow_symlinks 기본(True): 네트워크 드라이브(DFS · NAS)의 폴더는
                    # reparse point 로 보여 follow_symlinks=False 면 빠졌다(Para #48).
                    # 고리는 discover 의 seen · max_depth 가 막는다.
                    if e.is_dir():
                        out.append(Path(p) / e.name)
                except OSError:
                    continue
            return sorted(out, key=lambda x: x.name.lower())
    except OSError:
        return []


def discover(root, callback=None, cancel=None, max_depth=5):
    """Breadth-first search for wafer folders (a Lot folder or one wafer folder)."""
    root = Path(root)
    if is_wafer(root):
        callback and callback("found", root, 1, 1, 0)
        return [root]
    queue, seen, found, scanned = [(root, 0)], set(), [], 0
    while queue and len(found) < MAX_WAFERS:
        if cancel is not None and cancel.is_set():
            break
        current, depth = queue.pop(0)
        key = str(current).lower()
        if key in seen:
            continue
        seen.add(key)
        scanned += 1
        callback and callback("scanning", current, scanned, len(found), len(queue))
        if depth >= max_depth:
            continue
        for child in child_dirs(current):
            if child.name.lower() in SKIP:
                continue
            if is_wafer(child):
                found.append(child)
                callback and callback("found", child, scanned, len(found), len(queue))
            else:
                queue.append((child, depth + 1))
    callback and callback("complete", root, scanned, len(found), len(queue))
    return found


# ---------------------------------------------------------------- parsing
def _text(path: Path) -> str:
    with open(long_path(path), encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def parse_colors(path):
    rows, current = [], None
    for raw in _text(path).splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            if current:
                rows.append(current)
            current = {"file": line[1:-1]}
        elif current is not None and "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()
    if current:
        rows.append(current)
    return rows


def parse_frames(path):
    rows = []
    for raw in _text(path).splitlines():
        parts = [x.strip() for x in re.split(r"[,;\t]", raw.strip())]
        if len(parts) < 3 or parts[0].startswith("Version="):
            continue
        try:
            match = re.search(r"\.t\.(\d+)\.jpe?g$", parts[0], re.I)
            rows.append({"file": parts[0], "x": float(parts[1]), "y": float(parts[2]),
                         "recipe": int(match.group(1)) if match else None})
        except ValueError:
            pass
    return rows


def parse_transform(path):
    data = {}
    for raw in _text(path).splitlines():
        line = raw.split(";", 1)[0].strip() if not raw.lstrip().startswith("[") else ""
        if "=" in line:
            key, value = line.split("=", 1)
            try:
                nums = [float(x) for x in re.split(r"[\s,]+", value.strip()) if x]
            except ValueError:
                continue
            # 키 이름 대소문자 · '_' 무시(Scan_X · SCAN_X · ScanX, Para #49)
            data.setdefault(re.sub(r"[^a-z0-9]", "", key.lower()), nums)
    sx, sy = data.get("scanx"), data.get("scany")
    if not sx or not sy or len(sx) < 3 or len(sy) < 3:
        raise ValueError(f"{Path(path).name} 에 Scan_X · Scan_Y(숫자 3개) 줄이 없습니다")
    m = ((sx[0], sx[1]), (sy[0], sy[1]))
    offset = (sx[2], sy[2])
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if det == 0:
        raise ValueError("frameToChuckPlane 변환 행렬을 풀 수 없습니다")
    inverse = ((m[1][1] / det, -m[0][1] / det), (-m[1][0] / det, m[0][0] / det))
    return inverse, offset


def fault_xy(color):
    return float(color.get("FaultX", color.get("X"))), float(color.get("FaultY", color.get("Y")))


# Fault 좌표 해석(Para #49 후속). 소유자 설명: wafer map 을 꽉 채우는 가상의 직사각형을 그리면
# 그 좌측 하단이 (0,0) 이다. Gray 프레임 위치(ScanResultImageList)는 장비 chuck 좌표일 수 있어,
# 그대로 맞지 않으면 프레임들이 덮는 직사각형(= wafer map 직사각형)의 좌측 하단을 원점으로 옮겨 본다.
COORD_MODES = ("그대로", "좌측 하단 원점", "좌측 하단 원점 · Y 반전", "Y 반전")


def _forward(inverse):
    (a, b), (c, d) = inverse
    det = a * d - b * c
    return ((d / det, -b / det), (-c / det, a / det))


def frames_rect(frames, transform_of):
    """프레임들이 덮는 직사각형 (x0, y0, x1, y1) — chuck 좌표. transform_of(recipe) → (inverse, offset)."""
    xs, ys = [], []
    for f in frames:
        try:
            inverse, offset = transform_of(f["recipe"] if f["recipe"] is not None else 1)
            m = _forward(inverse)
        except (ValueError, ZeroDivisionError, OSError):
            continue
        for px, py in ((0, 0), (GW, 0), (0, GH), (GW, GH)):
            xs.append(f["x"] + offset[0] + m[0][0] * px + m[0][1] * py)
            ys.append(f["y"] + offset[1] + m[1][0] * px + m[1][1] * py)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def map_xy(mode, fx, fy, rect):
    if mode == 0 or rect is None:
        return fx, fy
    x0, y0, x1, y1 = rect
    if mode == 1:
        return x0 + fx, y0 + fy
    if mode == 2:
        return x0 + fx, y1 - fy
    return fx, y0 + y1 - fy


def choose_frame(color, frames, inverse, offset, xy=None):
    """Gray frame whose image contains the fault, preferring the one where it lies
    farthest from the frame edge. Returns (frame, px, py, candidate_count)."""
    fx, fy = xy if xy is not None else fault_xy(color)
    recipe = int(float(color.get("RecipeNumber", "1") or 1))
    # 프레임 이름에 레시피 번호(.t.<번호>.jpg)가 없거나 그 번호의 프레임이 없으면 모든 프레임에서 찾는다(Para #49)
    same = [f for f in frames if f["recipe"] == recipe]
    pool = same if same else [f for f in frames if f["recipe"] is None] or frames
    candidates = []
    for frame in pool:
        tx, ty = fx - frame["x"] - offset[0], fy - frame["y"] - offset[1]
        px = inverse[0][0] * tx + inverse[0][1] * ty
        py = inverse[1][0] * tx + inverse[1][1] * ty
        if 0 <= px < GW and 0 <= py < GH:
            candidates.append((min(px, GW - px, py, GH - py), frame, px, py))
    if not candidates:
        return None, None, None, 0
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, frame, px, py = candidates[0]
    return frame, px, py, len(candidates)


def crop_size(color):
    """(crop_w, crop_h, out_w, out_h): gray pixels covering the color image's field of
    view, and the color image size the crop is resized to."""
    out_w = int(float(color.get("ImageSizeX", 1380)))
    out_h = int(float(color.get("ImageSizeY", 1036)))
    crop_w = max(1, round(out_w * float(color.get("PixelSizeX", 0.4674)) / GP))
    crop_h = max(1, round(out_h * float(color.get("PixelSizeY", 0.4674)) / GP))
    return crop_w, crop_h, out_w, out_h


def _inside(wafer: Path, name: str, names: dict | None = None):
    """A file named inside the wafer's list files; never outside the wafer folder.

    목록에 장비의 전체 경로(`D:\\...\\x.t.1.jpg`)나 다른 대소문자가 적혀 있으면
    wafer 폴더 안의 같은 이름 파일을 쓴다(Para #49)."""
    name = (name or "").strip().strip('"')
    base = re.split(r"[\\/]", name)[-1]
    if names is not None and (re.search(r"^[A-Za-z]:|^[\\/]|[\\/]", name)) and base.lower() in names:
        return wafer / names[base.lower()]
    if names is not None and name.lower() in names:
        return wafer / names[name.lower()]
    path = (wafer / name)
    try:
        if os.path.commonpath([os.path.abspath(path), os.path.abspath(wafer)]) != os.path.abspath(wafer):
            return None
    except ValueError:
        return None
    return path


def plan_wafer(wafer):
    """Match every color image of one wafer. Returns (records, failures)."""
    wafer = Path(wafer)
    names = file_names(wafer)
    colors = parse_colors(wafer_file(wafer, WAFER_FILES[0], names))
    frames = parse_frames(wafer_file(wafer, WAFER_FILES[1], names))
    tfiles = transform_files(wafer, names)
    if not tfiles:
        raise ValueError(f"{TRANSFORM_NAME} 이 없습니다")
    parsed = {}

    def transform(recipe):
        f = transform_for(tfiles, recipe)
        if f not in parsed:
            parsed[f] = parse_transform(f)
        return parsed[f]

    def recipe_of(color):
        try:
            return int(float(color.get("RecipeNumber", "1") or 1))
        except (TypeError, ValueError):
            return 1

    for color in colors:
        transform(recipe_of(color))             # 변환 파일 오류는 한 번에 알린다(Color 마다 숨기지 않음)
    rect = frames_rect(frames, transform)

    def match(mode):
        out = []
        for color in colors:
            inverse, offset = transform(recipe_of(color))
            try:
                fx, fy = fault_xy(color)
                out.append(choose_frame(color, frames, inverse, offset, map_xy(mode, fx, fy, rect)) + ((fx, fy),))
            except (TypeError, ValueError):
                out.append(None)
        return out

    # 그대로 → 다 맞으면 끝. 못 맞는 것이 있으면 좌측 하단 원점 해석들을 시험해 가장 많이 맞는 것을 쓴다.
    mode, best = 0, match(0)
    hits = sum(1 for m in best if m and m[0])
    if rect is not None and hits < sum(1 for m in best if m):
        for alt in range(1, len(COORD_MODES)):
            trial = match(alt)
            n = sum(1 for m in trial if m and m[0])
            if n > hits:
                mode, best, hits = alt, trial, n

    records, failures = [], []
    for index, (color, m) in enumerate(zip(colors, best), 1):
        if m is None:
            failures.append((color.get("file", ""), "좌표 값을 읽을 수 없음"))
            continue
        frame, px, py, count, (fx, fy) = m
        color_path = _inside(wafer, color["file"], names)
        gray_path = _inside(wafer, frame["file"], names) if frame else None
        if not frame:
            failures.append((color["file"], "매칭되는 Gray 프레임 없음"))
            continue
        if color_path is None or not os.path.exists(long_path(color_path)) or gray_path is None or not os.path.exists(long_path(gray_path)):
            failures.append((color["file"], "Color 또는 Gray 파일 없음"))
            continue
        crop_w, crop_h, out_w, out_h = crop_size(color)
        records.append(dict(index=index, color_file=color["file"], gray_file=frame["file"],
                            color_path=str(color_path), gray_path=str(gray_path),
                            fault_x=fx, fault_y=fy, pixel_x=px, pixel_y=py, candidate_count=count,
                            crop_w=crop_w, crop_h=crop_h, out_w=out_w, out_h=out_h, coord=COORD_MODES[mode]))
    plan_wafer.last_coord = COORD_MODES[mode]
    return records, failures, len(colors)


def diagnose(wafer, failures, records=()) -> dict:
    """매칭이 안 될 때 화면에 보일 요약(Para #49): 실패 이유별 수 · 파일 수 · 첫 실패의 좌표."""
    wafer = Path(wafer)
    names = file_names(wafer)
    reasons = {}
    for _, why in failures:
        reasons[why] = reasons.get(why, 0) + 1
    out = dict(reasons=reasons, transform=[p.name for p in transform_files(wafer, names).values()])
    try:
        colors = parse_colors(wafer_file(wafer, WAFER_FILES[0], names))
        frames = parse_frames(wafer_file(wafer, WAFER_FILES[1], names))
    except OSError:
        return out
    out["colors"] = len(colors)
    out["frames"] = len(frames)
    out["frame_recipes"] = sorted({str(f["recipe"]) for f in frames})
    out["color_recipes"] = sorted({str(c.get("RecipeNumber", "1")) for c in colors})
    out["jpg_files"] = sum(1 for n in names if n.endswith((".jpg", ".jpeg")))
    if frames:
        out["frame_example"] = frames[0]["file"]
    if colors:
        out["color_example"] = colors[0].get("file", "")
    # 프레임이 없다고 한 첫 Color: 가장 가까운 프레임에서 계산한 Gray 픽셀 좌표
    bad = {f for f, why in failures if why == "매칭되는 Gray 프레임 없음"}
    for c in colors:
        if c.get("file") not in bad:
            continue
        try:
            tf = transform_files(wafer, names)
            inverse, offset = parse_transform(transform_for(tf, int(float(c.get("RecipeNumber", "1") or 1))))
            fx, fy = fault_xy(c)
        except (TypeError, ValueError, OSError):
            break
        best = None
        for fr in frames:
            tx, ty = fx - fr["x"] - offset[0], fy - fr["y"] - offset[1]
            px = inverse[0][0] * tx + inverse[0][1] * ty
            py = inverse[1][0] * tx + inverse[1][1] * ty
            d = max(0, -px, px - GW) + max(0, -py, py - GH)
            if best is None or d < best[0]:
                best = (d, fr["file"], round(px, 1), round(py, 1))
        if best:
            out["nearest"] = dict(color=c.get("file"), fault=[fx, fy], frame=best[1], px=best[2], py=best[3], gw=GW, gh=GH)
        break
    return out


# ---------------------------------------------------------------- outputs
def output_names(record_index: int, color_file: str):
    stem = Path(color_file).stem
    safe = re.sub(r'[\\/:*?"<>|]+', "_", stem)[:120] or f"{record_index:04d}"
    return {"crop": f"{CROPS}/{safe}_gray_crop.jpeg",
            "color_thumb": f"{THUMBS}/{record_index:04d}_color.jpg",
            "gray_thumb": f"{THUMBS}/{record_index:04d}_gray.jpg",
            "crop_thumb": f"{THUMBS}/{record_index:04d}_crop.jpg"}


def excel_link(base, target):
    base, target = Path(base).resolve(), Path(target).resolve()
    try:
        return ".\\" + str(target.relative_to(base)).replace("/", "\\")
    except ValueError:
        return str(target)


def jpeg_size(data: bytes):
    """(width, height) from a baseline/progressive JPEG header, or None."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + length
    return None


def _jpeg_image_class():
    from openpyxl.drawing.image import Image

    class JpegImage(Image):
        """openpyxl image from JPEG bytes — no Pillow (Para allows openpyxl only)."""

        def __init__(self, data: bytes, width: int, height: int):  # noqa: D401 - no super(): it needs Pillow
            self.ref = None
            self._bytes = data
            self.width, self.height = width, height
            self.format = "jpeg"
            self.anchor = "A1"

        def _data(self):
            return self._bytes

    return JpegImage


def build_workbook(result: Path, wafer_name: str, records, callback=None):
    """`records` carry the original paths and the output files written for them."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    JpegImage = _jpeg_image_class()
    result = Path(result)
    output = result / f"{wafer_name}_Color_Gray_Crop.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Image_Comparison"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    ws.append(["Color image", "Gray image", "Cropped gray image", "Coordinates / matching details"])
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1B345F")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    for col in "ABC":
        ws.column_dimensions[col].width = 52
    ws.column_dimensions["D"].width = 58
    total = max(1, len(records))
    for n, rec in enumerate(records, 1):
        row = n + 1
        ws.row_dimensions[row].height = 205
        for col, thumb, target, label in (("A", "color_thumb", "color_path", "Color 사진 열기"),
                                          ("B", "gray_thumb", "gray_path", "Gray 사진 열기"),
                                          ("C", "crop_thumb", "crop_path", "Crop 사진 열기")):
            cell = ws[f"{col}{row}"]
            cell.value = label
            cell.hyperlink = excel_link(output.parent, rec[target])
            cell.style = "Hyperlink"
            cell.alignment = Alignment(horizontal="center", vertical="bottom")
            data = Path(rec[thumb]).read_bytes()
            if jpeg_size(data):
                picture = JpegImage(data, TW, 245)
                ws.add_image(picture, f"{col}{row}")
        ws.cell(row, 4, f"Color: {rec['color_file']}\nGray: {rec['gray_file']}\n"
                        f"Fault: {rec['fault_x']:.3f}, {rec['fault_y']:.3f}\n"
                        f"Gray Pixel: {rec['pixel_x']:.1f}, {rec['pixel_y']:.1f}\n"
                        f"Candidates: {rec['candidate_count']}\nCrop: {tuple(rec.get('crop_box') or ())}")
        ws.cell(row, 4).alignment = Alignment(wrap_text=True, vertical="top")
        callback and callback(n, total)
    wb.save(output)
    return output


def write_failures(result: Path, failures):
    path = Path(result) / "unmatched_or_missing.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerows([("ColorFile", "Reason"), *failures])
    return path


# ---------------------------------------------------------------- v14: 최종 목록 CSV (Defect 분석)
# AOI Contrast Wizard 5-3 [📄 최종 목록 CSV 저장](HTML `FL_HEAD`)이 쓰는 열 이름이 약속이다 — HTML 을 바꾸면 여기도.
FINAL_FOLDER_COLS = ("매칭폴더", "매칭폴더(고른 폴더부터)")
FINAL_COLOR_COL = "Color 파일"
FINAL_MAX_ROWS = 5000                                 # CSV 는 한 번에 엔진으로 보낸다(4 MB 한도)
FINAL_IMG_H = 180                                     # 사진 줄 높이(px) — HTML XL_IMG_H 와 같음
# (제목, 폭 px, 사진 종류 또는 CSV 열 이름) — HTML 최종 목록 엑셀(XL_COLS)과 같은 차례 · 제목
FINAL_COLS = [("5-1 #", 52, "5-1 #"), ("Lot", 130, "Lot"), ("Slot", 110, "Slot"), ("ID", 60, "ID"),
              ("첫번째 분류", 130, "첫번째 분류"), ("재분류", 130, "재분류"), ("Recipe", 110, "Recipe"),
              ("Contrast(실제)", 96, "Contrast(실제)"),
              ("Color", 250, "img:color_view"), ("Gray Crop (빨간 네모 = Defect)", 250, "img:crop_mark"),
              ("Gray 프레임 (빨간 네모 = Defect · 노란 상자 = Crop 범위)", 570, "img:frame_mark"),
              ("상태", 150, "#state"), ("Area µm²", 80, "Area µm²"), ("Width", 64, "Width"), ("Length", 64, "Length"),
              ("Box W×H", 84, "#box"), ("Wafer X", 84, "Wafer X"), ("Wafer Y", 84, "Wafer Y"),
              ("Die (장비 Col, Row)", 110, "Die (장비 Col, Row)"), ("Color 파일", 190, "Color 파일"),
              ("Color 전체 경로", 380, "#color_path"), ("Gray 파일", 190, "#gray_file"), ("Gray 전체 경로", 380, "#gray_path"),
              ("사진 없음 이유", 240, "#reason"), ("Lot 경로", 300, "Lot 경로"), ("흑백 GL 평균 (원)", 110, "흑백 GL 평균 (원)"),
              ("Gray 위치 계산", 140, "#calc"), ("매칭폴더", 380, "#folder"),
              ("Zone", 90, "Zone"), ("Region", 70, "Region"), ("판정 비트", 110, "판정 비트"), ("분류 코드", 80, "분류 코드"),
              ("Zone 이름", 110, "Zone 이름"), ("판정 종류", 150, "판정 종류")]


def base_name(name: str) -> str:
    return re.split(r"[\\/]", (name or "").strip().strip('"'))[-1]


def parse_final_csv(text: str) -> list[dict]:
    """최종 목록 CSV(UTF-8, BOM 있어도 됨) → 줄마다 {열 이름: 값}. 우리 형식이 아니면 ValueError."""
    rows = list(csv.reader(io.StringIO((text or "").lstrip("﻿"))))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("빈 CSV 입니다")
    head = [h.strip() for h in rows[0]]
    if FINAL_COLOR_COL not in head or not any(c in head for c in FINAL_FOLDER_COLS):
        raise ValueError("최종 목록 CSV 가 아닙니다 — Defect 분석 › Defect 분석(대규모) 5-3 의 [📄 최종 목록 CSV 저장] 파일을 고르십시오"
                         f"('{FINAL_COLOR_COL}' · '매칭폴더' 열이 있어야 함)")
    if len(rows) - 1 > FINAL_MAX_ROWS:
        raise ValueError(f"줄이 너무 많습니다({len(rows) - 1}개 > {FINAL_MAX_ROWS})")
    return [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head)} for r in rows[1:]]


def is_abs_path(v) -> bool:
    v = (v or "").strip().strip('"')
    return bool(v) and (Path(v).is_absolute() or v.startswith("\\\\") or bool(re.match(r"^[A-Za-z]:[\\/]", v)))


def final_folder(row: dict, base=None):
    """그 줄의 매칭 폴더(있는 폴더만). 전체 경로가 있으면 그대로, 상대 경로(고른 폴더부터)면 base(사람이 고른 폴더)와 붙여 본다."""
    tried = []
    for key in FINAL_FOLDER_COLS:
        v = (row.get(key) or "").strip().strip('"')
        if not v:
            continue
        if is_abs_path(v):
            tried.append(Path(v))
        elif base:
            base = Path(base)
            segs = [s for s in re.split(r"[\\/]", v) if s]
            tried += [base.joinpath(*segs), base.parent.joinpath(*segs)]
            if segs and segs[0].lower() == base.name.lower():
                tried.append(base.joinpath(*segs[1:]))
    for p in tried:
        if os.path.isdir(long_path(p)):
            return p
    return None


def _num(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def final_fallback(wafer: Path, row: dict, index: int):
    """프로그램 매칭에 없는 줄(목록 · 변환 파일이 없는 Slot 등): 최종 목록 CSV 의 Gray 프레임 · Gray 위치 · Crop 크기
    (HTML 이 대신 계산한 값)로 같은 처리를 한다. 파일이 없거나 값이 없으면 (None, 이유)."""
    wafer = Path(wafer)
    names = file_names(wafer)
    cname, gname = base_name(row.get(FINAL_COLOR_COL, "")), base_name(row.get("Gray 파일", ""))
    if not cname:
        return None, "Color 파일 이름 없음"
    cpath = _inside(wafer, cname, names)
    if cpath is None or not os.path.exists(long_path(cpath)):
        return None, f"Color 파일 없음: {cname}"
    px, py = _num(row.get("GrayPX(3168x1024기준)")), _num(row.get("GrayPY(3168x1024기준)"))
    if not gname or px is None or py is None:
        return None, "Gray 위치 없음(프로그램 매칭에도, 최종 목록 CSV 에도)"
    gpath = _inside(wafer, gname, names)
    if gpath is None or not os.path.exists(long_path(gpath)):
        return None, f"Gray 파일 없음: {gname}"
    cw, ch = _num(row.get("CropW")), _num(row.get("CropH"))
    crop_w, crop_h, out_w, out_h = crop_size({})
    if cw and ch:
        crop_w, crop_h = max(1, round(cw)), max(1, round(ch))
    return dict(index=index, color_file=cname, gray_file=gname, color_path=str(cpath), gray_path=str(gpath),
                fault_x=_num(row.get("Wafer X")) or 0.0, fault_y=_num(row.get("Wafer Y")) or 0.0,
                pixel_x=px, pixel_y=py, candidate_count=0, crop_w=crop_w, crop_h=crop_h, out_w=out_w, out_h=out_h,
                coord="최종 목록 CSV 값"), ""


def _final_value(item: dict, key: str):
    row, rec = item["row"], item.get("rec")
    if key == "#state":
        return "추출 완료" if item.get("done") else "사진 없음"
    if key == "#reason":
        return "" if item.get("done") else (item.get("reason") or "처리 안 됨(취소 또는 오류)")
    if key == "#box":
        bw, bh = row.get("BoxW", ""), row.get("BoxH", "")
        return f"{bw}×{bh}" if bw or bh else row.get("Box W×H", "")
    if key == "#calc":
        return rec.get("calc", "") if rec else ""
    if key == "#folder":
        return item.get("folder", "")
    if key == "#color_path":
        return rec["color_path"] if rec else row.get("Color 전체 경로", "")
    if key == "#gray_path":
        return rec["gray_path"] if rec else row.get("Gray 전체 경로", "")
    if key == "#gray_file":
        return base_name(rec["gray_file"]) if rec else row.get("Gray 파일", "")
    v = str(row.get(key, "") or "").strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def build_final_workbook(path: Path, items: list[dict], callback=None) -> Path:
    """최종 목록 엑셀 — HTML 5-3 [💾 최종 목록 엑셀 저장]과 같은 열 · 사진 3장(Color · Gray Crop 빨간 네모 · Gray 프레임 노란 상자).
    items = [{row(CSV 줄), rec(처리한 기록 또는 None), done, reason, folder, pictures:{kind: 파일}}] — CSV 차례."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    JpegImage = _jpeg_image_class()
    wb = Workbook()
    ws = wb.active
    ws.title = "최종목록"
    ws.append([c[0] for c in FINAL_COLS])
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1B345F")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 34
    for ci, (_, px, _) in enumerate(FINAL_COLS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = round(px / 7, 1)
    ws.freeze_panes = "I2"
    total = max(1, len(items))
    for n, item in enumerate(items, 1):
        r = n + 1
        ws.row_dimensions[r].height = round((FINAL_IMG_H + 8) * 0.75, 1)
        for ci, (_, px, key) in enumerate(FINAL_COLS, 1):
            cell = ws.cell(r, ci)
            if key.startswith("img:"):
                f = (item.get("pictures") or {}).get(key[4:])
                data = Path(f).read_bytes() if f and os.path.exists(long_path(f)) else b""
                size = jpeg_size(data) if data else None
                if size:
                    k = min(1.0, (px - 8) / size[0], FINAL_IMG_H / size[1])
                    ws.add_image(JpegImage(data, max(1, round(size[0] * k)), max(1, round(size[1] * k))), f"{get_column_letter(ci)}{r}")
                else:
                    cell.value = "(사진 없음)"
            else:
                cell.value = _final_value(item, key)
            cell.alignment = Alignment(vertical="top", wrap_text=key in ("#reason",))
        callback and callback(n, total)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(FINAL_COLS))}{len(items) + 1}"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
