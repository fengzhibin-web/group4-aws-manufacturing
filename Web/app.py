"""Manufacturing Quality Intelligence · bilingual light UI.

Streamlit Cloud entrypoint: Web/app.py
Requires existing aws_client.py, data_contract.py and Web/data/ files.
Never put AWS Academy credentials or DEMO_API_KEY in source control.

Status timeline in AWS mode is a coarse, illustrative milestone display;
AWS does not currently expose independently measured per-stage percentages.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from aws_client import CloudAPI, CloudAPIError
from data_contract import MAX_BYTES, MAX_ROWS, REQUIRED, OPTIONAL, validate_file, analyze_file

st.set_page_config(
    page_title="Manufacturing Quality Intelligence | Group 4",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = r"""
<style>
:root{--mq-blue:#287dda;--mq-green:#18a786;--mq-navy:#183c65;--mq-muted:#7189a2;--mq-border:#dbe8f6}
.stApp {background:radial-gradient(circle at 12% 0%,#e7f3ff 0,transparent 37%),linear-gradient(180deg,#f6fbff,#f4f8fd 65%,#f8fbff)!important;color:#1b3752!important}
section[data-testid="stSidebar"]{display:none!important}
header[data-testid="stHeader"]{background:rgba(246,250,254,.96)!important;box-shadow:none!important;border-bottom:0!important}
[data-testid="stToolbar"]{background:transparent!important}
[data-testid="stDecoration"]{display:none!important}
.block-container{max-width:1420px!important;padding:1.35rem 2.2rem 4rem!important}
#MainMenu,footer[data-testid="stFooter"]{visibility:hidden}
.mq-brand{display:flex;align-items:center;gap:13px;padding:4px 0 17px;border-bottom:1px solid #e1eaf5}
.mq-mark{height:44px;width:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#579afa,#47cba4);color:#fff;font-weight:900;box-shadow:0 8px 19px rgba(49,125,203,.14)}
.mq-brand-eyebrow,.mq-eyebrow{color:#357cc3;text-transform:uppercase;letter-spacing:.14em;font-size:10px;font-weight:800}
.mq-brand-title{font-weight:850;font-size:17px;color:#1e3f62}
.mq-region{margin-left:auto;border:1px solid #d7e6f5;background:#fff;border-radius:999px;padding:8px 13px;font-size:11px;color:#66839f}
.mq-hero{padding:24px 0 15px}.mq-hero h1{font-size:clamp(28px,3vw,41px)!important;letter-spacing:-.04em!important;line-height:1.16!important;color:#1c436a!important;margin:6px 0!important;font-weight:850!important}
.mq-hero p{color:#6a849f;font-size:13px;max-width:760px;line-height:1.65;margin:7px 0 0}
.mq-p-head{padding:0 0 5px}.mq-p-head h3{font-size:18px;margin:0;color:#1f466d;font-weight:800}.mq-p-head p{margin:3px 0 0;color:#8295a8;font-size:12px}
[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(170deg,#fff,#fbfdff)!important;border:1px solid #dce9f6!important;border-radius:18px!important;box-shadow:0 9px 32px rgba(43,101,157,.065)!important}
[data-testid="stFileUploader"]{border:1.5px dashed #a5caee!important;border-radius:15px!important;background:linear-gradient(140deg,#f4faff,#eef7ff)!important;padding:12px!important}
[data-testid="stFileUploaderDropzone"]{border:0!important;background:transparent!important}
[data-testid="stFileUploaderDropzoneInstructions"]{color:#557a9f!important}
.stButton>button[kind="primary"]{background:linear-gradient(120deg,#468de8,#2e77d2)!important;color:#fff!important;border:0!important;box-shadow:0 7px 18px rgba(52,123,212,.19)}
.stButton>button,.stDownloadButton>button{border-radius:10px!important;font-weight:720!important;border:1px solid #d0e2f3!important;transition:transform .18s ease, box-shadow .18s ease!important}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(65,128,191,.14)}
[data-testid="stRadio"] [role="radiogroup"]{gap:9px}
[data-testid="stRadio"] label{color:#315b83!important}
[data-testid="stAlert"]{border-radius:11px!important}
[data-testid="stTabs"] button[aria-selected="true"]{color:#287bd4!important;border-bottom-color:#287bd4!important}
[data-testid="stDataFrame"]{border:1px solid #e1eaf5;border-radius:10px}
.mq-pill{display:inline-block;border:1px solid #cee0f2;color:#3676b4;border-radius:8px;padding:4px 9px;background:#f0f7ff;font-size:10px;font-weight:700}
.mq-inline-meta{display:flex;gap:9px;flex-wrap:wrap;padding:9px 0 2px}.mq-inline-meta span{background:#f1f7fd;color:#55738f;border-radius:8px;padding:7px 9px;font-size:11px}
.mq-disclaimer{border:1px solid #d8e9f7;background:#f3f9ff;color:#507495;font-size:11px;padding:12px 14px;border-radius:12px;line-height:1.6}
.mq-pipeline-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.mq-percent{font-size:29px;font-weight:850;color:#265c97;font-variant-numeric:tabular-nums}
.mq-track{height:10px;background:#e3eef9;border-radius:99px;overflow:hidden;margin:11px 0}.mq-fill{height:100%;background:linear-gradient(90deg,#327dd7,#58aeed,#33bea4);border-radius:99px;animation:mq-grow 1s cubic-bezier(.2,.7,.2,1) both}
@keyframes mq-grow{from{width:0}to{width:var(--target)}}
.mq-stage{display:flex;gap:13px;align-items:flex-start;border-bottom:1px solid #eef3f8;padding:9px 1px}.mq-stage:last-child{border:0}
.mq-dot{width:27px;height:27px;flex:0 0 27px;border-radius:9px;display:grid;place-items:center;background:#edf3f9;border:1px solid #d7e3f0;color:#8ba1b8;font-size:11px;font-weight:850}
.mq-dot.error{background:#ffe9eb;color:#be2b42;border-color:#ffc0cb}.mq-stage.error .mq-step-title{color:#be2b42}
.mq-dot.done{background:#e2f8ef;color:#078d67;border-color:#a4e2cf}.mq-dot.active{background:#e2f0ff;color:#2375d3;border-color:#a9d2fd;animation:mq-pulse 1.7s infinite}
@keyframes mq-pulse{50%{box-shadow:0 0 0 6px rgba(49,128,224,.09)}}
.mq-step-title{color:#315b7e;font-size:12px;font-weight:750}.mq-step-sub{font-size:10px;color:#839db2;margin-top:2px}.mq-stage-name{margin-left:auto;font-size:10px;color:#91a8ba}
.mq-log{background:#f5f9ff;border:1px solid #e3edf9;border-radius:12px;padding:9px 12px;font-size:11px;color:#627f9e;max-height:150px;overflow:auto;margin-top:10px}
.mq-log div{padding:3px 0;border-bottom:1px solid #edf2f9}.mq-log div:last-child{border:0}
.mq-section-title{font-size:24px;color:#1c446b;font-weight:850;margin:20px 0 5px}.mq-footer{color:#879caf;font-size:11px;border-top:1px solid #e0ebf4;margin-top:26px;padding-top:13px}
@media(max-width:800px){.block-container{padding:1rem .85rem 3rem!important}.mq-hero h1{font-size:27px!important}.mq-region{font-size:9px}.mq-brand-title{font-size:13px}.mq-stage-name{display:none}}
</style>
"""

LANG = {
"en": {
    "hero":"Track every processing stage.", "hero2":"Turn manufacturing data into quality insights.",
    "subtitle":"Upload production data, follow each job, and explore manufacturing-quality insights.",
    "data":"01 / Upload dataset", "data_sub":"Upload UTF-8 CSV or choose the included sample dataset.",
    "choose":"Drag and drop your CSV here", "sample":"Load sample CSV", "reset":"Reset", "run_local":"Run local analysis", "run_aws":"Upload to AWS", "file":"Dataset", "not_selected":"No file selected", "mode":"Execution mode",
    "local":"Local demo · No AWS", "aws":"AWS cloud mode", "mode_help_local":"Local analysis runs on the Streamlit host; it does not call AWS.", "mode_help_aws":"AWS mode uses a presigned S3 upload and the existing API Gateway endpoints.",
    "rules":"7 required fields · Max 10 MiB · Up to 50,000 rows (UI)","ready":"Structure validated", "invalid":"Input validation failed", "warnings":"Review warnings", "file_preview":"CSV preview",
    "pipeline":"02 / Processing pipeline", "pipeline_sub":"Job activity and processing status","job":"Job ID", "pending":"Awaiting submission", "progress":"Job progress","complete":"Completed", "failed":"Failed", "in_progress":"In progress", "waiting":"Waiting", "events":"Task activity",
    "demo_info":"In local mode, progress summarizes local processing milestones. AWS mode maps known job statuses to approximate steps; the current backend does not expose precise per-stage percentages or timings.",
    "results":"Quality insights & visualizations", "results_sub":"Animated results are calculated from the processed dataset. Associations are not proof of root cause.",
    "quality":"Data quality", "downloads":"Reports & downloads", "charts":"Analytics", "stats":"Overview", "missing":"Missing values by column", "issues":"Review flags", "preview_clean":"Cleaned data preview", "source":"Analysis source", "raw":"Input rows", "clean":"Cleaned rows", "duplicate":"Duplicates removed", "defects":"Defective rows", "rate":"Defect rate", "nothing":"Run an analysis to see animated KPIs, defect comparisons and downloads.",
    "report_download":"Download report.json", "csv_download":"Download cleaned.csv", "download_sample":"Download 6-row sample", "download_6000":"Download 6,000-row dataset", "data_dictionary":"CSV data dictionary", "required":"Required", "optional":"Optional", "column":"Column", "format":"Format / example", "kind":"Requirement", "docs":"Schema & samples", "notice":"Cloud-side validation currently implements a subset of the local UI checks.",
    "lookup":"Job status lookup", "refresh":"Refresh job status", "enter_job":"Enter job ID", "aws_missing":"AWS_API_BASE_URL or DEMO_API_KEY is missing from Streamlit Secrets.", "aws_ready":"API configuration detected; availability is not yet verified.", "aws_uploaded":"File uploaded. Tracking AWS automatically.","aws_invalid_option":"Allow invalid CSV upload (test INVALID_INPUT)","aws_fetch_error":"Could not retrieve job status", "aws_upload_error":"AWS upload failed", "job_failed":"The job is FAILED; inspect the AWS logs and DLQ.","job_invalid":"AWS rejected the input schema.", "status":"Current status", "origin_local":"Local Python analysis", "origin_aws":"AWS report.json and cleaned.csv (additional breakdowns calculated by the UI)",
    "region":"AWS · us-east-1", "footer":"Group 4 · Manufacturing Quality Intelligence · Academic demonstration", "no_valid":"No valid labeled records", "no_data":"No statistics available", "stages_done":"All seven stages completed", "stage_unknown":"Exact per-stage progress is not provided by AWS.", "file_bigger":"File exceeds the allowed size.", "file_error":"Upload a CSV with the seven required columns.",
    "machine":"Defect rate by machine", "shift":"Defect rate by shift", "product":"Defect rate by product", "supplier":"Defect rate by supplier batch", "day":"Daily defect-rate trend", "donut":"Overall defect distribution", "valid_label":"Valid labeled rows", "by_stage":"Stage", "web_warning":"Public access is enabled. Anyone who can open this site may submit cloud jobs; set usage controls before production use.",
    "types":"UTF-8 · CSV · Maximum 10 MiB", "clean_preview":"Preview of cleaned records", "warnings_none":"No quality warnings detected by local checks.",
    "status_CREATED":"Created", "status_UPLOADED":"Uploaded", "status_VALIDATING":"Validating", "status_AWAITING_EVENT":"Waiting for S3 event", "status_QUEUED":"Queued", "status_PROCESSING":"Processing", "status_COMPLETED":"Completed", "status_COMPLETED_WITH_WARNING":"Completed with warning", "status_INVALID_INPUT":"Invalid input", "status_FAILED":"Failed"
},
"zh": {
    "hero":"每一步处理，都清晰可见。", "hero2":"让制造数据变成质量洞察。", "subtitle":"上传生产CSV，实时查看任务状态和制造业质量分析结果。",
    "data":"01 / 上传生产数据", "data_sub":"上传 UTF-8 CSV，或使用示例数据体验流程。", "choose":"拖拽 CSV 文件至此", "sample":"加载示例CSV", "reset":"重置", "run_local":"运行本地分析", "run_aws":"上传至AWS", "file":"数据文件", "not_selected":"未选择文件", "mode":"运行模式",
    "local":"本地演示 · 不连接AWS", "aws":"AWS云端模式", "mode_help_local":"本地模式在Streamlit服务器执行分析，不会调用AWS。", "mode_help_aws":"AWS模式使用预签名S3上传和已有的API Gateway接口。",
    "rules":"7个必需列 · 最大10 MiB · 最多50,000行（前端）", "ready":"结构校验通过", "invalid":"输入校验失败", "warnings":"质量提示", "file_preview":"CSV预览",
    "pipeline":"02 / 数据处理流程", "pipeline_sub":"任务动态与处理状态", "job":"任务ID", "pending":"等待提交", "progress":"任务进度", "complete":"处理完成", "failed":"处理失败", "in_progress":"处理中", "waiting":"等待中", "events":"任务动态",
    "demo_info":"本地模式展示本地处理阶段。AWS 模式根据可用任务状态推断大致进度；目前后端不提供每一阶段的精确百分比或耗时。",
    "results":"质量洞察与可视化", "results_sub":"根据当前数据计算指标并播放图表动画；统计相关性不代表因果关系。",
    "quality":"数据质量", "downloads":"报告与下载", "charts":"图表分析", "stats":"统计概览", "missing":"各字段缺失数量", "issues":"质量预警", "preview_clean":"清洗结果预览", "source":"分析来源", "raw":"原始记录", "clean":"清洗后记录", "duplicate":"去除重复行", "defects":"缺陷记录", "rate":"总体缺陷率", "nothing":"执行分析后，这里会展示动态指标、缺陷率对比和报告下载。",
    "report_download":"下载 report.json", "csv_download":"下载 cleaned.csv", "download_sample":"下载6行示例CSV", "download_6000":"下载6000行制造业CSV", "data_dictionary":"CSV字段字典", "required":"必需", "optional":"可选", "column":"字段", "format":"格式/示例", "kind":"属性", "docs":"数据规范与样例", "notice":"当前AWS后端校验范围比前端的本地检查少。",
    "lookup":"任务状态查询", "refresh":"刷新任务状态", "enter_job":"输入Job ID", "aws_missing":"Streamlit Secrets缺少 AWS_API_BASE_URL 或 DEMO_API_KEY。", "aws_ready":"检测到API配置，但尚未验证实际连接。", "aws_uploaded":"上传成功，正在自动跟踪AWS任务。", "aws_invalid_option":"允许上传无效结构CSV（测试INVALID_INPUT）", "aws_fetch_error":"无法读取任务状态", "aws_upload_error":"AWS上传失败", "job_failed":"任务处于FAILED状态，请查看CloudWatch和DLQ。", "job_invalid":"AWS判定输入结构无效。", "status":"当前状态", "origin_local":"本地Python分析", "origin_aws":"AWS report.json + cleaned.csv（附加分组指标由前端计算）",
    "region":"AWS · us-east-1", "footer":"Group 4 · 制造业质量智能分析 · 课程演示项目", "no_valid":"没有有效缺陷标签", "no_data":"暂无统计数据", "stages_done":"7个阶段已完成", "stage_unknown":"AWS尚不提供每个阶段的精确进度。", "file_bigger":"文件超过大小限制。", "file_error":"请上传包含7个必需字段的CSV。",
    "machine":"按机器缺陷率", "shift":"按班次缺陷率", "product":"按产品缺陷率", "supplier":"按供应商批次缺陷率", "day":"每日缺陷率趋势", "donut":"总体质量分布", "valid_label":"有效标签记录", "by_stage":"阶段", "web_warning":"当前网站允许公开访问。其他访客可能通过网页发起AWS任务；正式部署前应增加访问控制或限流。",
    "types":"UTF-8 · CSV · 最大10 MiB", "clean_preview":"清洗记录预览", "warnings_none":"本地检查未发现质量预警。",
    "status_CREATED":"已创建", "status_UPLOADED":"已上传", "status_VALIDATING":"校验中", "status_AWAITING_EVENT":"等待S3事件", "status_QUEUED":"排队中", "status_PROCESSING":"处理中", "status_COMPLETED":"已完成", "status_COMPLETED_WITH_WARNING":"完成但有警告", "status_INVALID_INPUT":"输入无效", "status_FAILED":"失败"
}}

STAGES = {
"en":[
("Secure S3 upload", "Presigned URL uploads raw CSV to S3"),
("Validation Lambda", "CSV schema and required-field checks"),
("SHA-256 & deduplication", "Content-based idempotent job ID"),
("Amazon SQS queue", "Asynchronous queue and retries"),
("Processing Lambda", "Deterministic cleaning and exact deduplication"),
("Quality metrics", "Defect rates and missing-value statistics"),
("S3 report + DynamoDB", "Save outputs and mark job COMPLETED"),
],
"zh":[
("安全上传 S3", "使用预签名URL上传原始CSV"),
("Validation Lambda校验", "CSV结构及必需列检查"),
("SHA-256内容去重", "基于内容的幂等Job ID"),
("Amazon SQS任务入队", "异步排队和失败重试"),
("Processing Lambda清洗", "确定性清洗、完全重复行去重"),
("质量指标统计", "缺陷率、缺失值与分组分析"),
("S3报告 + DynamoDB", "保存输出并更新COMPLETED状态"),
]}

LOCAL_STAGES = {
"en":[
("File loaded locally", "Read CSV on the Streamlit server; no S3 upload"),
("Local schema validation", "UTF-8 and required columns checked locally"),
("SHA-256 job fingerprint", "Same bytes map to the same v1 ID"),
("Local preparation", "Prepare validated records for local processing"),
("Local Python cleaning", "Trim whitespace and remove exact duplicates"),
("Local quality analytics", "Compute deterministic defect rates"),
("Local report ready", "Downloads generated on the Streamlit server"),
],
"zh":[
("本地文件已读取", "Streamlit服务器读取文件，不上传S3"),
("本地结构校验", "在前端服务中检查UTF-8和7项必需列"),
("SHA-256任务指纹", "相同字节得到相同v1 Job ID"),
("本地预处理准备", "将校验后的记录准备进行本地清洗"),
("本地Python数据清洗", "去空格、去完全重复行"),
("本地质量分析", "计算确定性缺陷率指标"),
("本地报告已生成", "下载文件由Streamlit服务器生成"),
]}

WARNING_TRANSLATIONS = {
"时间戳无法解析":"Unparseable timestamp", "时间戳缺失":"Missing timestamp",
"机器编号不在示例清单内":"Machine ID outside demo set", "班次值不在示例清单内":"Shift outside demo set",
"产品编号格式异常":"Unusual product ID format", "供应商批次格式异常":"Unusual supplier batch format",
"温度缺失":"Missing temperature", "温度非有限数字":"Non-finite temperature", "温度超出演示预警区间（不自动删除）":"Temperature outside demo review band (not deleted)",
"温度不是数字":"Non-numeric temperature", "缺陷标签无效或缺失":"Missing / invalid defect label", "完全重复记录（可安全去重）":"Exact duplicate records (safe to remove)",
"缺少必需列":"Missing required columns", "文件为空":"Empty file", "文件大于 10 MiB 限制":"File exceeds 10 MiB", "CSV结构解析失败":"CSV parsing failed", "数据行超过":"Too many rows",
}


def label(key: str) -> str:
    return LANG[st.session_state.get("ui_lang", "en")].get(key, key)


def _cfg(key: str):
    try:
        return st.secrets.get(key, os.environ.get(key, ""))
    except Exception:
        return os.environ.get(key, "")


def _api() -> CloudAPI:
    return CloudAPI(str(_cfg("AWS_API_BASE_URL")), str(_cfg("DEMO_API_KEY")))


def _event(message: str):
    utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    st.session_state.setdefault("ui_events", []).append(f"{utc} · {message}")
    st.session_state["ui_events"] = st.session_state["ui_events"][-14:]

def _localized_event(event: str) -> str:
    zh=st.session_state.get("ui_lang")=="zh"
    if any(x in event for x in ("SAMPLE_SELECTED","Sample CSV selected","已选择示例CSV")):
        return event.split(" · ")[0]+" · "+("已选择示例CSV" if zh else "Sample CSV selected")
    if "Existing SHA-256 job reused" in event:
        return event.replace("Existing SHA-256 job reused","复用已有SHA-256任务" if zh else "Existing SHA-256 job reused")
    if "S3 raw/ upload accepted" in event:
        return event.replace("S3 raw/ upload accepted","S3上传成功" if zh else "S3 raw/ upload accepted")
    if "Local validation, cleaning and analysis completed" in event:
        return event.replace("Local validation, cleaning and analysis completed","本地校验、清洗与分析已完成" if zh else "Local validation, cleaning and analysis completed")
    return event


def _status_milestone(is_aws: bool, has_file: bool, valid: bool, has_result: bool, code: str):
    """Coarse UI milestones only. Not measured stage progress or latency."""
    if not is_aws:
        if has_result:
            return 7, 100, "COMPLETED"
        if has_file and not valid:
            return 2, 28, "INVALID_INPUT"
        return (1, 14, "FILE_READY") if has_file else (0, 0, "WAITING")
    table = {"AWAITING_EVENT":(2,25), "CREATED":(2,25), "UPLOADED":(2,25),
             "VALIDATING":(2,27), "VALIDATED":(3,41), "QUEUED":(4,56),
             "PROCESSING":(5,73), "COMPLETED":(7,100), "COMPLETED_WITH_WARNING":(7,100),
             "INVALID_INPUT":(2,27), "FAILED":(5,73), "AWS_UPLOAD_FAILED":(1,0)}
    if code in table:
        count,pct=table[code];return count,pct,code
    return (0,0,"WAITING") if is_aws else ((1,14,"FILE_READY") if has_file else (0,0,"WAITING"))


def _pipeline(is_aws:bool, has_file:bool, valid:bool, has_result:bool, code:str, job_id:str):
    count,pct,state=_status_milestone(is_aws,has_file,valid,has_result,code)
    status_txt=label(f"status_{state}") if state in {"CREATED","UPLOADED","VALIDATING","AWAITING_EVENT","QUEUED","PROCESSING","COMPLETED","COMPLETED_WITH_WARNING","INVALID_INPUT","FAILED","AWS_UPLOAD_FAILED"} else (label("ready") if state=="FILE_READY" else label("waiting"))
    pieces=[f'<div class="mq-pipeline-top"><div><div class="mq-eyebrow">{html.escape(label("progress"))}</div><div style="color:#7795ae;font-size:11px;margin-top:4px">{html.escape(status_txt)}</div></div><div class="mq-percent">{pct}%</div></div>',
            f'<div class="mq-track"><div class="mq-fill" style="--target:{pct}%"></div></div>',
            f'<div style="font-size:10px;color:#88a0b6;overflow-wrap:anywhere">{html.escape(label("job"))}: {html.escape(job_id or "—")} · v1</div>']
    for i,(title,desc) in enumerate((STAGES if is_aws else LOCAL_STAGES)[st.session_state.get("ui_lang","en")]):
        if state == "AWS_UPLOAD_FAILED" and i == 0:
            dot_class="error";mark="!"
        elif state in {"FAILED","INVALID_INPUT"} and i==count-1:
            dot_class="error";mark="!"
        elif i<count and state in {"COMPLETED","COMPLETED_WITH_WARNING"}:
            dot_class="done";mark="✓"
        elif i<count-1:
            dot_class="done";mark="✓"
        elif i==count-1:
            dot_class="active";mark=str(i+1)
        else:
            dot_class="";mark=str(i+1)
        suffix=label("failed") if dot_class=="error" else label("complete") if dot_class=="done" else label("in_progress") if dot_class=="active" else label("waiting")
        pieces.append(f'<div class="mq-stage {dot_class}"><div class="mq-dot {dot_class}">{mark}</div><div><div class="mq-step-title">{html.escape(title)}</div><div class="mq-step-sub">{html.escape(desc)}</div></div><div class="mq-stage-name">{html.escape(suffix)}</div></div>')
    return "".join(pieces)


def _translate_warnings(warnings:list[str]):
    if st.session_state.get("ui_lang","en")=="zh":
        return warnings
    translated=[]
    for line in warnings:
        for z,en in WARNING_TRANSLATIONS.items():
            line=line.replace(z,en)
        line=line.replace(" 行"," rows").replace("：", ": ")
        translated.append(line)
    return translated


def _load_result_from_aws(job_id:str,result:dict):
    if result.get("status") not in ("COMPLETED","COMPLETED_WITH_WARNING"):
        return
    api=_api()
    report_url=result.get("report_url")
    cleaned_url=result.get("cleaned_url")
    report=api.fetch_json(report_url) if report_url else {}
    clean_bytes=api.fetch_bytes(cleaned_url) if cleaned_url else None
    cleaned=pd.read_csv(io.BytesIO(clean_bytes),dtype=str).fillna("") if clean_bytes else None
    if clean_bytes:
        derived,_=analyze_file(clean_bytes, f"{job_id}.csv")
        for name in ("by_shift","by_product","by_supplier_batch","by_day","quality_flags"):
            report.setdefault(name,derived.get(name,{}))
    st.session_state["result_aws"]=(report, cleaned, "aws")


# The HTML/SVG analytics lives in an isolated Streamlit component. All data is
# passed from Python server to the client; credentials are never sent to it.
ANALYTICS_HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;color:#244865;background:transparent}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.kpi{background:#fff;border:1px solid #dfeaf5;border-radius:15px;padding:16px;box-shadow:0 8px 24px rgba(52,102,148,.05);animation:appear .55s both}.kpi .lbl{font-size:11px;font-weight:700;color:#839ab0}.kpi .num{font-size:27px;font-weight:850;color:#275784;margin-top:7px;font-variant-numeric:tabular-nums}.kpi .sub{font-size:10px;color:#94a8bc;margin-top:5px}
.panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.panel{background:#fff;border:1px solid #dfebf5;border-radius:15px;padding:17px;min-height:218px;box-shadow:0 8px 24px rgba(52,102,148,.045);animation:appear .65s both}.panel h3{font-size:14px;margin:0 0 4px;color:#285276}.sub{font-size:10px;color:#8ba1b6;margin-bottom:16px}.donutwrap{display:flex;align-items:center;justify-content:space-around;gap:15px;margin-top:2px}.donut{width:158px;height:158px;transform:rotate(-90deg)}.circle-bg{fill:none;stroke:#e7f1fa;stroke-width:12}.circle-val{fill:none;stroke:#2cb58e;stroke-width:12;stroke-linecap:round;stroke-dasharray:289;stroke-dashoffset:289;transition:stroke-dashoffset 1.5s cubic-bezier(.2,.75,.2,1)}.donuttext{font-size:30px;font-weight:850;color:#2b5879}.legend{color:#69839d;font-size:12px;line-height:2}.legend b{color:#2d5576}
.barrow{display:grid;grid-template-columns:64px minmax(0,1fr) 50px;gap:9px;align-items:center;margin:12px 0;font-size:11px;color:#587997}.barbg{background:#eaf2fa;height:10px;border-radius:99px;overflow:hidden}.barfill{height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,#3990e4,#83beff);transition:width 1.3s cubic-bezier(.16,.75,.22,1)}.barfill.alert{background:linear-gradient(90deg,#ecac61,#f5d191)}.barpct{text-align:right;color:#426787;font-weight:650}
.trend{width:100%;height:auto}.gridline{stroke:#e3edf7;stroke-width:1}.trendline{fill:none;stroke:#428ce3;stroke-width:3;stroke-linejoin:round;stroke-linecap:round}.trendarea{fill:#e4f2ff}.plotpoint{fill:#3f8df0;stroke:#fff;stroke-width:2}.axis{fill:#819cb5;font-size:10px}
@keyframes appear{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:650px){.kpis{grid-template-columns:repeat(2,1fr)}.panels{grid-template-columns:1fr}.panel{min-height:220px}}
</style></head><body>
<div class="kpis" id="kpis"></div>
<div class="panels">
<div class="panel"><h3 id="donutTitle"></h3><div class="sub" id="donutSub"></div><div class="donutwrap"><div style="position:relative"><svg class="donut" viewBox="0 0 120 120"><circle class="circle-bg" cx="60" cy="60" r="46"/><circle class="circle-val" id="arc" cx="60" cy="60" r="46"/></svg><div style="position:absolute;top:60px;left:0;width:158px;text-align:center" class="donuttext" id="donutText"></div></div><div class="legend" id="legend"></div></div></div>
<div class="panel"><h3 id="machineTitle"></h3><div class="sub">Machine · %</div><div id="machines"></div></div>
<div class="panel"><h3 id="shiftTitle"></h3><div class="sub">Shift · %</div><div id="shifts"></div></div>
<div class="panel"><h3 id="trendTitle"></h3><div class="sub">Daily · %</div><div id="trend"></div></div>
</div>
<script>
const report=__REPORT_DATA__;const L=__TEXT_DATA__;const $=id=>document.getElementById(id);
const fmt=(x)=>Number(x||0).toLocaleString('en-US');
function counter(el,val,suffix=''){let t0;function tick(t){if(!t0)t0=t;let p=Math.min(1,(t-t0)/1100),e=1-(1-p)**3;el.textContent=suffix==='%'?(val*e).toFixed(1)+'%':fmt(Math.round(val*e));if(p<1)requestAnimationFrame(tick)}requestAnimationFrame(tick)}
function addKpi(lab,val,sub,suffix=''){let c=document.createElement('div');c.className='kpi';let a=document.createElement('div');a.className='lbl';a.textContent=lab;let n=document.createElement('div');n.className='num';let x=document.createElement('div');x.className='sub';x.textContent=sub;c.append(a,n,x);$('kpis').appendChild(c);if(val==null)n.textContent='N/A';else counter(n,val,suffix)}
addKpi(L.raw,report.input_rows||0,L.stats);addKpi(L.clean,report.cleaned_rows||0,L.duplicate+': '+(report.exact_duplicates_removed||0));addKpi(L.defects,report.defects||0,L.valid_label+': '+(report.valid_labeled_rows||0));addKpi(L.rate,report.defect_rate==null?null:report.defect_rate*100,L.donut,'%');
$('donutTitle').textContent=L.donut;$('donutSub').textContent=L.valid_label;$('machineTitle').textContent=L.machine;$('shiftTitle').textContent=L.shift;$('trendTitle').textContent=L.day;
const rate=report.defect_rate||0;setTimeout(()=>$('arc').style.strokeDashoffset=String(289*(1-rate)),70);if(report.defect_rate==null)$('donutText').textContent='N/A';else counter($('donutText'),rate*100,'%');$('legend').textContent=`${L.valid_label}: ${fmt(report.valid_labeled_rows)} · ${L.defects}: ${fmt(report.defects)}`;
function bars(id,obj){let d=$(id),entries=Object.entries(obj||{}).filter(([,x])=>x&&x.defect_rate!=null).slice(0,6);if(!entries.length){d.textContent=L.no_data;return;}for(let [name,v] of entries){let row=document.createElement('div');row.className='barrow';let lab=document.createElement('div');lab.textContent=name;let bg=document.createElement('div');bg.className='barbg';let fill=document.createElement('div');fill.className='barfill'+(v.defect_rate>=.25?' alert':'');bg.appendChild(fill);let pct=document.createElement('div');pct.className='barpct';pct.textContent=(v.defect_rate*100).toFixed(1)+'%';row.append(lab,bg,pct);d.appendChild(row);requestAnimationFrame(()=>requestAnimationFrame(()=>{fill.style.width=(v.defect_rate*100)+'%'}));}}
bars('machines',report.by_machine);bars('shifts',report.by_shift);
function trend(obj){let entries=Object.entries(obj||{}).filter(([,x])=>x&&x.defect_rate!=null).sort((a,b)=>a[0].localeCompare(b[0])).slice(-12);let box=$('trend');if(!entries.length){box.textContent=L.no_data;return}const w=515,h=196,pad=28,max=Math.max(.2,...entries.map(x=>x[1].defect_rate*1.2));let coords=entries.map((x,i)=>[pad+i*(w-pad*2)/Math.max(1,entries.length-1),h-pad-(h-2*pad)*x[1].defect_rate/max]);let svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.classList.add('trend');for(let i=0;i<4;i++){let y=pad+i*(h-2*pad)/3;let line=document.createElementNS(svg.namespaceURI,'line');line.setAttribute('x1',pad);line.setAttribute('x2',w-pad);line.setAttribute('y1',y);line.setAttribute('y2',y);line.setAttribute('class','gridline');svg.appendChild(line)}let d=coords.map((c,i)=>(i?'L':'M')+c[0].toFixed(1)+' '+c[1].toFixed(1)).join(' ');let area=document.createElementNS(svg.namespaceURI,'path');area.setAttribute('d',d+` L ${coords.at(-1)[0]} ${h-pad} L ${coords[0][0]} ${h-pad} Z`);area.setAttribute('class','trendarea');svg.appendChild(area);let line=document.createElementNS(svg.namespaceURI,'path');line.setAttribute('d',d);line.setAttribute('class','trendline');svg.appendChild(line);coords.forEach(c=>{let dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',c[0]);dot.setAttribute('cy',c[1]);dot.setAttribute('r',4);dot.setAttribute('class','plotpoint');svg.appendChild(dot)});box.appendChild(svg);let len=line.getTotalLength();line.style.strokeDasharray=String(len);line.style.strokeDashoffset=String(len);requestAnimationFrame(()=>requestAnimationFrame(()=>{line.style.transition='stroke-dashoffset 1.8s ease';line.style.strokeDashoffset=0}));}
trend(report.by_day);
</script></body></html>
"""


def _render_analytics(report:dict):
    # Prevent closing the script tag through untrusted dataset values.
    safe_report=json.dumps(report,ensure_ascii=False,default=str).replace('<','\\u003c').replace('>','\\u003e')
    safe_text=json.dumps({k:label(k) for k in ["raw","clean","duplicate","defects","rate","donut","machine","shift","day","stats","valid_label","no_data"]},ensure_ascii=False)
    page=ANALYTICS_HTML.replace("__REPORT_DATA__",safe_report).replace("__TEXT_DATA__",safe_text)
    components.html(page,height=620,scrolling=True)


# -- UI --
if "ui_lang" not in st.session_state:
    st.session_state["ui_lang"] = "en"
# Restore the non-secret job ID from the URL on a full browser refresh.
url_job = str(st.query_params.get("job", "")).lower()
if re.fullmatch(r"[0-9a-f]{16}", url_job) and not st.session_state.get("aws_job_id"):
    st.session_state["aws_job_id"] = url_job
    st.session_state["aws_polling"] = True
if "execution_mode" not in st.session_state:
    st.session_state["execution_mode"] = "aws" if (st.session_state.get("aws_job_id") or (_cfg("AWS_API_BASE_URL") and _cfg("DEMO_API_KEY"))) else "local"
if "job_id_input" not in st.session_state:
    st.session_state["job_id_input"] = st.session_state.get("aws_job_id", "")
st.markdown(CSS,unsafe_allow_html=True)
head,choice=st.columns([5,1],vertical_alignment="center")
with head:
    st.markdown('<div class="mq-brand"><span class="mq-mark">MQ</span><span><div class="mq-brand-eyebrow">GROUP 4 · CLOUD COMPUTING</div><div class="mq-brand-title">Manufacturing Quality Intelligence</div></span><span class="mq-region">AWS · us-east-1</span></div>',unsafe_allow_html=True)
with choice:
    st.radio("Language / 语言",options=["en","zh"],format_func=lambda x:"English" if x=="en" else "中文",horizontal=True,label_visibility="collapsed",key="ui_lang")

st.markdown(f'<section class="mq-hero"><div class="mq-eyebrow">EVENT-DRIVEN DATA QUALITY PLATFORM</div><h1>{html.escape(label("hero"))}<br><span style="color:#3185d5">{html.escape(label("hero2"))}</span></h1><p>{html.escape(label("subtitle"))}</p></section>',unsafe_allow_html=True)

mode=st.radio(
    label("mode"), options=["local","aws"],
    index=["local","aws"].index(st.session_state.get("execution_mode","local")),
    format_func=lambda x:label(x), horizontal=True,
    key=f"mode_selector_{st.session_state.ui_lang}", label_visibility="collapsed",
)
st.session_state["execution_mode"]=mode
is_aws=mode=="aws"
# Language and mode switches must never erase a cloud task.

if is_aws:
    if not (_cfg("AWS_API_BASE_URL") and _cfg("DEMO_API_KEY")):
        st.warning(label("aws_missing"))

left,right=st.columns([0.94,1.06],gap="large",vertical_alignment="top")
with left:
    with st.container(border=True):
        st.markdown(f'<div class="mq-p-head"><h3>{html.escape(label("data"))}</h3><p>{html.escape(label("data_sub"))}</p></div>',unsafe_allow_html=True)
        if "upload_widget_seq" not in st.session_state:st.session_state["upload_widget_seq"]=0
        upload=st.file_uploader("CSV dataset",type=["csv"],key=f"csv_upload_{st.session_state.upload_widget_seq}")
        bc,br=st.columns([1,1])
        with bc:
            if st.button(label("sample"),use_container_width=True):
                st.session_state["use_sample"]=True
                st.session_state["upload_widget_seq"]+=1
                st.session_state.pop("result_local",None)
                _event("SAMPLE_SELECTED")
                st.rerun()
        with br:
            if st.button(label("reset"),use_container_width=True):
                st.session_state["use_sample"]=False
                st.session_state["upload_widget_seq"]+=1
                for k in ("result_local","result_aws","aws_status","aws_job_id","aws_upload_error","aws_polling","aws_poll_error","aws_result_error","_last_fingerprint","aws_notice"):
                    st.session_state.pop(k,None)
                st.session_state["job_id_input"]=""
                if "job" in st.query_params:
                    del st.query_params["job"]
                st.session_state["ui_events"]=[]
                st.rerun()
        file_name=None;raw=None
        if upload is not None:
            raw=upload.getvalue();file_name=upload.name
            st.session_state["use_sample"]=False
        elif st.session_state.get("use_sample",False):
            file_name="sample_valid.csv";raw=(Path(__file__).parent/"data"/file_name).read_bytes()
        has_file=raw is not None
        valid=False;check=None
        if has_file:
            check=validate_file(raw,file_name)
            valid=not bool(check["errors"])
            fingerprint=f"{file_name}:{check['job_id']}"
            if st.session_state.get("_last_fingerprint") != fingerprint:
                st.session_state["_last_fingerprint"]=fingerprint
                st.session_state.pop("result_local", None)
                st.session_state.pop("aws_notice",None)
            st.caption(f'📄 {file_name} · {len(raw):,} bytes · {label("job")}: `{check["job_id"]}`')
            if valid:
                st.success(f'{label("ready")} · {check["rows"]:,} rows',icon="✅")
            else:
                for err in _translate_warnings(check["errors"]):
                    (st.warning if is_aws else st.error)(err)
            with st.expander(label("file_preview"),expanded=False):
                if check["frame"] is not None:
                    st.dataframe(check["frame"].head(15),hide_index=True,use_container_width=True)
            if check["warnings"]:
                with st.expander(f'{label("warnings")} ({len(check["warnings"])})'):
                    for warning in _translate_warnings(check["warnings"]):st.warning(warning)
        else:
            st.caption(label("not_selected"))
        st.markdown(f'<div class="mq-inline-meta"><span>{html.escape(label("types"))}</span><span>SHA-256 · v1</span></div>',unsafe_allow_html=True)
        # The AWS Validation Lambda remains authoritative, including INVALID_INPUT.
        if is_aws and has_file and not valid:
            st.info("AWS will validate the submitted file." if st.session_state.ui_lang=="en" else "文件提交后将由AWS进行最终校验。")
        over_row_limit=has_file and any("50,000" in str(err) and "超过" in str(err) for err in (check["errors"] if check else []))
        active=has_file and 0<len(raw or b"")<=MAX_BYTES and not over_row_limit and (is_aws or valid)
        if st.button(label("run_aws" if is_aws else "run_local"),type="primary",disabled=not active,use_container_width=True):
            if is_aws:
                st.session_state.pop("aws_upload_error",None)
                st.session_state.pop("aws_notice",None)
                try:
                    with st.spinner(label("in_progress")):
                        info=_api().upload(file_name,raw)
                    job_id=info["job_id"]
                    st.session_state["aws_job_id"]=job_id
                    st.session_state["job_id_input"]=job_id
                    st.query_params["job"]=job_id
                    st.session_state.pop("result_aws",None)
                    st.session_state.pop("aws_result_error",None)
                    if info.get("duplicate"):
                        existing=info.get("existing",{})
                        st.session_state["aws_status"]=existing
                        previous=existing.get("status","UNKNOWN")
                        st.session_state["aws_polling"]=previous not in {"COMPLETED","COMPLETED_WITH_WARNING","INVALID_INPUT","FAILED"}
                        if previous in {"COMPLETED","COMPLETED_WITH_WARNING"}:
                            try:
                                _load_result_from_aws(job_id,existing)
                            except CloudAPIError as exc:
                                st.session_state["aws_result_error"]=str(exc)
                        st.session_state["aws_notice"]={"type":"duplicate","job_id":job_id,"status":previous}
                        _event(f'Existing SHA-256 job reused · {job_id} · {previous}')
                    else:
                        st.session_state["aws_status"]={"job_id":job_id,"status":"AWAITING_EVENT"}
                        st.session_state["aws_polling"]=True
                        st.session_state["aws_poll_started"]=datetime.now(timezone.utc).timestamp()
                        _event(f'S3 raw/ upload accepted · {job_id}')
                        st.success(label("aws_uploaded"))
                except CloudAPIError as e:
                    st.session_state["aws_upload_error"]={"stage":e.stage,"status":e.status_code,"code":e.code,"request_id":e.request_id,"reason":e.reason}
                    st.error(f"{label('aws_upload_error')}: {e}")
                    tips={"ExpiredToken":"AWS temporary credentials expired. Restart Learner Lab and refresh Web API Lambda.","SignatureDoesNotMatch":"Check presigned PUT Content-Type, HTTP method and signing region.","AccessDenied":"Check Lambda role s3:PutObject, S3 bucket policy and temporary AWS credentials."}
                    tip=tips.get(e.code,"Check Web API Lambda credentials, S3 permissions and request ID.")
                    st.info(tip if st.session_state.ui_lang=="en" else {"ExpiredToken":"AWS临时凭证可能过期，请检查Learner Lab并刷新Web API Lambda。","SignatureDoesNotMatch":"检查预签名PUT的Content-Type、HTTP方法及签名区域。","AccessDenied":"检查Lambda角色的S3写入权限、桶策略以及临时AWS凭证。"}.get(e.code,"请检查Web API Lambda凭证、S3权限与Request ID。"))
                    _event(f"{e.stage} · FAILED · HTTP {e.status_code or 'N/A'} · {e.code}")
                except Exception:
                    st.session_state["aws_upload_error"]={"stage":"UNKNOWN","status":None,"code":"UNEXPECTED_ERROR"}
                    st.error("Upload failed; check Streamlit logs." if st.session_state.ui_lang=="en" else "上传失败，请检查Streamlit日志。")
                    _event("Upload error · UNEXPECTED_ERROR")
            else:
                try:
                    with st.spinner(label("in_progress")):
                        report,cleaned=analyze_file(raw,file_name)
                    st.session_state["result_local"]=(report,cleaned,"local")
                    _event(f'Local validation, cleaning and analysis completed · {report["job_id"]}')
                    st.success(label("complete"))
                except Exception as e:
                    st.error(str(e))



        notice=st.session_state.get("aws_notice") if is_aws else None
        if notice and notice.get("type")=="duplicate" and notice.get("job_id")==st.session_state.get("aws_job_id"):
            previous=notice.get("status","UNKNOWN")
            if st.session_state.ui_lang=="en":
                st.warning(f"Duplicate content detected. Reusing AWS job ({previous}); no reprocessing.")
            else:
                st.warning(f"检测到相同内容，已复用AWS任务（{previous}），不会重复处理。")

    if is_aws:
        with st.container(border=True):
            st.markdown(f'**{label("lookup")}**')
            typed=st.text_input("Job ID",max_chars=64,key="job_id_input")
            if st.button(label("refresh"),disabled=not bool(re.fullmatch(r"[0-9a-fA-F]{16}",typed.strip())),use_container_width=True):
                try:
                    job_id=typed.strip().lower()
                    with st.spinner(label("in_progress")):
                        reply=_api().status(job_id)
                    previous=st.session_state.get("aws_status",{}).get("status")
                    st.session_state["aws_status"]=reply
                    st.session_state["aws_job_id"]=job_id
                    st.query_params["job"]=job_id
                    state=reply.get("status","UNKNOWN")
                    st.session_state["aws_polling"]=state not in {"COMPLETED","COMPLETED_WITH_WARNING","INVALID_INPUT","FAILED"}
                    st.session_state["aws_poll_started"]=datetime.now(timezone.utc).timestamp()
                    st.session_state.pop("aws_upload_error",None)
                    if state!=previous:
                        _event(f'GET /jobs/{job_id} · {state}')
                    if state in {"COMPLETED","COMPLETED_WITH_WARNING"}:
                        _load_result_from_aws(job_id,reply)
                    st.success(f'{label("status")}: {label("status_"+state)}')
                except CloudAPIError as e:
                    st.error(f'{label("aws_fetch_error")}: {e}')
                except Exception:
                    st.error(label("aws_fetch_error"))
            aws_state=st.session_state.get("aws_status",{}).get("status")
            if aws_state=="FAILED":
                st.error(label("job_failed"))
            elif aws_state=="INVALID_INPUT":
                errs=st.session_state.get("aws_status",{}).get("validation_errors",[])
                st.error(label("job_invalid") + (" · "+", ".join(map(str,errs[:6])) if isinstance(errs,list) and errs else ""))

@st.fragment(run_every="4s")
def live_job_panel():
    """Only poll actual AWS job status; no simulated timers or fabricated events."""
    if is_aws and _cfg("AWS_API_BASE_URL") and _cfg("DEMO_API_KEY") and st.session_state.get("aws_polling") and st.session_state.get("aws_job_id"):
        job_id=st.session_state["aws_job_id"]
        try:
            started=st.session_state.get("aws_poll_started")
            if started and datetime.now(timezone.utc).timestamp()-started>240:
                st.session_state["aws_polling"]=False
                st.session_state["aws_poll_error"]=("The job did not complete within four minutes. Check S3 event notification, Lambda, SQS, and DynamoDB." if st.session_state.ui_lang=="en" else "超过4分钟仍未完成，请检查S3事件通知、Lambda、SQS和DynamoDB。")
                _event("Job status · TIMEOUT")
                st.rerun()
            reply=_api().status(job_id)
            status=reply.get("status","UNKNOWN")
            previous=st.session_state.get("aws_status",{}).get("status")
            st.session_state["aws_status"]=reply
            if status!=previous:
                _event(f'GET /jobs/{job_id} · {status}')
            st.session_state.pop("aws_poll_error",None)
            if status in {"COMPLETED","COMPLETED_WITH_WARNING","INVALID_INPUT","FAILED"}:
                st.session_state["aws_polling"]=False
                if status in {"COMPLETED","COMPLETED_WITH_WARNING"}:
                    try:
                        _load_result_from_aws(job_id,reply)
                        st.session_state.pop("aws_result_error",None)
                    except CloudAPIError as exc:
                        st.session_state["aws_result_error"]=str(exc)
                    except Exception:
                        st.session_state["aws_result_error"]="Report could not be loaded"
                st.rerun()
        except CloudAPIError as exc:
            st.session_state["aws_poll_error"]=str(exc)
            st.session_state["aws_polling"]=False
            _event(f'Job status request failed · {exc.code}')
    with st.container(border=True):
        st.markdown(f'<div class="mq-p-head"><h3>{html.escape(label("pipeline"))}</h3><p>{html.escape(label("pipeline_sub"))}</p></div>',unsafe_allow_html=True)
        result=st.session_state.get("result_aws" if is_aws else "result_local")
        aws_status=st.session_state.get("aws_status",{}).get("status", "")
        failure=st.session_state.get("aws_upload_error") if is_aws else None
        if failure:
            aws_status="AWS_UPLOAD_FAILED"
            st.error(f"{'Upload failed' if st.session_state.ui_lang=='en' else '上传失败'} · HTTP {failure['status'] or 'N/A'} · {failure['code']}")
        job=st.session_state.get("aws_job_id", "") if is_aws else (check["job_id"] if check else "")
        st.markdown(_pipeline(is_aws,has_file,valid,bool(result),aws_status,job),unsafe_allow_html=True)
        status_txt=st.session_state.get("aws_status",{}).get("status","")
        if is_aws and status_txt=="INVALID_INPUT":
            errs=st.session_state.get("aws_status",{}).get("validation_errors",[])
            st.error(("AWS validation rejected the CSV" if st.session_state.ui_lang=="en" else "AWS验证拒绝了CSV") + (": "+", ".join(map(str,errs[:6])) if isinstance(errs,list) and errs else ""))
        if is_aws and status_txt=="FAILED":
            st.error(label("job_failed"))
        if is_aws and st.session_state.get("aws_result_error"):
            st.warning(st.session_state["aws_result_error"])
        if is_aws and st.session_state.get("aws_poll_error"):
            st.warning(st.session_state["aws_poll_error"])
        st.markdown(f'<div style="margin-top:13px;font-size:11px;color:#547998;font-weight:750">⌘ {html.escape(label("events"))}</div>',unsafe_allow_html=True)
        events=st.session_state.get("ui_events",[])
        if events:
            st.markdown('<div class="mq-log">'+''.join(f'<div>{html.escape(_localized_event(x))}</div>' for x in events)+'</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="mq-log">{html.escape(label("pending"))}</div>',unsafe_allow_html=True)

with right:
    live_job_panel()

st.markdown(f'<div class="mq-section-title">{html.escape(label("results"))}</div><div style="color:#7b94aa;font-size:12px;margin-bottom:13px">{html.escape(label("results_sub"))}</div>',unsafe_allow_html=True)
result=st.session_state.get("result_aws" if is_aws else "result_local")
if result:
    report,cleaned,origin=result
    st.caption(f'{label("source")}: {label("origin_aws" if origin=="aws" else "origin_local")}')
    tab_chart,tab_quality,tab_download=st.tabs([label("charts"),label("quality"),label("downloads")])
    with tab_chart:
        _render_analytics(report)
        # Additional breakdowns remain deterministic, no AI claims.
        a,b=st.columns(2)
        for holder,name,key in ((a,label("product"),"by_product"),(b,label("supplier"),"by_supplier_batch")):
            with holder:
                st.markdown(f'**{name}**')
                obj=report.get(key,{})
                rows=[{"Segment":str(seg),"Defect rate (%)":round(v.get("defect_rate",0)*100,2),"Labeled":v.get("labeled",0)} for seg,v in obj.items() if v.get("defect_rate") is not None]
                if rows:
                    df=pd.DataFrame(rows).set_index("Segment")
                    st.bar_chart(df["Defect rate (%)"],y_label="%")
                else:st.caption(label("no_data"))
    with tab_quality:
        flags=report.get("quality_flags",{})
        st.markdown(f'**{label("missing")}**')
        missing=report.get("missing_values_by_column",{})
        if missing:
            st.dataframe(pd.DataFrame([{"Column":k,"Missing rows":v} for k,v in missing.items()]),hide_index=True,use_container_width=True)
        else:st.caption(label("no_data"))
        st.markdown(f'**{label("issues")}**')
        if flags:st.dataframe(pd.DataFrame([{"Flag":k,"Rows":v} for k,v in flags.items()]),hide_index=True,use_container_width=True)
        else:st.caption(label("warnings_none"))
        if cleaned is not None:
            st.markdown(f'**{label("clean_preview")}**')
            st.dataframe(cleaned.head(100),hide_index=True,use_container_width=True)
    with tab_download:
        c1,c2=st.columns(2)
        with c1:
            st.download_button(label("report_download"),json.dumps(report,ensure_ascii=False,indent=2,default=str),file_name=f'report_{report.get("job_id","local")}.json',mime="application/json",use_container_width=True)
        with c2:
            if cleaned is not None:
                st.download_button(label("csv_download"),cleaned.to_csv(index=False).encode("utf-8-sig"),file_name=f'cleaned_{report.get("job_id","local")}.csv',mime="text/csv",use_container_width=True)
else:
    st.info(label("nothing"))

with st.expander(label("docs")):
    st.markdown(f'**{label("data_dictionary")}**')
    examples={"timestamp":"2026-09-01T08:00:00","machine_id":"M03","shift":"Night","product_id":"P02","supplier_batch":"SB-204","temperature":"91.3","defect_label":"1","batch_id":"B2026-001","defect_type":"Surface"}
    st.dataframe(pd.DataFrame([{label("column"):name,label("kind"):label("required") if name in REQUIRED else label("optional"),label("format"):examples.get(name,"")} for name in list(REQUIRED)+list(OPTIONAL)]),hide_index=True,use_container_width=True)
    p=Path(__file__).parent/"data"
    a,b=st.columns(2)
    with a:
        st.download_button(label("download_sample"),(p/"sample_valid.csv").read_bytes(),file_name="sample_valid.csv",mime="text/csv",use_container_width=True)
    with b:
        st.download_button(label("download_6000"),(p/"manufacturing_6000.csv").read_bytes(),file_name="manufacturing_6000.csv",mime="text/csv",use_container_width=True)

st.markdown(f'<div class="mq-footer">{html.escape(label("footer"))}</div>',unsafe_allow_html=True)
