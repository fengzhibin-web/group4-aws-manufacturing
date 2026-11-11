"""Generate 6,000 synthetic manufacturing records. No private business data."""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

rng = random.Random(5384)
start = datetime(2026, 9, 1, 0, 0, 0)
fields = ["timestamp", "machine_id", "shift", "product_id", "supplier_batch",
          "temperature", "defect_label", "batch_id", "defect_type"]
shifts = ["Day", "Evening", "Night"]
output = []
for i in range(6000):
    machine = f"M{rng.randint(1,4):02d}"
    shift = shifts[i % 3]
    batch = rng.choice(["SB-201", "SB-202", "SB-203", "SB-204", "SB-205"])
    anomaly = machine == "M03" and shift == "Night" and batch == "SB-204"
    temp = rng.gauss(88 if anomaly else 73, 3)
    defect = 1 if rng.random() < (0.45 if anomaly else 0.055) else 0
    output.append({
        "timestamp": (start + timedelta(minutes=i)).isoformat(timespec="seconds"),
        "machine_id": machine,
        "shift": shift,
        "product_id": f"P{rng.randint(1,3):02d}",
        "supplier_batch": batch,
        "temperature": f"{temp:.1f}",
        "defect_label": str(defect),
        "batch_id": f"B2026-{i // 200 + 1:03d}",
        "defect_type": rng.choice(["Surface", "Dimension", "Other"]) if defect else "",
    })
# Intentional controlled anomalies for the quality review demo.
for i in (90, 1100, 2400, 3600, 4800):
    output[i] = output[i - 1].copy()  # exact duplicate
for i in (200, 800, 2200):
    output[i]["defect_label"] = "unknown"  # should be flagged
for i in (700, 3100):
    output[i]["temperature"] = ""  # missing measurement
with (Path(__file__).parent / "manufacturing_6000.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(output)
print("Generated 6,000 synthetic rows")
