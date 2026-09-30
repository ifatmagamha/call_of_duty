import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "camera_counter.py"
spec = importlib.util.spec_from_file_location("camera_counter", SCRIPT)
camera_counter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera_counter)


def test_empty_scene_is_a_confident_zero_that_auto_applies():
    count, boxes, confidence = camera_counter.count_people(np.zeros((480, 640, 3), np.uint8))
    assert (count, boxes) == (0, [])
    assert confidence >= 0.90
