# -*- coding: utf-8 -*-
"""Web 服务 —— 上传图纸/方案 → 解析/校核 → 结果面板数据 + 报告下载。

运行：cd code/backend && py -m uvicorn app.server:app --reload --port 8000
浏览器打开 http://127.0.0.1:8000
"""
import os
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .parsers.dxf_parser import parse_any_cad
from .parsers.pdf_parser import parse_pdf
from .parsers.docx_parser import parse_docx
from .rules.engine import run_checks
from .report.export import build_report_docx
from .schemas.parameter_card import ParameterCard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # code/backend
DATA_DIR = os.path.join(BASE, "webdata")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORT_DIR = os.path.join(DATA_DIR, "reports")


def _resolve_static_dir():
    """静态目录：包内 app/_data/static 优先，回退 code/backend/static。

    v0.1.0 的 wheel 不含 static，装完后服务能起但首页 404、/static/* 全挂（v0.1.1 修）。
    这里不抛异常：让 API 仍可用，但首页请求会返回明确的 503 说明而不是空 404。
    """
    from .resources import AssetMissing, asset_path
    try:
        return asset_path("static")
    except AssetMissing:
        return ""


STATIC_DIR = _resolve_static_dir()
for d in (UPLOAD_DIR, REPORT_DIR):
    os.makedirs(d, exist_ok=True)
if STATIC_DIR:
    os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="施工图×施工方案 协同校核系统")
STORE = {}  # id -> {"kind","path","card"}


def _save_upload(upload: UploadFile) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in (".pdf", ".dxf", ".dwg", ".docx"):
        raise HTTPException(400, "仅支持 PDF/DXF/DWG 图纸与 DOCX 方案")
    fid = uuid.uuid4().hex[:12]
    path = os.path.join(UPLOAD_DIR, fid + ext)
    with open(path, "wb") as f:
        f.write(upload.file.read())
    return path


def _parse_by_kind(kind: str, path: str):
    if kind == "drawing":
        ext = os.path.splitext(path)[1].lower()
        return parse_pdf(path) if ext == ".pdf" else parse_any_cad(path)
    return parse_docx(path)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), kind: str = Form(...)):
    if kind not in ("drawing", "plan"):
        raise HTTPException(400, "kind 必须是 drawing 或 plan")
    path = _save_upload(file)
    card = _parse_by_kind(kind, path)
    fid = uuid.uuid4().hex[:12]
    STORE[fid] = {"kind": kind, "path": path, "card": card, "name": os.path.basename(path)}
    return {
        "id": fid, "kind": kind, "name": STORE[fid]["name"],
        "参数数": len(card.parameters),
        "warnings": card.warnings[:5],
        "meta": card.meta,
        "pdf": path.lower().endswith(".pdf"),
    }


@app.post("/api/check")
async def check(body: dict):
    did, pid = body.get("drawing_id"), body.get("plan_id")
    if did not in STORE or pid not in STORE:
        raise HTTPException(404, "请先上传图纸与方案")
    rag_on = bool(body.get("rag"))
    kb = None
    if rag_on:
        try:
            from .knowledge.rag import KB
            kb = KB()
        except Exception:
            kb = None
            rag_on = False
    report = run_checks(STORE[did]["card"], STORE[pid]["card"], rag_on=rag_on, kb=kb)
    rid = uuid.uuid4().hex[:12]
    docx_path = os.path.join(REPORT_DIR, "校核报告_%s.docx" % rid)
    build_report_docx(report, STORE[did]["card"], STORE[pid]["card"], docx_path)
    STORE[rid] = {"kind": "report", "path": docx_path, "report": report}
    return {"report_id": rid, "report": report}


@app.get("/api/report/{rid}.docx")
def download_report(rid: str):
    item = STORE.get(rid)
    if not item or item["kind"] != "report":
        raise HTTPException(404, "报告不存在")
    return FileResponse(item["path"], filename="协同校核报告_%s.docx" % rid,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/source/{fid}")
def source_file(fid: str):
    item = STORE.get(fid)
    if not item or item["kind"] not in ("drawing", "plan"):
        raise HTTPException(404, "文件不存在")
    return FileResponse(item["path"], filename=item["name"])


@app.get("/api/card/{fid}")
def card_json(fid: str):
    item = STORE.get(fid)
    if not item:
        raise HTTPException(404, "不存在")
    return JSONResponse(item["card"].to_dict())


@app.get("/")
def index():
    idx = os.path.join(STATIC_DIR, "index.html") if STATIC_DIR else ""
    if not idx or not os.path.isfile(idx):
        # 明确报"静态资源缺失"而不是让浏览器拿到空白 404（v0.1.0 装态缺陷）
        raise HTTPException(
            503,
            "Web 静态资源缺失（static/index.html 未随安装包分发）。"
            "API 端点仍可用；请改用 `pip install -e .`（源码态）或 Release 的 source zip。")
    return FileResponse(idx)


if STATIC_DIR:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
