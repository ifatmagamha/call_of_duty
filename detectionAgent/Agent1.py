"""
People & Queue Counting Agent
=============================

Detects people in a live video feed (webcam, video file, or RTSP stream),
tracks them across frames, and counts:
  1. Total number of people currently visible in the frame
  2. Number of people inside one or more defined "queue" zones
  3. (Optional) approximate wait time per person based on dwell time in a zone

Requirements:
    pip install ultralytics opencv-python numpy

Usage:
    python people_queue_counter.py --source 0                 # webcam
    python people_queue_counter.py --source video.mp4         # video file
    python people_queue_counter.py --source rtsp://<url>      # IP camera
    python people_queue_counter.py --source 0 --define-zone   # interactively draw a queue zone first

Press 'q' to quit while the video window is focused.
"""

import argparse
import time
import json
import os
from collections import defaultdict

import cv2
import numpy as np
from ultralytics import YOLO

PERSON_CLASS_ID = 0  # COCO class id for "person"
ZONES_FILE = "zones.json"


# --------------------------------------------------------------------------
# Zone handling
# --------------------------------------------------------------------------
def load_zones():
    if os.path.exists(ZONES_FILE):
        with open(ZONES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_zones(zones):
    with open(ZONES_FILE, "w") as f:
        json.dump(zones, f, indent=2)


def define_zone_interactively(source):
    """Let the user click points on the first frame to draw a queue polygon."""
    cap = cv2.VideoCapture(source)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("Could not read a frame from the source to define a zone.")

    points = []
    clone = frame.copy()

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([x, y])
            cv2.circle(clone, (x, y), 4, (0, 255, 0), -1)
            if len(points) > 1:
                cv2.line(clone, tuple(points[-2]), tuple(points[-1]), (0, 255, 0), 2)

    cv2.namedWindow("Define queue zone - click points, press 's' to save, 'esc' to skip")
    cv2.setMouseCallback("Define queue zone - click points, press 's' to save, 'esc' to skip", on_click)

    while True:
        cv2.imshow("Define queue zone - click points, press 's' to save, 'esc' to skip", clone)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("s") and len(points) >= 3:
            break
        if key == 27:  # ESC
            points = []
            break
    cv2.destroyAllWindows()

    zones = load_zones()
    if points:
        zone_name = f"queue_zone_{len(zones) + 1}"
        zones[zone_name] = points
        save_zones(zones)
        print(f"Saved zone '{zone_name}' with {len(points)} points to {ZONES_FILE}")
    return zones


def point_in_zone(point, polygon):
    return cv2.pointPolygonTest(np.array(polygon, dtype=np.int32), point, False) >= 0


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
def run(source, model_path="yolov8n.pt", conf=0.4, show=True):
    zones = load_zones()
    model = YOLO(model_path)

    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    # track_id -> first_seen_timestamp, for dwell-time estimation per zone
    zone_entry_time = defaultdict(dict)  # {zone_name: {track_id: entry_ts}}

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        results = model.track(
            frame,
            persist=True,
            classes=[PERSON_CLASS_ID],
            conf=conf,
            verbose=False,
        )[0]

        total_people = 0
        zone_counts = {name: 0 for name in zones}
        now = time.time()

        if results.boxes is not None and results.boxes.id is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            ids = results.boxes.id.cpu().numpy().astype(int)
            total_people = len(ids)

            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = box
                cx, cy = int((x1 + x2) / 2), int(y2)  # foot point (bottom-center)

                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 200, 255), 2)
                cv2.putText(frame, f"ID {track_id}", (int(x1), int(y1) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)

                for zone_name, polygon in zones.items():
                    if point_in_zone((cx, cy), polygon):
                        zone_counts[zone_name] += 1
                        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                        entry_map = zone_entry_time[zone_name]
                        entry_map.setdefault(track_id, now)
                        wait_s = now - entry_map[track_id]
                        cv2.putText(frame, f"{wait_s:.0f}s", (cx + 6, cy),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
                    else:
                        zone_entry_time[zone_name].pop(track_id, None)

        # Draw zones + counts
        for zone_name, polygon in zones.items():
            pts = np.array(polygon, dtype=np.int32)
            cv2.polylines(frame, [pts], isClosed=True, color=(255, 0, 0), thickness=2)
            label_pos = tuple(pts[0])
            cv2.putText(frame, f"{zone_name}: {zone_counts[zone_name]} waiting",
                        label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        cv2.putText(frame, f"Total people in frame: {total_people}", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        if show:
            cv2.imshow("People & Queue Counter", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="People & Queue Counting Agent")
    parser.add_argument("--source", default="0", help="0 for webcam, path to video file, or RTSP URL")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model weights (n/s/m/l/x)")
    parser.add_argument("--conf", type=float, default=0.4, help="Detection confidence threshold")
    parser.add_argument("--define-zone", action="store_true", help="Draw a queue zone before running")
    args = parser.parse_args()

    if args.define_zone:
        define_zone_interactively(args.source)

    run(args.source, model_path=args.model, conf=args.conf)