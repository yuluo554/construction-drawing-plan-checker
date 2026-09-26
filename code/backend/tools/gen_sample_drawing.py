# -*- coding: utf-8 -*-
"""程序化生成 22G101 平法标注样例图纸（DXF+PDF）—— 自制数据管线 v1（见 plan/04 §3.4）。

用途：
1. 为图纸解析器提供带真值的训练/测试样本（参数随机可复现，支持批量基准评测）；
2. 端到端演示数据；与 gen_sample_plan.py 配对生成"图纸+方案"数据集。

运行：cd code/backend && py tools/gen_sample_drawing.py [输出目录] [随机种子]
输出：<dir>/sample_beam_plan.dxf + sample_beam_plan.pdf + sample_beam_plan.truth.json
"""
import json
import os
import random
import sys

import ezdxf
import fitz

SCALE = 100.0  # 1m -> 100 units


def make_scenario(rnd):
    """随机生成梁/柱参数（用于批量基准评测）。"""
    dias = [12, 14, 16, 18, 20, 22, 25]
    beams = []
    for i in range(rnd.randint(3, 5)):
        beams.append({"tag": "%s%d" % (rnd.choice(["KL", "KL", "KL", "L"]), i + 1),
                      "spans": rnd.randint(1, 4),
                      "sec": [rnd.choice([200, 250, 300, 350]), rnd.choice([400, 500, 600, 650, 700])],
                      "stir": ("Φ", rnd.choice([8, 10]),
                               rnd.choice(["100/200", "150/200", "200/200"]), rnd.choice([2, 4])),
                      "top": (rnd.randint(2, 4), "Φ", rnd.choice(dias)),
                      "bot": (rnd.randint(2, 4), "Φ", rnd.choice(dias))})
    columns = []
    for i in range(rnd.randint(2, 4)):
        columns.append({"tag": "KZ%d" % (i + 1),
                        "sec": [rnd.choice([400, 500, 600]), rnd.choice([400, 500, 600, 700])],
                        "rebar": (str(rnd.randint(8, 24)), "Φ", rnd.choice(dias)),
                        "stir": ("Φ", rnd.choice([8, 10]), rnd.choice(["100/150", "100/200"]), 4)})
    return {"beams": beams, "columns": columns,
            "conc": rnd.choice(["C30", "C35", "C40"]), "protect": rnd.choice([15, 20, 25])}


