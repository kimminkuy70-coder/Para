"""Para 프로그램 아이콘 생성 — 추가 패키지 없이 표준 라이브러리(zlib)만 사용.

디자인
------
  · 웨이퍼(원형 + 노치 + 다이 격자) = 반도체 검사 대상
  · 위쪽 AOI 검사 카메라(경통 + 렌즈 + 조명 링) = 광학 검사
  · 아래쪽 파라미터 슬라이더 3줄 = 파라미터 설정/관리
  · 파랑→청록 그라데이션 배경 라운드 사각형(산업용 소프트웨어 톤)
  · 중앙 하단에 "AOI" 표기(작게 줄여도 읽히도록 굵은 획)
  · 배경 투명(라운드 사각형 밖은 알파 0)

Camtek 공식 로고는 쓰지 않고 전부 도형으로 새로 그린다.

산출물: param_manager/data/para_icon.ico (16/24/32/48/64/128/256)
        param_manager/data/para_icon.png (256, 미리보기)

사용: python3 tools/make_icon.py
"""

from __future__ import annotations

import math
import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "param_manager", "data")
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 4                      # 슈퍼샘플링 배율(계단현상 제거)

# 팔레트 — 파랑 → 청록
BG_TOP = (23, 78, 166)      # 진한 파랑
BG_BOT = (13, 148, 160)     # 청록
WAFER = (231, 245, 252)
WAFER_EDGE = (255, 255, 255)
DIE_LINE = (99, 160, 200)
LENS_DARK = (12, 42, 82)
LENS_GLASS = (56, 189, 214)
RING = (125, 232, 245)
SLIDER_TRACK = (255, 255, 255)
KNOB = (255, 214, 102)      # 노랑 포인트(슬라이더 손잡이)
TEXT = (255, 255, 255)


