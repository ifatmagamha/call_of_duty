"""Edge people counter: a local camera (or video file / RTSP URL) feeds a clinic's queue.

Counts people with OpenCV's built-in HOG pedestrian detector (no model download, no
API key) and POSTs each count to /ingestion/camera, exactly like a deployed edge device.

    python scripts/camera_counter.py --clinic clinic-b              # webcam 0
    python scripts/camera_counter.py --clinic clinic-b --source ../fixtures/footage.mp4
    python scripts/camera_counter.py --clinic clinic-b --snapshot last.jpg  # see detections

ponytail: HOG is a fast, dependency-free baseline that misses seated or crowded people;
swap count_people() for a YOLO/ONNX detector when accuracy matters.
"""

import argparse
import json
import time
import urllib.error
import urllib.request

import cv2
import numpy as np

HOG = cv2.HOGDescriptor()
HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def count_people(
    frame: np.ndarray, work_width: int = 1280, min_score: float = 0.3
) -> tuple[int, list, float]:
    """Return (count, boxes, confidence) for one BGR frame.

    Frames are resized to work_width: upscaling finds small, distant people (a queue
    photo went from 3 to 10 detections at 1280 px) at the cost of CPU time.
    """
    scale = work_width / max(frame.shape[1], 1)
    resized = cv2.resize(frame, None, fx=scale, fy=scale)
    boxes, weights = HOG.detectMultiScale(resized, winStride=(8, 8), padding=(8, 8), scale=1.05)
    if len(boxes) == 0:
        return 0, [], 0.95  # an empty scene is a confident zero
    scores = [float(w) for w in np.ravel(weights)]
    keep = cv2.dnn.NMSBoxes([list(map(int, b)) for b in boxes], scores, min_score, 0.4)
    kept = [boxes[i] for i in np.ravel(keep)] if len(keep) else []
    kept = [[int(v / scale) for v in box] for box in kept]
    confidence = float(np.mean([min(scores[i], 1.5) / 1.5 for i in np.ravel(keep)])) if kept else 0.95
    return len(kept), kept, round(confidence, 2)


def post_reading(api: str, clinic_id: str, camera_id: str, count: int, confidence: float) -> dict:
    body = json.dumps(
        {"clinic_id": clinic_id, "camera_id": camera_id, "people_count": count, "confidence": confidence}
    ).encode()
    request = urllib.request.Request(
        f"{api}/ingestion/camera", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clinic", required=True, help="clinic id this camera watches, e.g. clinic-b")
    parser.add_argument("--source", default="0", help="webcam index, video file, or RTSP/HTTP URL")
    parser.add_argument("--camera-id", default=None)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=5, help="seconds between readings")
    parser.add_argument("--work-width", type=int, default=1280,
                        help="detection resolution; raise for distant crowds, lower for speed")
    parser.add_argument("--min-confidence", type=float, default=0.0,
                        help="override the reported confidence floor (review below the API threshold)")
    parser.add_argument("--snapshot", default=None, help="write the latest annotated frame here")
    parser.add_argument("--once", action="store_true", help="send one reading and exit")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    camera_id = args.camera_id or f"cam-{args.clinic}"
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise SystemExit(f"Cannot open camera source {args.source!r}.")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                if isinstance(source, str):  # loop video files for demos
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                raise SystemExit("Camera stopped delivering frames.")
            count, boxes, confidence = count_people(frame, args.work_width)
            confidence = max(confidence, args.min_confidence)
            try:
                status = post_reading(args.api, args.clinic, camera_id, count, confidence)["status"]
            except (urllib.error.URLError, TimeoutError) as exc:
                if args.once:
                    raise SystemExit(f"API unreachable at {args.api}: {exc}")
                status = f"not sent, API unreachable ({exc}); retrying next interval"
            print(f"{time.strftime('%H:%M:%S')} {args.clinic}: {count} people "
                  f"(confidence {confidence:.2f}) -> {status}")
            if args.snapshot:
                for x, y, w, h in boxes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)
                cv2.putText(frame, f"{count} people", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 0), 2)
                cv2.imwrite(args.snapshot, frame)
            if args.once:
                return
            # Drop buffered frames so each reading reflects "now", not the queue backlog.
            deadline = time.time() + args.interval
            while time.time() < deadline:
                if not capture.grab():
                    time.sleep(0.05)
    finally:
        capture.release()


if __name__ == "__main__":
    main()
