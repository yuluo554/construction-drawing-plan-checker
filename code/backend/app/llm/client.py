# -*- coding: utf-8 -*-
"""大模型客户端 —— OpenAI 兼容接口（阿里云百炼等），从 code/.env 读取配置。

用法：
    from app.llm.client import chat, chat_json
    text = chat("把这句话翻译成英文：你好")
    data = chat_json("从下文抽取参数，输出JSON：...")   # 自动剥离 ```json 围栏并解析

环境变量（.env，位于 code/ 根目录）：
    LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
"""
import json
import os
import re
import time
from pathlib import Path

_ENV_LOADED = False
CFG = {"LLM_API_KEY": "", "LLM_BASE_URL": "", "LLM_MODEL": "qwen3.8-flash"}


def load_env(env_path=None):
    """读取 .env（不覆盖已存在的进程环境变量）。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return CFG
    p = Path(env_path or Path(__file__).resolve().parents[3] / ".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    for k in CFG:
        CFG[k] = os.environ.get(k, CFG[k])
    _ENV_LOADED = True
    return CFG


def chat(prompt, system=None, model=None, temperature=0.1, max_tokens=2000,
         retries=2, timeout=90, json_mode=False, enable_thinking=False):
    """单轮对话，返回文本。失败重试；json_mode=True 时附加 JSON 指令。
    enable_thinking=False 关闭推理模式（qwen3 系列默认开启，抽取任务无需）。"""
    import requests
    cfg = load_env()
    if not cfg["LLM_API_KEY"]:
        raise RuntimeError("未配置 LLM_API_KEY（请参考 .env.example 配置 code/.env）")
    url = cfg["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + cfg["LLM_API_KEY"],
               "Content-Type": "application/json"}
    sys_prompt = system or ("你是一名建筑工程领域的资深工程师，负责施工图纸与施工方案的"
                            "参数校核。输出必须严格依据给定材料，不得编造。")
    if json_mode:
        sys_prompt += "只输出合法 JSON，不要输出任何解释或 Markdown 围栏。"
    body = {"model": model or cfg["LLM_MODEL"],
            "messages": ([{"role": "system", "content": sys_prompt}] if sys_prompt else [])
            + [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enable_thinking": enable_thinking}
    last_err = None
    for i in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"] or ""
            last_err = RuntimeError("HTTP %s: %s" % (r.status_code, r.text[:300]))
            if r.status_code in (401, 404):
                break  # 鉴权/模型错误重试无意义
        except Exception as exc:
            last_err = exc
        time.sleep(2 * (i + 1))
    raise last_err


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.S)


def chat_json(prompt, **kw):
    """要求模型输出 JSON 并解析；自动剥离围栏/前后缀；截断时尝试修复。"""
    text = chat(prompt, json_mode=True, **kw)
    m = _JSON_FENCE_RE.search(text)
    raw = m.group(1) if m else text
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    end = max(raw.rfind("}"), raw.rfind("]"))
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # max_tokens 截断修复：回退到上一个完整对象并闭合数组/对象
    pos = raw.rfind("}")
    while pos > 0:
        try:
            return json.loads(raw[:pos + 1] + "]}")
        except json.JSONDecodeError:
            try:
                return json.loads(raw[:pos + 1] + '"}]}')
            except json.JSONDecodeError:
                pos = raw.rfind("}", 0, pos)
    raise ValueError("JSON 解析失败（含修复尝试）: %s" % text[:200])


if __name__ == "__main__":
    print("连通性测试:", chat("只回复两个字：正常"))