class Canvas:
    """RGBA 캔버스 — 알파 합성 방식으로 도형을 그린다."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 4)          # 전부 투명

    def blend(self, x, y, rgb, a):
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 4
        dr, dg, db, da = self.px[i:i + 4]
        a = min(1.0, a)
        na = a + da / 255.0 * (1 - a)
        if na <= 0:
            return
        for k, sv in enumerate(rgb):
            dv = self.px[i + k]
            self.px[i + k] = int(round((sv * a + dv / 255.0 * da / 255.0 * (1 - a) * 255)
                                       / na))
        self.px[i + 3] = int(round(na * 255))

    # ── 도형 ────────────────────────────────────────────────────────────
    def round_rect(self, x0, y0, x1, y1, r, color_fn):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                dx = min(x - x0, x1 - x)
                dy = min(y - y0, y1 - y)
                if dx < r and dy < r:
                    d = math.hypot(r - dx, r - dy)
                    if d > r:
                        continue
                self.blend(x, y, color_fn(x, y), 1.0)

    def disc(self, cx, cy, rad, rgb, a=1.0):
        for y in range(int(cy - rad) - 1, int(cy + rad) + 2):
            for x in range(int(cx - rad) - 1, int(cx + rad) + 2):
                if math.hypot(x - cx, y - cy) <= rad:
                    self.blend(x, y, rgb, a)

    def ring(self, cx, cy, rad, width, rgb, a=1.0):
        inner = rad - width
        for y in range(int(cy - rad) - 1, int(cy + rad) + 2):
            for x in range(int(cx - rad) - 1, int(cx + rad) + 2):
                d = math.hypot(x - cx, y - cy)
                if inner <= d <= rad:
                    self.blend(x, y, rgb, a)

    def ellipse_ring(self, cx, cy, rx, ry, width, rgb, a=1.0):
        """타원 테두리 — 글자 'O' 처럼 세로로 긴 링에 쓴다(원으로 그리면 폭에
        갇혀 점처럼 작아진다)."""
        ix, iy = max(0.1, rx - width), max(0.1, ry - width)
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = x - cx, y - cy
                if (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0 and \
                        (dx / ix) ** 2 + (dy / iy) ** 2 >= 1.0:
                    self.blend(x, y, rgb, a)

    def rect(self, x0, y0, x1, y1, rgb, a=1.0):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.blend(x, y, rgb, a)

    def bar(self, x0, y0, x1, y1, rgb, a=1.0):
        """양끝이 둥근 막대(슬라이더 트랙)."""
        r = (y1 - y0) / 2.0
        cy = (y0 + y1) / 2.0
        self.rect(x0 + r, y0, x1 - r, y1, rgb, a)
        self.disc(x0 + r, cy, r, rgb, a)
        self.disc(x1 - r, cy, r, rgb, a)

    def poly(self, pts, rgb, a=1.0):
        """볼록/오목 다각형 채우기(scanline)."""
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x1_, y1_ = pts[i]
                x2_, y2_ = pts[(i + 1) % n]
                if (y1_ <= y < y2_) or (y2_ <= y < y1_):
                    t = (y - y1_) / (y2_ - y1_)
                    xs.append(x1_ + t * (x2_ - x1_))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(xs[i], y, xs[i + 1], y, rgb, a)

    def downsample(self, factor):
        w, h = self.w // factor, self.h // factor
        out = Canvas(w, h)
        f2 = factor * factor
        for y in range(h):
            for x in range(w):
                r = g = b = a = 0
                for dy in range(factor):
                    for dx in range(factor):
                        i = ((y * factor + dy) * self.w + (x * factor + dx)) * 4
                        pa = self.px[i + 3]
                        r += self.px[i] * pa
                        g += self.px[i + 1] * pa
                        b += self.px[i + 2] * pa
                        a += pa
                j = (y * w + x) * 4
                if a:
                    out.px[j] = min(255, r // a)
                    out.px[j + 1] = min(255, g // a)
                    out.px[j + 2] = min(255, b // a)
                out.px[j + 3] = a // f2
        return out

    def to_png(self) -> bytes:
        raw = bytearray()
        for y in range(self.h):
            raw.append(0)                               # 필터 None
            raw += self.px[y * self.w * 4:(y + 1) * self.w * 4]

        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))


# ── 글자(획으로 직접 구성 — 폰트 의존 없음) ───────────────────────────────
def draw_letter(c, ch, x, y, w, h, t, rgb):
    """A/O/I/P/V 를 굵은 획으로 그린다(작은 크기에서도 뭉개지지 않게)."""
    if ch == "A":
        c.poly([(x + w / 2, y), (x + w, y + h), (x + w - t, y + h),
                (x + w / 2, y + t * 1.2), (x + t, y + h), (x, y + h)], rgb)
        c.rect(x + w * 0.26, y + h * 0.62, x + w * 0.74, y + h * 0.62 + t * 0.8, rgb)
    elif ch == "O":
        # 타원 링 — 글자 높이를 꽉 채운다. (가운데를 알파 0 으로 뚫으면 배경까지
        # 구멍이 나므로 절대 그렇게 하지 않는다.)
        c.ellipse_ring(x + w / 2, y + h / 2, w / 2, h / 2, t, rgb)
    elif ch == "I":
        c.rect(x + w / 2 - t / 2, y, x + w / 2 + t / 2, y + h, rgb)
    elif ch == "P":
        c.rect(x, y, x + t, y + h, rgb)
        c.rect(x, y, x + w * 0.85, y + t, rgb)
        c.rect(x, y + h * 0.45, x + w * 0.85, y + h * 0.45 + t, rgb)
        c.rect(x + w * 0.85 - t, y, x + w * 0.85, y + h * 0.45 + t, rgb)
    elif ch == "V":
        c.poly([(x, y), (x + t, y), (x + w / 2, y + h - t), (x + w - t, y), (x + w, y),
                (x + w / 2 + t * 0.1, y + h), (x + w / 2 - t * 0.1, y + h)], rgb)


def draw_icon(size):
    """size 픽셀 아이콘 1장 생성(내부적으로 SS 배 크게 그린 뒤 축소)."""
    S = size * SS
    c = Canvas(S, S)
    # 크기별 단계 — 작은 아이콘에 다 넣으면 뭉개져서 오히려 못 알아본다.
    #   tiny(≤24px): 글자·격자 생략, 웨이퍼/카메라를 키운 **실루엣**만
    #   small(≤48px): 격자·광선 생략, 글자는 표시
    #   그 외: 전부
    tiny = size <= 24
    small = size <= 48

    # 배경: 라운드 사각형 + 세로 그라데이션
    pad = S * 0.045
    def grad(_x, y):
        t = (y - pad) / max(1.0, (S - 2 * pad))
        t = min(1.0, max(0.0, t))
        return tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
    c.round_rect(pad, pad, S - pad, S - pad, S * 0.22, grad)

    # ── 웨이퍼(원) ──
    wcx, wcy = S * 0.5, (S * 0.545 if tiny else S * 0.515)
    wr = S * (0.285 if tiny else 0.225)
    c.disc(wcx, wcy, wr, WAFER)
    c.ring(wcx, wcy, wr, max(1.0, S * 0.012), WAFER_EDGE)
    # 노치(웨이퍼 방향 표식)
    nr = wr * 0.16
    c.disc(wcx, wcy - wr, nr, grad(wcx, wcy - wr))
    if not small:
        # 다이 격자(검사 영역) — 원 안쪽만. 글자가 놓일 중앙 띠는 비워 가독성 확보.
        step = wr * 0.5
        lw = max(1.0, S * 0.006)
        text_band = (wcy - S * 0.055, wcy + S * 0.055)
        for k in (-2, -1, 1, 2):
            off = k * step
            for i in range(int(-wr), int(wr)):
                x, y = wcx + i, wcy + off               # 가로선
                if math.hypot(x - wcx, y - wcy) <= wr - lw:
                    c.rect(x, y, x + lw, y + lw, DIE_LINE, 0.45)
                x, y = wcx + off, wcy + i               # 세로선
                if math.hypot(x - wcx, y - wcy) <= wr - lw \
                        and not (text_band[0] <= y <= text_band[1]):
                    c.rect(x, y, x + lw, y + lw, DIE_LINE, 0.45)

    # ── AOI 카메라(웨이퍼 위) ──
    cam_w, cam_h = (S * 0.34, S * 0.16) if tiny else (S * 0.30, S * 0.15)
    cam_x, cam_y = S * 0.5 - cam_w / 2, S * (0.10 if tiny else 0.135)
    c.round_rect(cam_x, cam_y, cam_x + cam_w, cam_y + cam_h, S * 0.035,
                 lambda _x, _y: LENS_DARK)
    # 경통(사다리꼴)
    c.poly([(S * 0.5 - cam_w * 0.30, cam_y + cam_h),
            (S * 0.5 + cam_w * 0.30, cam_y + cam_h),
            (S * 0.5 + cam_w * 0.19, cam_y + cam_h + S * 0.055),
            (S * 0.5 - cam_w * 0.19, cam_y + cam_h + S * 0.055)], LENS_DARK)
    # 렌즈 + 조명 링
    lcy = cam_y + cam_h + S * 0.058
    c.disc(S * 0.5, lcy, S * (0.062 if tiny else 0.052), LENS_GLASS)
    c.ring(S * 0.5, lcy, S * (0.062 if tiny else 0.052),
           max(1.0, S * (0.018 if tiny else 0.014)), RING)
    if not small:
        # 검사 광선(웨이퍼로 퍼지는 빛)
        c.poly([(S * 0.5 - S * 0.030, lcy + S * 0.030),
                (S * 0.5 + S * 0.030, lcy + S * 0.030),
                (S * 0.5 + S * 0.105, wcy - wr * 0.15),
                (S * 0.5 - S * 0.105, wcy - wr * 0.15)], RING, 0.30)

    # ── "AOI" 표기 — 밝은 웨이퍼 위에 **진한 남색**으로(흰 글자는 안 보인다) ──
    if not tiny:
        tw = S * (0.060 if small else 0.055)
        th_ = S * (0.088 if small else 0.080)
        gap = S * (0.016 if small else 0.018)
        total = tw * 3 + gap * 2
        tx = S * 0.5 - total / 2
        ty = wcy - th_ / 2
        stroke = max(1.5, S * (0.021 if small else 0.017))
        for i, ch in enumerate("AOI"):
            draw_letter(c, ch, tx + i * (tw + gap), ty, tw, th_, stroke,
                        LENS_DARK)

    # ── 파라미터 슬라이더(웨이퍼 아래, 겹치지 않게) ──
    rows = [(0.62,)] if small else [(0.62,), (0.36,), (0.80,)]
    if tiny:
        rows = [(0.62,)]
    base_y = wcy + wr + S * (0.035 if tiny else (0.055 if small else 0.045))
    th = S * (0.055 if tiny else (0.040 if small else 0.030))
    x0, x1 = (S * 0.22, S * 0.78) if tiny else (S * 0.27, S * 0.73)
    for idx, (kf,) in enumerate(rows):
        y0 = base_y + idx * S * 0.052
        if y0 + th > S - pad - S * 0.02:          # 배경 밖으로 나가면 그리지 않음
            break
        c.bar(x0, y0, x1, y0 + th, SLIDER_TRACK, 0.9)
        kx = x0 + (x1 - x0) * kf
        c.disc(kx, y0 + th / 2, th * 0.92, KNOB)

    return c.downsample(SS)


def build_ico(images) -> bytes:
    """PNG 들을 담은 .ico (Vista+ 는 PNG 압축 엔트리 허용)."""
    n = len(images)
    out = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries, blobs = b"", b""
    for size, png in images:
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0,
                               size if size < 256 else 0, 0, 0, 1, 32,
                               len(png), offset)
        blobs += png
        offset += len(png)
    return out + entries + blobs


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    images = []
    for size in ICO_SIZES:
        img = draw_icon(size)
        png = img.to_png()
        images.append((size, png))
        print(f"  {size:3d}x{size:<3d} {len(png):6d} bytes")
        if size == 256:
            with open(os.path.join(OUT_DIR, "para_icon.png"), "wb") as fh:
                fh.write(png)
    ico = build_ico(images)
    with open(os.path.join(OUT_DIR, "para_icon.ico"), "wb") as fh:
        fh.write(ico)
    print(f"생성: {os.path.join(OUT_DIR, 'para_icon.ico')} ({len(ico)} bytes)")


if __name__ == "__main__":
    main()
