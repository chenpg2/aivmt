#!/usr/bin/env python3
"""Generate an OFFLINE faculty scoring packet (LaTeX -> PDF) from the blinded eval transcripts.

Organized BY CASE: one chapter per OB/GYN case, each opening with the case background (so the rater
has the standardized-patient context), then every encounter of that case (full dialogue + an 8-item
scoring table). For faculty NOT on the local network: they fill scores on this PDF, return them, and
the operator enters each row into the web tool under that faculty's rater_id, matched by encounter_id.

Blinded: only de-identified transcript turns are printed — no system score, gold, or designed_quality.
Case background is the SP rubric context (presentation + the history points a thorough student should
elicit), drawn verbatim from the collaborator-reviewed case YAMLs; nothing is invented.
"""
from __future__ import annotations

import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

AIVMT = Path(__file__).resolve().parent.parent
EVAL_DIR = AIVMT / "data/eval_transcripts"
CASE_DIR = AIVMT / "conf/case"
OUT_TEX = AIVMT / "outputs" / "faculty_scoring_packet.tex"

_MARKER = re.compile(r"\s*\(#\d+_\d+\)")
_TODO = "TODO_COLLAB"

# Fixed chapter order.
CASE_ORDER = ["obgyn_ectopic_zh_01", "obgyn_aub_zh_01", "obgyn_vaginitis_zh_01"]
CASE_ZH = {
    "obgyn_ectopic_zh_01": "异位妊娠",
    "obgyn_aub_zh_01": "异常子宫出血",
    "obgyn_vaginitis_zh_01": "外阴阴道炎",
}

DIMENSIONS = [
    ("1. 开场 Set the stage", "未自我介绍/未说明目的 → 自我介绍、说明来意并建立融洽关系"),
    ("2. 采集信息 Elicit information", "几乎不提问/只问封闭式 → 系统、开放式地引出病史"),
    ("3. 提供信息 Give information", "未给任何解释/反馈 → 用病人能懂的语言清晰说明"),
    ("4. 理解病人视角 Understand perspective", "忽视病人的担忧与情绪 → 主动了解想法、顾虑与期望"),
    ("5. 结束问诊 End the encounter", "突兀结束 → 小结、答疑并妥善收尾"),
    ("6. 病史完整度 History completion", "关键病史几乎全部遗漏 → 应问要点基本问全"),
    ("7. 临床推理 Clinical reasoning", "提问无目的、无鉴别思路 → 围绕鉴别诊断有条理地追问"),
    ("8. 总体表现 Overall", "完全未达标 → 总体表现优秀"),
]


def tex_escape(s: str) -> str:
    repl = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(repl.get(c, c) for c in str(s))


def clean(v: object) -> str | None:
    """Return a printable value, or None if it is missing/TODO_COLLAB placeholder."""
    if v is None:
        return None
    s = str(v).strip()
    return None if (not s or s == _TODO) else s


def load_transcripts_by_case() -> dict[str, list[dict]]:
    by_case: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(glob.glob(str(EVAL_DIR / "*.json"))):
        rec = json.load(open(f, encoding="utf-8"))
        by_case[rec["case_id"]].append(rec)
    for recs in by_case.values():
        recs.sort(key=lambda r: r["encounter_id"])
    return by_case


def load_case(case_id: str) -> dict:
    return yaml.safe_load(open(CASE_DIR / f"{case_id}.yaml", encoding="utf-8"))


PREAMBLE = r"""\documentclass[11pt,fontset=macnew]{ctexart}
\usepackage[margin=2cm]{geometry}
\usepackage{booktabs}
\usepackage{array}
\usepackage{xcolor}
\usepackage{tcolorbox}
\usepackage{enumitem}
\usepackage{fancyhdr}
\definecolor{accent}{HTML}{0F6E56}
\definecolor{warn}{HTML}{993C1D}
\definecolor{caseblue}{HTML}{185FA5}
\renewcommand{\arraystretch}{1.35}
\pagestyle{fancy}\fancyhf{}
\rhead{\small AIVMT 教师评分包}\lhead{\small 盲评 · 仅供本研究}\cfoot{\small 第 \thepage 页}
\setlength{\headheight}{14pt}
\newcommand{\scorebox}{\fbox{\rule{0pt}{2.4ex}\hspace{3.2em}}}
\begin{document}
"""


