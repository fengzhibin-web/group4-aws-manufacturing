"""Group 4 CSV contract and deterministic report generation.

No AWS dependency: usable by local Streamlit, tests, and later shared Lambda code.
Version: v1; keep synchronized with the deployed Lambda before claiming parity.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from collections import Counter
from datetime import datetime

import pandas as pd

VERSION = "v1"
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000
REQUIRED = (
    "timestamp", "machine_id", "shift", "product_id", "supplier_batch",
    "temperature", "defect_label",
)
OPTIONAL = ("batch_id", "defect_type")
MACHINES = ("M01", "M02", "M03", "M04")
SHIFTS = ("Day", "Evening", "Night")
# This is only a demo warning band, NOT a manufacturing acceptance threshold.
TEMP_REVIEW_BAND_C = (60.0, 90.0)


def stable_job_id(data: bytes, processing_version: str = VERSION) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return hashlib.sha256(f"{digest}:{processing_version}".encode()).hexdigest()[:16]


def _load(data: bytes, filename: str) -> tuple[pd.DataFrame | None, list[str]]:
    errors = []
    if not filename.lower().endswith(".csv"):
        errors.append("只接受 .csv 文件")
    if len(data) > MAX_BYTES:
        errors.append("文件大于 10 MiB 限制")
    if not data:
        errors.append("文件为空")
    if errors:
        return None, errors
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, ["文件需使用 UTF-8 编码（支持 UTF-8 BOM）"]
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        return None, [f"CSV结构解析失败：{exc}"]
    if not rows:
        return None, ["CSV缺少表头"]
    columns = rows[0]
    if len(columns) != len(set(columns)):
        errors.append("列名重复")
    missing = sorted(set(REQUIRED) - set(columns))
    if missing:
        errors.append("缺少必需列：" + ", ".join(missing))
    if len(rows) < 2:
        errors.append("CSV没有数据行")
    if len(rows) - 1 > MAX_ROWS:
        errors.append(f"数据行超过 {MAX_ROWS:,} 行")
    malformed = [i for i, row in enumerate(rows[1:], start=2) if len(row) != len(columns)]
    if malformed:
        errors.append("行的列数与表头不一致（CSV行号：" + ", ".join(map(str, malformed[:6])) + "）")
    if errors:
        return None, errors
    return pd.DataFrame(rows[1:], columns=columns, dtype=str).fillna(""), []


def validate_file(data: bytes, filename: str) -> dict:
    """Return contract-level errors and row-level quality warnings separately."""
    df, errors = _load(data, filename)
    result = {
        "job_id": stable_job_id(data), "file_name": filename,
        "size_bytes": len(data), "errors": errors,
        "warnings": [], "warning_counts": {}, "rows": 0, "frame": df,
        "schema_valid": not bool(errors),
    }
    if df is None:
        return result

    # Whitespace removal is the only normalization applied by the current AWS core.
    d = df.copy()
    for col in d.columns:
        d[col] = d[col].astype(str).str.strip()
    result["rows"] = len(d)
    issues = Counter()
    for _, row in d.iterrows():
        raw_ts = row["timestamp"]
        if raw_ts:
            try:
                datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                issues["时间戳无法解析"] += 1
        else:
            issues["时间戳缺失"] += 1
        if row["machine_id"] not in MACHINES:
            issues["机器编号不在示例清单内"] += 1
        if row["shift"] not in SHIFTS:
            issues["班次值不在示例清单内"] += 1
        if not re.fullmatch(r"P\d{2,}", row["product_id"]):
            issues["产品编号格式异常"] += 1
        if not re.fullmatch(r"SB-\d+", row["supplier_batch"]):
            issues["供应商批次格式异常"] += 1
        temp = row["temperature"]
        if not temp:
            issues["温度缺失"] += 1
        else:
            try:
                number = float(temp)
                if not math.isfinite(number):
                    issues["温度非有限数字"] += 1
                elif not (TEMP_REVIEW_BAND_C[0] <= number <= TEMP_REVIEW_BAND_C[1]):
                    issues["温度超出演示预警区间（不自动删除）"] += 1
            except ValueError:
                issues["温度不是数字"] += 1
        if row["defect_label"] not in {"0", "1"}:
            issues["缺陷标签无效或缺失"] += 1
    duplicate_rows = int(d.duplicated().sum())
    if duplicate_rows:
        issues["完全重复记录（可安全去重）"] = duplicate_rows
    result["warning_counts"] = dict(issues)
    result["warnings"] = [f"{k}：{v} 行" for k, v in issues.items()]
    return result


def _group_rates(valid: pd.DataFrame, col: str) -> dict:
    if col not in valid.columns or valid.empty:
        return {}
    table = valid.groupby(col, dropna=False)["label_num"].agg(["count", "sum"])
    return {
        str(idx) if str(idx) else "UNKNOWN": {
            "labeled": int(record["count"]),
            "defects": int(record["sum"]),
            "defect_rate": round(float(record["sum"] / record["count"]), 6),
        }
        for idx, record in table.sort_index().iterrows()
    }


def analyze_file(data: bytes, filename: str) -> tuple[dict, pd.DataFrame]:
    check = validate_file(data, filename)
    if check["errors"]:
        raise ValueError("; ".join(check["errors"]))
    df = check["frame"].copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    missing = {col: int((df[col] == "").sum()) for col in df.columns}
    good = df[df["defect_label"].isin(["0", "1"])].copy()
    good["label_num"] = good["defect_label"].astype(int)
    valid_timestamps = pd.to_datetime(good["timestamp"], errors="coerce", utc=True)
    good["production_day"] = valid_timestamps.dt.strftime("%Y-%m-%d").fillna("INVALID_TIME")
    defects = int(good["label_num"].sum()) if len(good) else 0
    report = {
        "job_id": stable_job_id(data), "status": "COMPLETED",
        "processing_version": VERSION, "input_rows": check["rows"],
        "cleaned_rows": int(len(df)), "exact_duplicates_removed": duplicates,
        "invalid_defect_labels_flagged": int(len(df) - len(good)),
        "missing_values_by_column": missing,
        "valid_labeled_rows": int(len(good)), "defects": defects,
        "defect_rate": round(defects / len(good), 6) if len(good) else None,
        "by_machine": _group_rates(good, "machine_id"),
        "by_shift": _group_rates(good, "shift"),
        "by_product": _group_rates(good, "product_id"),
        "by_supplier_batch": _group_rates(good, "supplier_batch"),
        "by_day": _group_rates(good, "production_day"),
        "quality_flags": check["warning_counts"],
        "limitations": [
            "本报告为描述性统计，不代表已经确定质量问题的因果根源。",
            "温度预警区间仅用于演示，需要由工程师按设备设定真实限值。",
            "缺陷率分母是有效缺陷标签的去重记录数。",
        ],
    }
    return report, df
