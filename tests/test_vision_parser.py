# test_vision_parser.py — focused tests for vision trace bbox parsing

import os
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
MAESTRO_DIR = str(Path(__file__).resolve().parent.parent / "maestro")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, MAESTRO_DIR)
os.environ["DATABASE_URL"] = "sqlite://"

from maestro.tools.vision import _extract_bboxes_from_trace

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")


print("\n== Vision Trace Parser ==")

# Rectangle extraction from code
trace = [{"type": "code", "content": "draw.rectangle((100, 200, 400, 500), outline='red')"}]
boxes = _extract_bboxes_from_trace(trace, image_width=1000, image_height=1000)
test("rectangle parsed", len(boxes) == 1)
test("rectangle normalized", boxes[0] == {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.3})

# Crop extraction + dedupe across entries
trace = [
    {"type": "code", "content": "crop = image.crop((50, 60, 350, 260))"},
    {"type": "code_result", "content": "image.crop((50,60,350,260))"},
]
boxes = _extract_bboxes_from_trace(trace, image_width=1000, image_height=1000)
test("crop deduped", len(boxes) == 1)
test("crop values", boxes[0] == {"x": 0.05, "y": 0.06, "width": 0.3, "height": 0.2})

# box_2d extraction from text
trace = [{"type": "text", "content": "Found object with box_2d=[10,20,60,80]"}]
boxes = _extract_bboxes_from_trace(trace, image_width=100, image_height=100)
test("box_2d parsed", len(boxes) == 1)
test("box_2d normalized", boxes[0] == {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6})

# Clamping and invalid/degenerate rejection
trace = [
    {"type": "code", "content": "draw.rectangle((-10, -10, 120, 120))"},
    {"type": "code", "content": "draw.rectangle((40, 40, 40, 80))"},  # degenerate, should be dropped
]
boxes = _extract_bboxes_from_trace(trace, image_width=100, image_height=100)
test("clamped + degenerate dropped", len(boxes) == 1)
test("clamped to full frame", boxes[0] == {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0})

# Empty/noisy trace
trace = [
    {"type": "text", "content": "no coordinates here"},
    {"type": "code_result", "content": "done"},
]
boxes = _extract_bboxes_from_trace(trace, image_width=1000, image_height=1000)
test("empty/noisy gives no boxes", boxes == [])

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")

if failed:
    sys.exit(1)
else:
    print("  ALL VISION PARSER TESTS PASSED!")
