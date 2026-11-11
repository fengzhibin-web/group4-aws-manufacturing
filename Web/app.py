"""Group 4 Manufacturing Data Quality — Streamlit UI.

Run: streamlit run app.py
Local demo does NOT call AWS. AWS mode requires the separately deployed API.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from aws_client import CloudAPI
from data_contract import (
    MAX_BYTES, OPTIONAL, REQUIRED, SHIFTS, MACHINES, TEMP_REVIEW_BAND_C,
    analyze_file, validate_file,
)

st.set_page_config(page_title="Manufacturing Quality | Group 4", page_icon="🏭", layout="wide")

STATUS = {
    "CREATED": "已创建", "UPLOADED": "已上传", "VALIDATING": "正在校验",
    "AWAITING_EVENT": "已上传，等待S3事件与任务记录", "VALIDATED": "校验通过",
    "INVALID_INPUT": "文件格式无效", "QUEUED": "排队中", "PROCESSING": "处理中",
    "COMPLETED": "处理完成", "COMPLETED_WITH_WARNING": "完成（有警告）", "FAILED": "处理失败",
}


def _cfg(key):
    try:
        return st.secrets.get(key, os.environ.get(key, ""))
    except Exception:
        return os.environ.get(key, "")


def _api():
    return CloudAPI(str(_cfg("AWS_API_BASE_URL")), str(_cfg("DEMO_API_KEY")))


def _rates_chart(by: dict, title: str, line: bool = False) -> None:
    st.markdown(f"**{title}**")
    if not by:
        st.caption("暂无可展示的统计")
        return
    rows = [{"组别": group, "缺陷率（%）": stats["defect_rate"] * 100,
             "有效记录": stats["labeled"], "缺陷记录": stats["defects"]}
            for group, stats in by.items() if stats.get("defect_rate") is not None]
    if not rows:
        st.caption("没有有效缺陷标签")
        return
    chart_df = pd.DataFrame(rows).set_index("组别")
    if line:
        st.line_chart(chart_df["缺陷率（%）"], y_label="缺陷率 %")
    else:
        st.bar_chart(chart_df["缺陷率（%）"], y_label="缺陷率 %")
    st.dataframe(chart_df.reset_index(), hide_index=True, use_container_width=True)


def _show_result(report: dict, cleaned: pd.DataFrame | None, *, origin: str) -> None:
    st.subheader("分析结果")
    st.caption(f"来源：{origin}。缺陷率按去重后、标签为0或1的记录计算；仅用于初步调查，不能直接推断原因。")
    columns = st.columns(5)
    indicators = [
        ("原始记录", report.get("input_rows", "—")),
        ("清洗后记录", report.get("cleaned_rows", "—")),
        ("去掉重复行", report.get("exact_duplicates_removed", "—")),
        ("缺陷记录", report.get("defects", "—")),
        ("总体缺陷率", f"{report['defect_rate'] * 100:.1f}%" if report.get("defect_rate") is not None else "N/A"),
    ]
    for col, (title, value) in zip(columns, indicators):
        col.metric(title, value)
    t1, t2, t3 = st.tabs(["质量对比", "数据质量", "报告与下载"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            _rates_chart(report.get("by_machine", {}), "按机器缺陷率")
            _rates_chart(report.get("by_product", {}), "按产品缺陷率")
        with c2:
            _rates_chart(report.get("by_shift", {}), "按班次缺陷率")
            _rates_chart(report.get("by_supplier_batch", {}), "按供应商批次缺陷率")
        _rates_chart(report.get("by_day", {}), "按日期缺陷率趋势", line=True)
    with t2:
        st.markdown("**各字段缺失数量（清洗后）**")
        st.dataframe(pd.DataFrame([{"字段": k, "缺失行数": v}
                                   for k, v in report.get("missing_values_by_column", {}).items()]),
                     hide_index=True, use_container_width=True)
        st.markdown("**需要人工复核的质量问题**")
        flags = report.get("quality_flags", {})
        if flags:
            st.dataframe(pd.DataFrame([{"质量预警": k, "涉及记录": v} for k, v in flags.items()]),
                         hide_index=True, use_container_width=True)
        else:
            st.info("报告暂无扩展预警字段；现有AWS后端主要输出缺失、重复、标签和按机器缺陷率。")
        if cleaned is not None:
            st.markdown("**清洗结果预览**")
            st.dataframe(cleaned.head(100), hide_index=True, use_container_width=True)
    with t3:
        st.download_button("下载 report.json", json.dumps(report, ensure_ascii=False, indent=2),
                           file_name=f"report_{report.get('job_id', 'local')}.json", mime="application/json")
        if cleaned is not None:
            st.download_button("下载 cleaned.csv", cleaned.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"cleaned_{report.get('job_id', 'local')}.csv", mime="text/csv")
        for note in report.get("limitations", []):
            st.caption("• " + str(note))


st.title("🏭 Manufacturing Data Quality & Investigation")
st.caption("Group 4 · Cloud Computing · S3 → Validation Lambda → SQS → Processing Lambda → DynamoDB")

with st.sidebar:
    st.subheader("运行模式")
    mode = st.radio("选择工作方式", ["本地演示（不连接AWS）", "AWS云端模式"], index=0)
    st.caption("本地模式只在运行Streamlit的电脑/服务端处理数据，不会产生AWS任务。")
    if mode == "AWS云端模式":
        if _cfg("AWS_API_BASE_URL") and _cfg("DEMO_API_KEY"):
            st.success("已检测到API配置（能否连接需实际测试）")
        else:
            st.warning("尚未配置 AWS_API_BASE_URL 和 DEMO_API_KEY")
    st.divider()
    st.markdown("**当前文件规范**")
    st.write("UTF-8 CSV · 7个必需列 · ≤10 MiB · ≤50,000行")
    st.caption("温度只是演示预警；异常记录不会因超出预警区间而自动删除。")

first, second = st.tabs(["上传与处理", "CSV数据规范"])
with second:
    st.subheader("标准数据字典（v1兼容）")
    spec = [
        ("timestamp", "必需", "YYYY-MM-DDTHH:MM:SS", "2026-09-01T08:00:00"),
        ("machine_id", "必需", "M01 / M02 / M03 / M04（示例）", "M03"),
        ("shift", "必需", "Day / Evening / Night（约定值）", "Night"),
        ("product_id", "必需", "P加数字（如P01）", "P02"),
        ("supplier_batch", "必需", "SB-数字（如SB-204）", "SB-204"),
        ("temperature", "必需", "摄氏度数字；空/异常值标记", "91.3"),
        ("defect_label", "必需", "0=合格，1=缺陷；其他值标记", "1"),
        ("batch_id", "可选", "生产批次文本编号", "B2026-001"),
        ("defect_type", "可选", "缺陷类别；合格可留空", "Surface"),
    ]
    st.dataframe(pd.DataFrame(spec, columns=["字段", "属性", "值域/格式", "例子"]),
                 hide_index=True, use_container_width=True)
    st.info("文件级拒绝：缺少必需列、空文件、文件过大、非UTF-8、CSV列数错误或超过50,000行。\n\n行级预警：时间戳异常、缺失值、温度超出示例区间、缺陷标签异常等；不自动删掉可疑生产事件。")
    st.caption("注意：此处为拟冻结的业务规范。云端现有Lambda只实现了其中一部分校验；未同步升级前，不能把本地预警称为AWS已部署能力。")
    st.download_button("下载样例CSV（6行）", (Path(__file__).parent / "data/sample_valid.csv").read_bytes(),
                       file_name="sample_valid.csv", mime="text/csv")
    st.download_button("下载6000行模拟制造业数据", (Path(__file__).parent / "data/manufacturing_6000.csv").read_bytes(),
                       file_name="manufacturing_6000.csv", mime="text/csv")

with first:
    st.subheader("1 · 上传制造业CSV")
    f = st.file_uploader("选择UTF-8 CSV文件", type=["csv"])
    checked = None
    if f is not None:
        raw = f.getvalue()
        checked = validate_file(raw, f.name)
        fingerprint = f"{mode}:{f.name}:{checked['job_id']}"
        if st.session_state.get("_active_file") != fingerprint:
            st.session_state["_active_file"] = fingerprint
            st.session_state.pop("result", None)
            st.session_state.pop("aws_status", None)
            st.session_state.pop("aws_job_id", None)
        st.caption(f"文件：{f.name} · {len(raw):,} bytes · 内容Job ID：`{checked['job_id']}`")
        if checked["errors"]:
            for problem in checked["errors"]:
                st.error(problem)
        else:
            st.success(f"文件结构通过校验：{checked['rows']:,} 行 · 必需列齐全")
            st.dataframe(checked["frame"].head(30), hide_index=True, use_container_width=True)
            if checked["warnings"]:
                with st.expander(f"质量警告（{len(checked['warnings'])}类，文件仍可处理）"):
                    for warning in checked["warnings"]:
                        st.warning(warning)
            else:
                st.caption("本地检查未发现质量警告。")
        col_a, col_b = st.columns([1, 3])
        if mode == "本地演示（不连接AWS）":
            with col_a:
                if st.button("本地执行分析", type="primary", disabled=bool(checked["errors"])):
                    report, df_cleaned = analyze_file(raw, f.name)
                    st.session_state["result"] = (report, df_cleaned, "本地Python分析")
                    st.session_state.pop("aws_job_id", None)
        else:
            allow_invalid = st.checkbox("允许上传无效结构文件（用于测试AWS的INVALID_INPUT）", value=False)
            with col_a:
                if st.button("提交到AWS", type="primary", disabled=bool(checked["errors"]) and not allow_invalid):
                    try:
                        info = _api().upload(f.name, raw)
                        st.session_state["aws_job_id"] = info["job_id"]
                        st.session_state.pop("result", None)
                        st.success("已上传到S3，等待AWS自动处理。")
                    except Exception as exc:
                        st.error(f"AWS上传失败：{exc}")

    if mode == "AWS云端模式":
        st.subheader("2 · AWS任务状态")
        default_job = st.session_state.get("aws_job_id", "")
        job_id = st.text_input("输入或粘贴Job ID", value=default_job, max_chars=64)
        if st.button("刷新任务状态", disabled=not bool(job_id)):
            try:
                result = _api().status(job_id.strip())
                st.session_state["aws_status"] = result
                if result.get("status") in {"COMPLETED", "COMPLETED_WITH_WARNING"}:
                    report_url = result.get("report_url")
                    cleaned_url = result.get("cleaned_url")
                    report = _api().fetch_json(report_url) if report_url else {}
                    clean_bytes = _api().fetch_bytes(cleaned_url) if cleaned_url else None
                    clean_df = pd.read_csv(io.BytesIO(clean_bytes), dtype=str).fillna("") if clean_bytes else None
                    # Optional UI-only extended breakdowns from the cleaned CSV.
                    if clean_bytes:
                        local_report, _ = analyze_file(clean_bytes, f"{job_id}.csv")
                        for key in ("by_shift", "by_product", "by_supplier_batch", "by_day", "quality_flags"):
                            report.setdefault(key, local_report.get(key, {}))
                    st.session_state["result"] = (report, clean_df, "AWS report.json + cleaned.csv（扩展图表由前端计算）")
            except Exception as exc:
                st.error(f"无法读取任务状态：{exc}")
        status = st.session_state.get("aws_status")
        if status and job_id == status.get("job_id"):
            status_value = status.get("status", "UNKNOWN")
            st.info(f"当前状态：**{STATUS.get(status_value, status_value)}**（{status_value}）")
            if status_value == "INVALID_INPUT":
                st.error("AWS认为这是无效文件，未提交Processing Lambda。")
                if status.get("validation_url"):
                    try:
                        st.json(_api().fetch_json(status["validation_url"]))
                    except Exception as exc:
                        st.caption(f"验证详情尚不可访问：{exc}")
            if status_value == "FAILED":
                st.warning("任务已被标记为FAILED；请在AWS CloudWatch/DLQ查看原始错误日志。")

    if "result" in st.session_state:
        report, cleaned, origin = st.session_state["result"]
        _show_result(report, cleaned, origin=origin)
    else:
        st.caption("选择数据并执行分析后，这里将显示质量指标、机器/班次/批次对比及下载按钮。")
