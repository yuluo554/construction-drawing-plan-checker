# -*- coding: utf-8 -*-
"""Web 服务 API 测试 —— 子进程启动独立实例(8011端口)，requests 调用。"""
import os
import subprocess
import sys
import time

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DRAWING_PDF = os.path.join(REPO, "data", "施工图纸", "自制样例", "sample_beam_plan.pdf")
PLAN_DOCX = os.path.join(REPO, "data", "施工方案", "自制样例", "sample_formwork_plan_13.docx")
PORT = 8011
BASE = "http://127.0.0.1:%d" % PORT


@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.server:app",
                             "--host", "127.0.0.1", "--port", str(PORT)],
                            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            if requests.get(BASE + "/", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("服务启动失败")
    yield
    proc.kill()


def _upload(path, kind):
    with open(path, "rb") as f:
        r = requests.post(BASE + "/api/upload", files={"file": (os.path.basename(path), f)},
                          data={"kind": kind}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.skipif(not (os.path.exists(DRAWING_PDF) and os.path.exists(PLAN_DOCX)),
                    reason="配对演示数据缺失")
def test_full_flow(server):
    d = _upload(DRAWING_PDF, "drawing")
    assert d["参数数"] > 0 and d["pdf"] is True
    p = _upload(PLAN_DOCX, "plan")
    assert p["参数数"] > 0

    r = requests.post(BASE + "/api/check", json={"drawing_id": d["id"], "plan_id": p["id"],
                                                 "rag": False}, timeout=120)
    assert r.status_code == 200
    body = r.json()
    report = body["report"]
    assert "结论" in report and "summary" in report
    assert report["summary"]["致命"] >= 1              # 植入的混凝土差异

    # 报告下载
    rd = requests.get(f"{BASE}/api/report/{body['report_id']}.docx", timeout=60)
    assert rd.status_code == 200 and len(rd.content) > 5000

    # 参数卡与源文件接口
    card = requests.get(f"{BASE}/api/card/{d['id']}", timeout=30).json()
    assert card["doc_type"] == "drawing"
    src = requests.get(f"{BASE}/api/source/{d['id']}", timeout=30)
    assert src.status_code == 200


def test_upload_rejects_bad_kind(server):
    r = requests.post(BASE + "/api/upload", files={"file": ("a.txt", b"hi")},
                      data={"kind": "drawing"}, timeout=30)
    assert r.status_code == 400