def build(seed=7):
    rnd = random.Random(seed)
    sc = make_scenario(rnd)
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    doc.layers.add("BEAM-TAG", color=3)
    doc.layers.add("GRID", color=1)
    doc.layers.add("TITLE", color=7)

    beams, columns, conc = sc["beams"], sc["columns"], sc["conc"]
    truth = {"beams": [], "columns": [], "concrete": conc, "protect": sc["protect"]}
    rows_n = max(len(beams), 4)

    # 轴网
    for i in range(5):
        x = i * 6 * SCALE
        msp.add_line((x, 0), (x, rows_n * 6 * SCALE), dxfattribs={"layer": "GRID"})
        msp.add_text("%d" % (i + 1), dxfattribs={"layer": "GRID", "height": 0.35}).set_placement((x + 1, rows_n * 6 * SCALE + 2))
    for j in range(5):
        y = j * 6 * SCALE
        msp.add_line((0, y), (24 * SCALE, y), dxfattribs={"layer": "GRID"})
        msp.add_text("%s" % chr(65 + j), dxfattribs={"layer": "GRID", "height": 0.35}).set_placement((24 * SCALE + 2, y + 1))

    # 梁集中标注（随机化跨中位置）
    for bi, b in enumerate(beams):
        y = 3 * SCALE + bi * 6 * SCALE
        msp.add_line((0, y), (24 * SCALE, y), dxfattribs={"layer": "BEAM-TAG"})
        tag_x = rnd.uniform(2, 16) * SCALE
        w, h = b["sec"]
        stir, top, bot = b["stir"], b["top"], b["bot"]
        msp.add_text("%s(%d) %d×%d" % (b["tag"], b["spans"], w, h),
                     dxfattribs={"layer": "BEAM-TAG", "height": 0.4}).set_placement((tag_x, y + 1.2))
        msp.add_text("%s%s@%s(%d) %s%s%s;%s%s%s" % (stir[0], stir[1], stir[2], stir[3],
                                                    top[0], top[1], top[2], bot[0], bot[1], bot[2]),
                     dxfattribs={"layer": "BEAM-TAG", "height": 0.4}).set_placement((tag_x, y + 0.6))
        truth["beams"].append({"tag": b["tag"], "spans": b["spans"], "sec": [w, h],
                               "stirrup": "%s%s@%s(%d肢)" % (stir[0], stir[1], stir[2], stir[3]),
                               "top": "%d%s%d" % top, "bottom": "%d%s%d" % bot})

    # 柱（轴网交点）
    for ci, c in enumerate(columns):
        w, h = c["sec"]
        x = (ci + 1) * 6 * SCALE
        y = 6 * SCALE
        msp.add_lwpolyline([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2),
                            (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)],
                           close=True, dxfattribs={"layer": "BEAM-TAG"})
        msp.add_text("%s %d×%d %s%s%s %s%s@%s(%d)" % (c["tag"], w, h,
                                                      c["rebar"][0], c["rebar"][1], c["rebar"][2],
                                                      c["stir"][0], c["stir"][1], c["stir"][2], c["stir"][3]),
                     dxfattribs={"layer": "BEAM-TAG", "height": 0.35}).set_placement((x - w / 2, y + h / 2 + 1))
        truth["columns"].append({"tag": c["tag"], "sec": [w, h],
                                 "rebar": "%s%s%s" % c["rebar"], "stir": list(c["stir"])})

    # 总说明与图框
    msp.add_text("混凝土强度等级为%s，保护层厚度%dmm" % (conc, sc["protect"]),
                 dxfattribs={"layer": "TITLE", "height": 0.5}).set_placement((2, rows_n * 6 * SCALE + 100))
    msp.add_text("工程名称：示例教学楼结构施工图 图号：结施-05 比例1:100",
                 dxfattribs={"layer": "TITLE", "height": 0.5}).set_placement((2, -3))
    return doc, truth


def export(doc, truth, outdir):
    os.makedirs(outdir, exist_ok=True)
    dxf_path = os.path.join(outdir, "sample_beam_plan.dxf")
    doc.saveas(dxf_path)

    # PDF：直接用 fitz 生成带文本层的矢量页（保证解析测试与演示可用；
    # matplotlib 渲染会把文字转为路径，导致无文本层）
    pdf_path = os.path.join(outdir, "sample_beam_plan.pdf")
    fdoc = fitz.open()
    page = fdoc.new_page()
    y = 100
    page.insert_text((60, y), "混凝土强度等级为%s" % truth["concrete"], fontsize=10, fontname="china-s")
    for b in truth["beams"]:
        y += 24
        page.insert_text((60, y), "%s(%d) %d×%d" % (b["tag"], b["spans"], b["sec"][0], b["sec"][1]),
                         fontsize=9, fontname="china-s")
        y += 14
        page.insert_text((60, y), "%s %s;%s" % (b["stirrup"], b["top"], b["bottom"]),
                         fontsize=9, fontname="china-s")
    for c in truth["columns"]:
        y += 24
        page.insert_text((60, y), "%s %d×%d %s" % (c["tag"], c["sec"][0], c["sec"][1], c["rebar"]),
                         fontsize=9, fontname="china-s")
    y += 30
    page.insert_text((60, y), "工程名称：示例教学楼结构施工图 图号：结施-05 比例1:100",
                     fontsize=10, fontname="china-s")
    fdoc.save(pdf_path)

    truth_path = os.path.join(outdir, "sample_beam_plan.truth.json")
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=2)
    print("生成完成：", dxf_path)
    print("        ", pdf_path)
    print("        ", truth_path)


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "../../data/施工图纸/自制样例"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    doc, truth = build(seed)
    export(doc, truth, outdir)
