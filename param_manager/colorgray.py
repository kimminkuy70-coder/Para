"""Color · Gray 매칭 — AOI Color 이미지마다 같은 위치의 Gray 스캔 프레임을 찾아 잘라 붙인다.

Port of the stand-alone "AOI Color-Gray Matcher Final v16" (pywebview + Pillow) into
Para. The matching maths is unchanged; what differs is *where the pixels are
handled*: Para may not add packages (openpyxl only), so decoding, cropping,
thumbnails and JPEG encoding run in the app's own WebView (canvas), and this
module does everything else:

* find wafer folders under a Lot/Wafer folder (`discover`),
* parse `ColorImageGrabingInfo.ini`, `ScanResultImageList.txt` and
  `frameToChuckPlane.*.ini`, pick the gray frame that contains each color fault
  (`plan_wafer` / `choose_frame`) and the crop size (`crop_size`),
* write the comparison workbook with the thumbnails the UI produced
  (`build_workbook` — JPEG bytes embedded without Pillow via `JpegImage`).

The source folders are only read. Results go to a separate output folder.
"""
from __future__ import annotations

import csv
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
def transform_file(p: Path):
    files = sorted(Path(p).glob("frameToChuckPlane.*.ini"))
    return files[0] if files else None


def is_wafer(p: Path) -> bool:
    p = Path(p)
    return ((p / "ColorImageGrabingInfo.ini").exists() and (p / "ScanResultImageList.txt").exists()
            and transform_file(p) is not None)


def child_dirs(p: Path):
    try:
        with os.scandir(p) as entries:
            return sorted((Path(e.path) for e in entries if e.is_dir(follow_symlinks=False)),
                          key=lambda x: x.name.lower())
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
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


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
        parts = raw.strip().split(",")
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
        if "=" in raw:
            key, value = raw.split("=", 1)
            try:
                data[key.strip()] = [float(x) for x in value.split()]
            except ValueError:
                pass
    sx, sy = data["Scan_X"], data["Scan_Y"]
    m = ((sx[0], sx[1]), (sy[0], sy[1]))
    offset = (sx[2], sy[2])
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if det == 0:
        raise ValueError("frameToChuckPlane 변환 행렬을 풀 수 없습니다")
    inverse = ((m[1][1] / det, -m[0][1] / det), (-m[1][0] / det, m[0][0] / det))
    return inverse, offset


def fault_xy(color):
    return float(color.get("FaultX", color.get("X"))), float(color.get("FaultY", color.get("Y")))


def choose_frame(color, frames, inverse, offset):
    """Gray frame whose image contains the fault, preferring the one where it lies
    farthest from the frame edge. Returns (frame, px, py, candidate_count)."""
    fx, fy = fault_xy(color)
    recipe = int(color.get("RecipeNumber", "1"))
    candidates = []
    for frame in frames:
        if frame["recipe"] != recipe:
            continue
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


def _inside(wafer: Path, name: str):
    """A file named inside the wafer's list files; never outside the wafer folder."""
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
    colors = parse_colors(wafer / "ColorImageGrabingInfo.ini")
    frames = parse_frames(wafer / "ScanResultImageList.txt")
    inverse, offset = parse_transform(transform_file(wafer))
    records, failures = [], []
    for index, color in enumerate(colors, 1):
        try:
            frame, px, py, count = choose_frame(color, frames, inverse, offset)
            fx, fy = fault_xy(color)
        except (TypeError, ValueError):
            failures.append((color.get("file", ""), "좌표 값을 읽을 수 없음"))
            continue
        color_path = _inside(wafer, color["file"])
        gray_path = _inside(wafer, frame["file"]) if frame else None
        if not frame:
            failures.append((color["file"], "매칭되는 Gray 프레임 없음"))
            continue
        if color_path is None or not color_path.exists() or gray_path is None or not gray_path.exists():
            failures.append((color["file"], "Color 또는 Gray 파일 없음"))
            continue
        crop_w, crop_h, out_w, out_h = crop_size(color)
        records.append(dict(index=index, color_file=color["file"], gray_file=frame["file"],
                            color_path=str(color_path), gray_path=str(gray_path),
                            fault_x=fx, fault_y=fy, pixel_x=px, pixel_y=py, candidate_count=count,
                            crop_w=crop_w, crop_h=crop_h, out_w=out_w, out_h=out_h))
    return records, failures, len(colors)


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
