import base64
import io
import json
import math
import os
import re
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import freetype as ft
from PIL import Image

ROOT = Path(__file__).parent
FONTS = []


def add_font(path):
    found = []
    try:
        face = ft.Face(str(path))
        for i in range(face.num_faces):
            f = ft.Face(str(path), i)
            item = {
                "id": len(FONTS),
                "path": str(path),
                "index": i,
                "name": (f.family_name or b"Font").decode("utf8", "replace")
                + " "
                + (f.style_name or b"").decode("utf8", "replace"),
                "sizes": sorted(set(round(s.y_ppem / 64) for s in f.available_sizes)),
            }
            FONTS.append(item)
            found.append(item)
    except ft.FT_Exception:
        pass
    return found


# Prioritize the Windows font collections shipped with Office.
for p in [
    Path("/Applications/Microsoft Word.app/Contents/Resources/DFonts/gulim.ttc"),
    Path("/Applications/Microsoft Word.app/Contents/Resources/DFonts/batang.ttc"),
]:
    if p.exists():
        add_font(p)
for folder in [
    Path.home() / "Library/Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
]:
    if folder.exists():
        for p in sorted(folder.rglob("*")):
            if p.suffix.lower() in (".ttf", ".ttc", ".otf") and len(FONTS) < 800:
                add_font(p)

for p in sorted((ROOT / "fonts").glob("*.font")):
    add_font(p)


