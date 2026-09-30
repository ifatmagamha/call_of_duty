"""Simulate edge cameras pushing people counts to the API.

A real deployment runs a person counter (e.g. a detector on a phone or Jetson) next to
each camera and POSTs the same JSON to /ingestion/camera.

    python scripts/simulate_cameras.py --interval 5
"""

import argparse
import json
import random
import time
import urllib.request


def call(base: str, path: str, body: dict | None = None):
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--rounds", type=int, default=0, help="0 = run forever")
    args = parser.parse_args()

    counts = {clinic["id"]: clinic["people_waiting"] for clinic in call(args.api, "/clinics")}
    round_number = 0
    while not args.rounds or round_number < args.rounds:
        round_number += 1
        for clinic_id in counts:
            # Queues mostly grow during an outbreak, with some drain.
            counts[clinic_id] = max(0, counts[clinic_id] + random.randint(-6, 9))
            observation = call(
                args.api,
                "/ingestion/camera",
                {
                    "clinic_id": clinic_id,
                    "camera_id": f"cam-{clinic_id}",
                    "people_count": counts[clinic_id],
                    "confidence": round(random.uniform(0.9, 0.99), 2),
                },
            )
            print(f"{clinic_id}: {counts[clinic_id]} people ({observation['status']})")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
