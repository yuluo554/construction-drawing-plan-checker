# -*- coding: utf-8 -*-
"""轻量工作流引擎（LangGraph 风格状态机）—— 节点/边/条件路由/节点级重试与耗时。

设计说明：LangGraph 新版不再支持 Python 3.8，本实现保持同语义接口
（add_node / add_edge / invoke(state)），后续环境升级可无缝替换。
"""
import time
import traceback


class Graph:
    def __init__(self, name="workflow"):
        self.name = name
        self.nodes = {}
        self.edges = {}      # node -> next node（无条件边）
        self.conditional = {}  # node -> fn(state) -> next node

    def add_node(self, name, fn, retries=0):
        self.nodes[name] = {"fn": fn, "retries": retries}
        return self

    def add_edge(self, a, b):
        self.edges[a] = b
        return self

    def add_conditional_edges(self, a, fn):
        self.conditional[a] = fn
        return self

    def set_entry(self, entry):
        self.entry = entry
        return self

    def invoke(self, state):
        state = dict(state or {})
        state.setdefault("_trace", [])
        cur = self.entry
        steps = 0
        while cur and steps < 50:
            node = self.nodes.get(cur)
            if node is None:
                break
            t0 = time.time()
            err = None
            for attempt in range(node["retries"] + 1):
                try:
                    state = node["fn"](state) or state
                    err = None
                    break
                except Exception as exc:
                    err = exc
                    if attempt < node["retries"]:
                        time.sleep(0.5)
                    else:
                        traceback.print_exc()
            state["_trace"].append({
                "node": cur, "ok": err is None,
                "耗时s": round(time.time() - t0, 2),
                "error": str(err) if err else ""})
            if err is not None:
                state.setdefault("_errors", []).append({"node": cur, "error": str(err)})
                break  # 失败即停（校核流水线要求确定性）
            steps += 1
            nxt = self.conditional.get(cur)
            if nxt is not None:
                cur = nxt(state)
            else:
                cur = self.edges.get(cur)
        state["_done"] = True
        return state
