# -*- coding: utf-8 -*-
"""程序化生成《模板工程专项施工方案》样例 docx —— 命题单位数据的替代方案（plan/04 §3）。

功能：
1. 按 建办质〔2021〕48号 指南的标准九章结构生成方案正文+参数表；
2. 参数由种子随机生成（支撑高度/立杆间距/步距/混凝土强度…），真值写入 truth.json；
3. 可注入与图纸真值的"已知差异"（混凝土强度不一致等），供阶段4一致性校核评测；
4. 与 gen_sample_drawing.py 同种子生成配对的 图纸+方案 演示数据集。

运行：cd code/backend && py tools/gen_sample_plan.py [输出目录] [种子]
"""
import json
import os
import random
import sys

from docx import Document
from docx.shared import Pt

CHAPTERS = [
    "一、编制依据", "二、工程概况", "三、施工计划", "四、施工工艺技术",
    "五、施工安全保证措施", "六、施工管理及作业人员配备和分工", "七、验收要求",
    "八、应急处置措施", "九、计算书及相关图纸",
]


def scenario(seed, drawing_conc=None):
    """随机生成场景参数与真值。drawing_conc 提供图纸真值以构成配对数据集。"""
    rnd = random.Random(seed)
    conc = drawing_conc or rnd.choice(["C30", "C35", "C40"])
    support_h = rnd.choice([4.2, 4.6, 6.2, 6.8, 8.5, 9.0])
    spacing = rnd.choice([0.9, 1.0, 1.2])
    step = rnd.choice([1.2, 1.5, 1.8])
    slab_t = rnd.choice([110, 120, 150])
    floors = rnd.randint(6, 18)
    area = rnd.randint(8000, 30000)
    # 注入差异：方案混凝土强度以 60% 概率与图纸一致
    plan_conc = conc if rnd.random() < 0.6 else rnd.choice([c for c in ["C30", "C35", "C40"] if c != conc])
    # 预期危大判定（模板支撑：≥5 危大，≥8 超规模）
    if support_h >= 8:
        weida = "超规模(须专家论证)"
    elif support_h >= 5:
        weida = "危大(须专项施工方案)"
    else:
        weida = "非危大"
    return {"种子": seed, "混凝土强度_图纸": conc, "混凝土强度_方案": plan_conc,
            "支撑搭设高度m": support_h, "立杆间距m": spacing, "步距m": step,
            "楼板厚度mm": slab_t, "层数": floors, "建筑面积㎡": area,
            "预期危大判定": weida,
            "预期混凝土差异": plan_conc != conc}


def build_docx(sc, path):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)

    doc.add_heading("模板工程专项施工方案（程序化样例%d）" % sc["种子"], level=0)
    doc.add_paragraph("工程名称：示例项目%d#楼  编制单位：示例建设工程有限公司" % sc["种子"])

    for ch in CHAPTERS:
        doc.add_heading(ch, level=1)

    doc.add_paragraph("1、工程概况")
    doc.add_paragraph("本工程建筑面积约%d㎡，地下1层，地上%d层；结构形式为钢筋混凝土框架剪力墙结构，"
                      "基础形式为筏板基础。" % (sc["建筑面积㎡"], sc["层数"]))
    doc.add_paragraph("2、模板支撑体系概况")
    doc.add_paragraph("模板支架搭设高度为%.1fm，支撑体系采用扣件式钢管满堂支撑架。" % sc["支撑搭设高度m"])

    doc.add_paragraph("1、模板支撑体系设计参数")
    tbl = doc.add_table(rows=6, cols=2)
    tbl.style = "Table Grid"
    rows = [("支撑搭设高度H(m)", "%.1f" % sc["支撑搭设高度m"]),
            ("立杆间距la×lb(m)", "%.1f×%.1f" % (sc["立杆间距m"], sc["立杆间距m"])),
            ("水平杆步距h(m)", "%.1f" % sc["步距m"]),
            ("模板支架高度H(m)", "%.1f" % sc["支撑搭设高度m"]),
            ("支撑层楼板厚度h(mm)", "%d" % sc["楼板厚度mm"]),
            ("混凝土强度等级", sc["混凝土强度_方案"])]
    for i, (k, v) in enumerate(rows):
        tbl.cell(i, 0).text = k
        tbl.cell(i, 1).text = v

    doc.add_paragraph("1、材料要求")
    doc.add_paragraph("模板木方采用落叶松，钢管采用Q235焊接钢管，混凝土强度等级为%s。" % sc["混凝土强度_方案"])
    doc.add_paragraph("2、工艺流程")
    doc.add_paragraph("测量放线→搭设支撑架→安装梁底模板→安装板底模板→钢筋绑扎→混凝土浇筑→养护拆模。")

    doc.save(path)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "../../data/施工方案/自制样例"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    sc = scenario(seed)
    os.makedirs(outdir, exist_ok=True)
    docx_path = os.path.join(outdir, "sample_formwork_plan_%d.docx" % seed)
    build_docx(sc, docx_path)
    truth_path = os.path.join(outdir, "sample_formwork_plan_%d.truth.json" % seed)
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, indent=2)
    print("生成：", docx_path)
    print("真值：", truth_path)
    print(json.dumps(sc, ensure_ascii=False))


if __name__ == "__main__":
    main()