def render(d):
    item = FONTS[int(d.get("font", 0))]
    f = ft.Face(item["path"], item["index"])
    stretch = int(d.get("stretch", 100))
    if not 25 <= stretch <= 300:
        raise ValueError("글자 너비는 25~300%로 설정하세요.")
    size = int(d.get("size", 12))
    scale = int(d.get("scale", 1))
    tracking = int(d.get("tracking", 0))
    leading = int(d.get("leading", 4))
    pad = int(d.get("padding", 8))
    if not (
        1 <= size <= 160
        and 1 <= scale <= 16
        and -20 <= tracking <= 100
        and 0 <= leading <= 100
        and 0 <= pad <= 200
    ):
        raise ValueError("설정 범위를 확인하세요.")
    text = str(d.get("text", ""))[:3000].replace("\r", "").replace("\t", "    ")
    strict = d.get("mode", "bitmap") == "bitmap"
    strike = next(
        (i for i, s in enumerate(f.available_sizes) if round(s.y_ppem / 64) == size),
        None,
    )
    if strict and strike is None:
        raise ValueError(
            "이 크기에는 내장 비트맵이 없습니다. 표시된 크기를 선택하세요."
        )
    if strict:
        f.select_size(strike)
    else:
        f.set_pixel_sizes(0, size)
    asc = math.ceil(f.size.ascender / 64)
    desc = max(0, math.ceil(-f.size.descender / 64))
    lineheight = max(size, asc + desc) + leading
    glyphs = []
    missing = []
    fallback = []
    minx = 0
    miny = 0
    maxx = 0
    maxy = asc + desc
    for row, line in enumerate(text.split("\n")):
        pen = 0
        for char in line:
            idx = f.get_char_index(ord(char))
            if not idx:
                missing.append(char)
                pen += size
                continue
            try:
                flags = (
                    ft.FT_LOAD_SBITS_ONLY
                    if strict
                    else ft.FT_LOAD_RENDER
                    | ft.FT_LOAD_NO_BITMAP
                    | ft.FT_LOAD_TARGET_MONO
                    | ft.FT_LOAD_MONOCHROME
                )
                f.load_glyph(idx, flags)
                if strict and f.glyph.format != ft.FT_GLYPH_FORMAT_BITMAP:
                    raise ValueError("내장 비트맵이 아닌 글리프입니다.")
            except (ft.FT_Exception, ValueError):
                if char.isspace():
                    pen += max(1, size // 2) + tracking
                    continue
                fallback.append(char)
                pen += size + tracking
                continue
            g = f.glyph
            b = g.bitmap
            w, h = b.width, b.rows
            x = pen + g.bitmap_left
            y = row * lineheight + asc - g.bitmap_top
            if w and h:
                raw = b.buffer
                pitch = abs(b.pitch)
                pixels = []
                for yy in range(h):
                    offset = (yy if b.pitch >= 0 else h - 1 - yy) * pitch
                    for xx in range(w):
                        v = (
                            (255 if raw[offset + xx // 8] & (128 >> (xx % 8)) else 0)
                            if b.pixel_mode == ft.FT_PIXEL_MODE_MONO
                            else raw[offset + xx]
                        )
                        if v:
                            pixels.append((xx, yy, v))
                glyphs.append((x, y, pixels))
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x + w)
                maxy = max(maxy, y + h)
            pen += round(g.advance.x / 64) + tracking
        maxx = max(maxx, pen - tracking if line else 0)
        maxy = max(maxy, row * lineheight + asc + desc)
    if missing or fallback:
        raise ValueError(
            "내장 비트맵/글자가 없는 문자: "
            + "".join(dict.fromkeys(missing + fallback))
            + " · 다른 글꼴이나 크기를 선택하세요."
        )
    width = max(1, maxx - minx + 2 * pad)
    height = max(1, maxy - miny + 2 * pad)
    if (
        width * height * scale * scale * max(1, stretch / 100) > 20000000
        or width * scale * max(1, stretch / 100) > 30000
        or height * scale > 30000
    ):
        raise ValueError("이미지가 너무 큽니다. 글자 수나 배율을 줄이세요.")
    color = str(d.get("color", "#111111"))
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("색상을 확인하세요.")
    rgb = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    bg = d.get("background", "transparent")
    image = Image.new(
        "RGBA",
        (width, height),
        (255, 255, 255, 0) if bg == "transparent" else (255, 255, 255, 255),
    )
    px = image.load()
    rects = []
    for x, y, pixels in glyphs:
        for xx, yy, v in pixels:
            px[x + xx - minx + pad, y + yy - miny + pad] = (*rgb, v)
    if stretch != 100:
        content_width = max(1, width - 2 * pad)
        target_width = max(1, round(content_width * stretch / 100))
        content = image.crop((pad, 0, pad + content_width, height)).resize(
            (target_width, height), Image.Resampling.NEAREST
        )
        width = target_width + 2 * pad
        image = Image.new(
            "RGBA",
            (width, height),
            (255, 255, 255, 0) if bg == "transparent" else (255, 255, 255, 255),
        )
        image.paste(content, (pad, 0))
        px = image.load()
    # Horizontal runs keep SVG compact and contain no dependent font or raster image.
    for y in range(height):
        x = 0
        while x < width:
            if px[x, y][3] and px[x, y][:3] == rgb:
                start = x
                alpha = px[x, y][3]
                while x < width and px[x, y] == (*rgb, alpha):
                    x += 1
                opacity = "" if alpha == 255 else f' opacity="{alpha / 255:.4f}"'
                rects.append(
                    f'<rect x="{start}" y="{y}" width="{x - start}" height="1"{opacity}/>'
                )
            else:
                x += 1
    background = (
        '<rect width="100%" height="100%" fill="white"/>' if bg != "transparent" else ""
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * scale}" height="{height * scale}" viewBox="0 0 {width} {height}" shape-rendering="crispEdges">{background}<g fill="{color}">{"".join(rects)}</g></svg>'
    image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return {
        "svg": svg,
        "png": base64.b64encode(out.getvalue()).decode(),
        "width": image.width,
        "height": image.height,
        "bitmap": strict,
        "font": item["name"],
        "size": size,
        "stretch": stretch,
    }


class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        host = self.headers.get("Host", "")
        if host not in ("127.0.0.1:8791", "localhost:8791"):
            self.send(403, {"error": "Only localhost requests are supported."})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + host:
            self.send(403, {"error": "Cross-origin requests are not supported."})
            return False
        return True

    def send(self, status, data, kind="application/json"):
        if isinstance(data, dict) or isinstance(data, list):
            data = json.dumps(data, ensure_ascii=False).encode()
        if isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.local_request():
            return
        if self.path == "/":
            self.send(
                200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8"
            )
        elif self.path == "/api/fonts":
            self.send(200, [{k: v for k, v in f.items() if k != "path"} for f in FONTS])
        else:
            self.send(404, {"error": "찾을 수 없습니다."})

    def do_POST(self):
        if not self.local_request():
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 20_000_000:
                raise ValueError("Request body must be between 1 byte and 20 MB.")
            raw = self.rfile.read(length)
            if self.path == "/api/render":
                self.send(200, render(json.loads(raw)))
            elif self.path == "/api/upload":
                target = ROOT / "fonts"
                target.mkdir(exist_ok=True)
                p = target / (os.urandom(8).hex() + ".font")
                p.write_bytes(raw)
                items = add_font(p)
                if not items:
                    p.unlink()
                    raise ValueError("읽을 수 있는 글꼴 파일이 아닙니다.")
                self.send(
                    200, [{k: v for k, v in f.items() if k != "path"} for f in items]
                )
            elif self.path == "/api/copy-svg":
                d = json.loads(raw)
                result = render(d)
                # NSPasteboard stores true public.svg-image plus an SVG text fallback.
                script = ROOT / "copy-svg.swift"
                with tempfile.TemporaryDirectory(
                    prefix="freetype-clipboard-"
                ) as folder:
                    p = Path(folder) / "clipboard.svg"
                    p.write_text(result["svg"], encoding="utf-8")
                    r = subprocess.run(
                        ["/usr/bin/swift", str(script), str(p)],
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )
                if r.returncode:
                    raise ValueError("SVG 복사 실패: " + r.stderr[-400:])
                self.send(200, {"ok": True})
            else:
                self.send(404, {"error": "찾을 수 없습니다."})
        except Exception as e:
            self.send(400, {"error": str(e)})


if __name__ == "__main__":
    print("FreeType Studio: http://127.0.0.1:8791", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8791), Handler).serve_forever()
