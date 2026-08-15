"""Run from Krita's Scripter to generate the Phase 6 host corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from krita import Krita, Selection

try:
    from PyQt6.QtCore import QByteArray
except ImportError:
    from PyQt5.QtCore import QByteArray

WIDTH = HEIGHT = 64
PROFILE = "sRGB-elle-V2-srgbtrc.icc"


def _rgba(width, height, color=(0, 0, 0, 0)):
    return bytearray(color * (width * height))


def _pixel(data, width, x, y, rgba):
    offset = (y * width + x) * 4
    data[offset : offset + 4] = bytes(rgba)


def _box(data, width, left, top, right, bottom, rgba):
    for x in range(left, right + 1):
        _pixel(data, width, x, top, rgba)
        _pixel(data, width, x, bottom, rgba)
    for y in range(top, bottom + 1):
        _pixel(data, width, left, y, rgba)
        _pixel(data, width, right, y, rgba)


def _bgra(data):
    result = bytearray(len(data))
    for offset in range(0, len(data), 4):
        result[offset : offset + 4] = bytes(
            (data[offset + 2], data[offset + 1], data[offset], data[offset + 3])
        )
    return QByteArray(bytes(result))


def _base_document(name, profile=PROFILE, width=WIDTH, height=HEIGHT):
    app = Krita.instance()
    document = app.createDocument(width, height, name, "RGBA", "U8", profile, 100.0)
    root = document.rootNode()
    existing = root.childNodes()
    coloring = existing[0] if existing else document.createNode("Coloring", "paintlayer")
    coloring.setName("Coloring")
    if not existing:
        root.addChildNode(coloring, None)
    line = document.createNode("Line Art", "paintlayer")
    guides = document.createNode("Guides", "paintlayer")
    root.addChildNode(guides, coloring)
    root.addChildNode(line, guides)
    return document, coloring, line, guides


def _set(node, rgba, width=WIDTH, height=HEIGHT):
    if not node.setPixelData(_bgra(rgba), 0, 0, width, height):
        raise RuntimeError(f"Krita rejected pixels for {node.name()}")


def _save(document, path):
    document.refreshProjection()
    document.waitForDone()
    if not document.saveAs(str(path)):
        raise RuntimeError(f"Krita failed to save {path}")
    document.close()


def _synthetic(output):
    coloring = _rgba(WIDTH, HEIGHT)
    line = _rgba(WIDTH, HEIGHT)
    guides = _rgba(WIDTH, HEIGHT)
    _box(line, WIDTH, 16, 16, 32, 32, (23, 41, 199, 255))
    for y in range(17, 32):
        for x in range(17, 32):
            if not (24 <= x <= 26 and 24 <= y <= 26):
                _pixel(coloring, WIDTH, x, y, (13, 117, 241, 255))
    document, target, line_node, guide_node = _base_document("ordinary-srgb")
    _set(target, coloring)
    _set(line_node, line)
    _set(guide_node, guides)
    _save(document, output / "ordinary-srgb.kra")

    _box(guides, WIDTH, 38, 12, 52, 26, (170, 21, 93, 255))
    document, target, line_node, guide_node = _base_document("guide-enclosed")
    _set(target, coloring)
    _set(line_node, line)
    _set(guide_node, guides)
    _save(document, output / "guide-enclosed.kra")

    document, target, line_node, guide_node = _base_document("multiple-colors")
    second = bytearray(coloring)
    _box(line, WIDTH, 38, 38, 54, 54, (11, 19, 31, 255))
    for y in range(39, 54):
        for x in range(39, 54):
            if not (46 <= x <= 48 and 46 <= y <= 48):
                _pixel(second, WIDTH, x, y, (227, 61, 17, 255))
    _set(target, second)
    _set(line_node, line)
    _set(guide_node, guides)
    _save(document, output / "multiple-colors.kra")

    document, target, line_node, guide_node = _base_document("soft-selection")
    _set(target, coloring)
    _set(line_node, line)
    _set(guide_node, guides)
    selection = Selection()
    values = bytearray(WIDTH * HEIGHT)
    values[24 * WIDTH + 24 : 24 * WIDTH + 28] = bytes((1, 64, 128, 255))
    selection.setPixelData(QByteArray(bytes(values)), 0, 0, WIDTH, HEIGHT)
    document.setSelection(selection)
    _save(document, output / "soft-selection.kra")

    document, target, line_node, guide_node = _base_document("moved-target")
    _set(target, coloring)
    _set(line_node, line)
    _set(guide_node, guides)
    target.move(3, 5)
    _save(document, output / "moved-target.kra")

    document, target, line_node, guide_node = _base_document("target-effects")
    _set(target, coloring)
    _set(line_node, line)
    _set(guide_node, guides)
    target.addChildNode(document.createTransformMask("Transform"), None)
    target.addChildNode(document.createTransparencyMask("Transparency"), None)
    _save(document, output / "target-effects.kra")

    landmarks = _rgba(WIDTH, HEIGHT)
    for x, y, color in (
        (0, 0, (255, 0, 0, 255)),
        (63, 0, (0, 255, 0, 255)),
        (0, 63, (0, 0, 255, 255)),
        (63, 63, (255, 255, 0, 255)),
    ):
        _pixel(landmarks, WIDTH, x, y, color)
    document, target, line_node, guide_node = _base_document("corner-landmarks")
    _set(target, landmarks)
    _set(line_node, line)
    _set(guide_node, guides)
    _save(document, output / "corner-landmarks.kra")

    alternate = next(
        (
            profile
            for profile in Krita.instance().profiles("RGBA", "U8")
            if str(profile) != PROFILE
        ),
        None,
    )
    if alternate is not None:
        document, target, line_node, guide_node = _base_document(
            "alternate-profile", str(alternate)
        )
        for node in (target, line_node, guide_node):
            node.setColorProfile(str(alternate))
        _set(target, coloring)
        _set(line_node, line)
        _set(guide_node, guides)
        _save(document, output / "alternate-profile.kra")


def _copy_real_case(repo, output, case_name, destination):
    source = repo / "tests" / "fixtures" / "gapfill" / "end_to_end" / "real" / case_name
    app = Krita.instance()
    opened = []
    try:
        for layer in ("coloring", "line", "guide"):
            document = app.openDocument(str(source / f"{layer}.png"))
            opened.append(document)
        width, height = opened[0].width(), opened[0].height()
        document, target, line_node, guide_node = _base_document(
            destination, PROFILE, width, height
        )
        for source_document, node in zip(opened, (target, line_node, guide_node)):
            raw = source_document.rootNode().projectionPixelData(0, 0, width, height)
            if not node.setPixelData(raw, 0, 0, width, height):
                raise RuntimeError("Krita rejected imported canonical fixture pixels")
        _save(document, output / f"{destination}.kra")
    finally:
        for document in opened:
            document.close()


def generate(repo_root, output_directory):
    repo = Path(repo_root).resolve()
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    _synthetic(output)
    _copy_real_case(repo, output, "E101_ex2_ordinary_crop", "real-ordinary-e101")
    _copy_real_case(repo, output, "E102_ex2_guide_crop", "real-guide-e102")
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob("*.kra"))
    }
    (output / "sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return hashes


# Edit these two paths, then run this line from Krita's Scripter.
# generate("/absolute/path/to/GapFill", "/absolute/output/krita-phase6-fixtures")