def intro() -> str:
    rows = "".join(f"{tex_escape(n)} & {tex_escape(a)} \\\\\n" for n, a in DIMENSIONS)
    return r"""
\begin{center}
{\LARGE\bfseries AIVMT 标准化病人 —— 教师评分包}\\[4pt]
{\large 离线打分用 · 共 3 个病例}\\[2pt]
{\color{warn} 本包不含任何系统评分或参考答案，以保证盲评。}
\end{center}

\vspace{6pt}
\section*{怎么打分（请先读这一页）}
\begin{enumerate}[leftmargin=1.6em,itemsep=3pt]
  \item 本包按\textbf{病例}分为 3 章。每章\textbf{开头先介绍该病例背景}（病人情况 + 应采集的关键病史），请先读一遍，建立这个病例“满分问诊该问到什么”的判断。
  \item 然后是该病例下\textbf{若干次不同水平的学生问诊}。每一次都\textbf{先通读完整对话}，再按下面 8 个维度打分。
  \item 每项打 \textbf{0 到 1 之间的小数}（如 0、0.3、0.5、0.7、1），写在每条记录后的“评分”栏。
\end{enumerate}

\begin{center}
\begin{tabular}{>{\raggedright\arraybackslash}p{5.2cm} >{\raggedright\arraybackslash}p{9.8cm}}
\toprule
\textbf{维度} & \textbf{0 分（差） $\rightarrow$ 1 分（好）} \\
\midrule
""" + rows + r"""\bottomrule
\end{tabular}
\end{center}

\vspace{6pt}
\begin{tcolorbox}[colback=accent!6,colframe=accent,boxrule=0.6pt,arc=2pt]
\textbf{打完后怎么办：} 把每条记录后填好的分数（连同最上方的\textbf{编号}）发回给项目组即可。
可直接在本 PDF 上填、打印后手写、或另用表格抄写——只要每条的\textbf{编号}和 8 个分数对得上。
项目组会按您的评分者编号录入系统。备注栏选填，写评分依据对分析很有帮助。
\end{tcolorbox}
\newpage
"""


def case_intro(case_id: str, n_enc: int) -> str:
    c = load_case(case_id)
    demo = c.get("demographics") or {}
    age, sex = clean(demo.get("age")), clean(demo.get("sex"))
    sex_zh = {"female": "女", "male": "男"}.get(sex or "", sex or "")
    marital = clean(demo.get("marital_status"))
    who = "、".join(x for x in [f"{age} 岁" if age else None, sex_zh, marital] if x)
    cc = clean(c.get("chief_complaint"))
    items = [clean(it.get("text")) for it in (c.get("history_checklist") or [])]
    items = [i for i in items if i]
    item_lines = "".join(rf"\item {tex_escape(i)}" for i in items)
    lines = [
        rf"\section*{{病例：{tex_escape(CASE_ZH.get(case_id, case_id))}}}",
        r"\begin{tcolorbox}[colback=caseblue!6,colframe=caseblue,boxrule=0.7pt,arc=2pt,title=病例背景（评分参考）]",
    ]
    if who:
        lines.append(rf"\textbf{{病人}}：{tex_escape(who)}\par")
    if cc:
        lines.append(rf"\textbf{{主诉}}：{tex_escape(cc)}\par")
    lines.append(r"\textbf{应采集的关键病史（一名到位的学生应问到）：}")
    lines.append(rf"\begin{{itemize}}[leftmargin=1.5em,itemsep=1pt,topsep=2pt]{item_lines}\end{{itemize}}")
    lines.append(r"\end{tcolorbox}")
    lines.append(rf"\noindent 下面是该病例的 \textbf{{{n_enc}}} 次学生问诊，请逐次通读后打分。\par\vspace{{4pt}}")
    return "\n".join(lines)


def transcript_block(idx: int, rec: dict) -> str:
    eid = tex_escape(rec["encounter_id"])
    lines = [
        rf"\subsection*{{第 {idx} 次问诊 \quad\small 编号（务必随分数一起回填）：\texttt{{{eid}}}}}",
        r"\begin{tcolorbox}[colback=gray!4,colframe=gray!40,boxrule=0.5pt,arc=1pt,left=6pt,right=6pt,top=4pt,bottom=4pt]",
    ]
    for t in rec["turns"]:
        text = _MARKER.sub("", t["text"]).strip()
        who = r"\textbf{学生}" if t["speaker"] == "student" else r"\textbf{病人}"
        lines.append(rf"{who}：{tex_escape(text)}\par")
    lines.append(r"\end{tcolorbox}\vspace{3pt}")
    lines.append(r"\begin{center}\begin{tabular}{>{\raggedright\arraybackslash}p{6.5cm} c}")
    lines.append(r"\toprule \textbf{维度} & \textbf{评分 (0--1)} \\ \midrule")
    for name, _ in DIMENSIONS:
        lines.append(rf"{tex_escape(name)} & \scorebox \\")
    lines.append(r"\bottomrule \end{tabular}\end{center}")
    lines.append(r"\noindent 备注（选填）：\rule{12cm}{0.4pt}")
    lines.append(r"\vspace{6pt}\hrule\vspace{6pt}")
    return "\n".join(lines)


def main() -> None:
    by_case = load_transcripts_by_case()
    total = sum(len(v) for v in by_case.values())
    parts = [PREAMBLE, intro()]
    for case_id in CASE_ORDER:
        recs = by_case.get(case_id, [])
        if not recs:
            continue
        parts.append(case_intro(case_id, len(recs)))
        for i, rec in enumerate(recs, 1):
            parts.append(transcript_block(i, rec))
        parts.append(r"\newpage")
    parts.append(r"\end{document}\n")
    OUT_TEX.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT_TEX} ({total} transcripts over {len(CASE_ORDER)} cases)")


if __name__ == "__main__":
    main()
