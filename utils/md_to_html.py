#!/usr/bin/env python3
"""
utils/md_to_html.py — Convert contract review .md reports to a self-contained HTML dashboard.

Usage:
    python md_to_html.py report.md              # outputs report.html
    python md_to_html.py report.md -o out.html  # custom output path
    python md_to_html.py                        # converts latest .md in data/reviews/
"""

import re
import json
import sys
import argparse
from pathlib import Path


# ─────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────

def parse_report(md_path: Path) -> dict:
    raw = md_path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")

    data = {
        "filename": "", "reviewed_at": "", "overall_risk": "",
        "recommendation": "", "risk_summary": {}, "executive_summary": "", "clauses": []
    }

    for line in lines[:20]:
        line = line.strip()
        if "**File:**" in line:
            data["filename"] = re.sub(r"\*\*File:\*\*\s*", "", line).strip()
        elif "**Reviewed:**" in line:
            data["reviewed_at"] = re.sub(r"\*\*Reviewed:\*\*\s*", "", line).strip()
        elif "**Overall Risk:**" in line:
            data["overall_risk"] = re.sub(r"\*\*Overall Risk:\*\*\s*", "", line).strip()
        elif "**Recommendation:**" in line:
            data["recommendation"] = re.sub(r"\*\*Recommendation:\*\*\s*", "", line).strip()

    for line in lines:
        m = re.search(r"🔴 HIGH \| (\d+)", line)
        if m: data["risk_summary"]["high"] = int(m.group(1))
        m = re.search(r"🟡 MEDIUM \| (\d+)", line)
        if m: data["risk_summary"]["medium"] = int(m.group(1))
        m = re.search(r"🔵 LOW \| (\d+)", line)
        if m: data["risk_summary"]["low"] = int(m.group(1))
        m = re.search(r"✅ ACCEPTABLE \| (\d+)", line)
        if m: data["risk_summary"]["acceptable"] = int(m.group(1))
        m = re.search(r"\*\*Total\*\* \| \*\*(\d+)\*\*", line)
        if m: data["risk_summary"]["total"] = int(m.group(1))

    # Executive summary block
    in_exec = False
    exec_lines = []
    for line in lines:
        if "## Executive Summary" in line:
            in_exec = True; continue
        if "## Clause Reviews" in line:
            in_exec = False; continue
        if in_exec:
            exec_lines.append(line)
    data["executive_summary"] = "\n".join(exec_lines).strip()

    # Parse clause blocks
    blocks = re.split(r"\n---\n", raw)
    for block in blocks:
        m = re.search(r"###\s*(🔴|🟡|🔵|✅)\s+(.+?)(?:\n|$)", block)
        if not m:
            continue

        emoji = m.group(1)
        heading = m.group(2).strip()
        risk_map = {"🔴": "HIGH", "🟡": "MEDIUM", "🔵": "LOW", "✅": "ACCEPTABLE"}
        risk_level = risk_map.get(emoji, "LOW")

        clause_type, clause_num = "", ""
        tm = re.search(r"\*\*Type:\*\*\s*(\S+)", block)
        if tm: clause_type = tm.group(1)
        nm = re.search(r"\*\*Clause:\*\*\s*(.+?)(?:  |\n)", block)
        if nm: clause_num = nm.group(1).strip()

        # Issues
        issues = []
        issue_sec = re.search(r"\*\*Issues:\*\*\n\n(.*?)(?=\n\*\*|\n<details|\Z)", block, re.DOTALL)
        if issue_sec:
            for im in re.finditer(r"(\d+)\.\s+(.+?)(?=\n\d+\.|\Z)", issue_sec.group(1), re.DOTALL):
                issue_text = im.group(2).strip()
                ev_m = re.search(r">\s*\*Evidence:\*\s*\"(.+?)\"", issue_text)
                evidence = ev_m.group(1) if ev_m else ""
                clean = re.sub(r"\n\s*>.*", "", issue_text).strip()
                issues.append({"text": clean, "evidence": evidence})

        # Redlines
        redlines = []
        red_sec = re.search(r"\*\*Redlines:\*\*\n\n(.*?)(?=\n\*\*Suggested|\n\*\*Reasoning|\n<details|\Z)", block, re.DOTALL)
        if red_sec:
            rps = re.findall(r"- \*\*Replace:\*\*\s*`?(.+?)`?\s*\n\s*\*\*With:\*\*\s*`?(.+?)`?(?=\n|$)", red_sec.group(1))
            for rp, wp in rps:
                redlines.append({"replace": rp.strip(), "with": wp.strip()})

        # New clauses
        new_clauses = []
        nc_sec = re.search(r"\*\*Suggested New Clauses:\*\*\n\n(.*?)(?=\n\*\*Reasoning|\n<details|\Z)", block, re.DOTALL)
        if nc_sec:
            for ncm in re.finditer(r"\*\*(.+?)\*\*\s*\n\*(.+?)\*\s*\n\n```\n(.*?)```", nc_sec.group(1), re.DOTALL):
                new_clauses.append({"title": ncm.group(1), "reason": ncm.group(2), "text": ncm.group(3).strip()})

        reasoning = ""
        rm2 = re.search(r"\*\*Reasoning:\*\*\s*(.+?)(?=\n<details|\Z)", block, re.DOTALL)
        if rm2: reasoning = rm2.group(1).strip()

        original = ""
        om = re.search(r"<details>.*?```\n(.*?)\n```", block, re.DOTALL)
        if om: original = om.group(1).strip()

        data["clauses"].append({
            "heading": heading, "risk_level": risk_level,
            "clause_type": clause_type, "clause_num": clause_num,
            "issues": issues, "redlines": redlines,
            "new_clauses": new_clauses, "reasoning": reasoning, "original": original
        })

    return data


# ─────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────

def render_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contract Review — {data['filename']}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Mono:wght@400;500&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:          #0c0d10;
  --surface:     #14161a;
  --surface2:    #1c1e24;
  --surface3:    #22252d;
  --border:      #272b33;
  --border2:     #333844;
  --text:        #eaebee;
  --text2:       #a0a6b4;
  --muted:       #636878;
  --accent:      #c9a96e;
  --accent-dim:  rgba(201,169,110,0.12);
  --high:        #e05c5c;
  --high-bg:     rgba(224,92,92,0.08);
  --high-border: rgba(224,92,92,0.25);
  --medium:      #e0a843;
  --medium-bg:   rgba(224,168,67,0.08);
  --medium-border:rgba(224,168,67,0.25);
  --low:         #5b8def;
  --low-bg:      rgba(91,141,239,0.07);
  --low-border:  rgba(91,141,239,0.2);
  --ok:          #52b788;
  --ok-bg:       rgba(82,183,136,0.07);
  --ok-border:   rgba(82,183,136,0.2);
  --sidebar-w:   300px;
  --radius:      7px;
}}

*,*::before,*::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}

body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  line-height: 1.7;
  min-height: 100vh;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border2); border-radius: 3px; }}

/* ══════════════════════════════════════
   LAYOUT
══════════════════════════════════════ */
.shell {{ display: flex; min-height: 100vh; }}

.sidebar {{
  width: var(--sidebar-w);
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  position: fixed;
  top: 0; left: 0; bottom: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  z-index: 200;
}}

.main {{
  margin-left: var(--sidebar-w);
  flex: 1;
  padding: 52px 64px 80px;
  max-width: calc(var(--sidebar-w) + 860px);
}}

/* ══════════════════════════════════════
   SIDEBAR
══════════════════════════════════════ */
.sb-brand {{
  padding: 24px 22px 18px;
  border-bottom: 1px solid var(--border);
}}

.sb-logo {{
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}}

.sb-filename {{
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: var(--text2);
  word-break: break-word;
  line-height: 1.5;
  margin-bottom: 12px;
}}

.sb-risk-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}
.sb-risk-pill.HIGH   {{ background:var(--high-bg);   color:var(--high);   border:1px solid var(--high-border); }}
.sb-risk-pill.MEDIUM {{ background:var(--medium-bg); color:var(--medium); border:1px solid var(--medium-border); }}
.sb-risk-pill.LOW    {{ background:var(--low-bg);    color:var(--low);    border:1px solid var(--low-border); }}

/* Stat grid */
.sb-stats {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--border);
}}

.stat-cell {{
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 10px 8px;
  text-align: center;
}}

.stat-num {{
  font-family: 'Playfair Display', serif;
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 4px;
}}
.stat-num.h {{ color: var(--high); }}
.stat-num.m {{ color: var(--medium); }}
.stat-num.l {{ color: var(--low); }}
.stat-num.o {{ color: var(--ok); }}

.stat-label {{
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}}

/* Search */
.sb-search {{
  padding: 10px 22px;
  border-bottom: 1px solid var(--border);
}}

.search-input {{
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  padding: 7px 11px;
  outline: none;
  transition: border-color 0.15s;
}}
.search-input:focus {{ border-color: var(--accent); }}
.search-input::placeholder {{ color: var(--muted); }}

/* Filter pills */
.sb-filters {{
  padding: 10px 22px 6px;
  border-bottom: 1px solid var(--border);
}}

.filter-heading {{
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 8px;
}}

.filter-btn {{
  width: 100%;
  background: none;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text2);
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  padding: 6px 11px;
  text-align: left;
  cursor: pointer;
  transition: all 0.14s;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}}
.filter-btn:hover {{ border-color: var(--border2); color: var(--text); background: var(--surface2); }}
.filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }}

.filter-count {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  opacity: 0.7;
}}

/* Clause nav list */
.sb-nav {{ flex: 1; overflow-y: auto; padding: 6px 0 20px; }}

.nav-section-title {{
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 10px 22px 4px;
}}

.nav-item {{
  padding: 7px 22px 7px 20px;
  cursor: pointer;
  border-left: 2px solid transparent;
  display: flex;
  align-items: center;
  gap: 9px;
  transition: all 0.12s;
}}
.nav-item:hover {{ background: var(--surface2); }}
.nav-item.active {{ border-left-color: var(--accent); background: var(--surface2); }}
.nav-item.hidden {{ display: none; }}

.nav-dot {{
  width: 6px; height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.nav-dot.HIGH   {{ background: var(--high); box-shadow: 0 0 5px var(--high); }}
.nav-dot.MEDIUM {{ background: var(--medium); }}
.nav-dot.LOW    {{ background: var(--low); }}
.nav-dot.ACCEPTABLE {{ background: var(--ok); }}

.nav-text {{
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}}
.nav-item:hover .nav-text,
.nav-item.active .nav-text {{ color: var(--text); }}

/* ══════════════════════════════════════
   MAIN CONTENT
══════════════════════════════════════ */
.page-header {{
  margin-bottom: 52px;
}}

.page-eyebrow {{
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}}

.page-title {{
  font-family: 'Playfair Display', serif;
  font-size: 34px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 12px;
  line-height: 1.15;
  letter-spacing: -0.01em;
}}

.page-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px 20px;
  font-size: 13px;
  color: var(--text2);
  margin-bottom: 20px;
}}

.page-meta span {{ display: flex; align-items: center; gap: 5px; }}

.rec-badge {{
  display: inline-block;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  background: var(--accent-dim);
  color: var(--accent);
  border: 1px solid rgba(201,169,110,0.25);
}}

/* Section title */
.section {{ margin-bottom: 52px; }}

.section-title {{
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 22px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: baseline;
  gap: 12px;
}}

.section-count {{
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  color: var(--muted);
  font-weight: 400;
}}

/* ── Executive summary ── */
.exec-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px 36px;
  line-height: 1.85;
}}

.exec-card h3 {{
  font-family: 'Playfair Display', serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
  margin: 24px 0 10px;
}}
.exec-card h3:first-child {{ margin-top: 0; }}
.exec-card p {{ color: var(--text2); margin-bottom: 12px; }}
.exec-card strong {{ color: var(--text); font-weight: 500; }}
.exec-card em {{ color: var(--accent); font-style: normal; font-weight: 500; }}
.exec-card ul {{ padding-left: 22px; margin: 8px 0 14px; }}
.exec-card li {{ color: var(--text2); margin-bottom: 6px; }}

/* ── Clause cards ── */
.clause-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
  scroll-margin-top: 24px;
  animation: fadeUp 0.35s ease both;
}}
.clause-card:hover {{ border-color: var(--border2); }}
.clause-card.HIGH    {{ border-left: 3px solid var(--high); }}
.clause-card.MEDIUM  {{ border-left: 3px solid var(--medium); }}
.clause-card.LOW     {{ border-left: 3px solid var(--low); }}
.clause-card.ACCEPTABLE {{ border-left: 3px solid var(--ok); }}
.clause-card.hidden  {{ display: none; animation: none; }}

.clause-header {{
  padding: 14px 18px;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  user-select: none;
  transition: background 0.12s;
}}
.clause-header:hover {{ background: var(--surface2); }}

.risk-chip {{
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-top: 3px;
}}
.risk-chip.HIGH    {{ background:var(--high-bg);   color:var(--high);   border:1px solid var(--high-border); }}
.risk-chip.MEDIUM  {{ background:var(--medium-bg); color:var(--medium); border:1px solid var(--medium-border); }}
.risk-chip.LOW     {{ background:var(--low-bg);    color:var(--low);    border:1px solid var(--low-border); }}
.risk-chip.ACCEPTABLE {{ background:var(--ok-bg);  color:var(--ok);     border:1px solid var(--ok-border); }}

.clause-info {{ flex: 1; min-width: 0; }}

.clause-heading {{
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.clause-sub {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}}

.clause-tag {{
  padding: 1px 7px;
  border-radius: 3px;
  font-size: 10px;
  background: var(--surface3);
  color: var(--muted);
  border: 1px solid var(--border);
}}

.chevron {{
  color: var(--muted);
  font-size: 11px;
  transition: transform 0.2s;
  flex-shrink: 0;
  margin-top: 5px;
}}
.clause-card.open .chevron {{ transform: rotate(180deg); }}

/* Clause body */
.clause-body {{
  display: none;
  padding: 0 20px 20px 20px;
  border-top: 1px solid var(--border);
}}
.clause-card.open .clause-body {{ display: block; }}

/* Sub-section labels */
.body-label {{
  font-size: 10px;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 18px 0 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.body-label::after {{
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}}

/* Issue items */
.issue-item {{
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 11px 14px;
  margin-bottom: 7px;
  font-size: 13px;
  color: var(--text2);
  line-height: 1.65;
}}
.issue-num {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  margin-right: 6px;
}}

.evidence-quote {{
  margin-top: 8px;
  padding: 7px 12px;
  background: var(--accent-dim);
  border-left: 2px solid var(--accent);
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--text2);
  border-radius: 0 4px 4px 0;
  line-height: 1.65;
}}
.evidence-label {{
  font-size: 10px;
  color: var(--accent);
  margin-bottom: 3px;
  letter-spacing: 0.05em;
}}

/* Redlines */
.redline-block {{ margin-bottom: 10px; border-radius: 5px; overflow: hidden; }}

.redline-remove {{
  background: rgba(224,92,92,0.07);
  border: 1px solid rgba(224,92,92,0.18);
  border-bottom: none;
  padding: 10px 14px;
  font-family: 'DM Mono', monospace;
  font-size: 11.5px;
  color: #e09090;
  line-height: 1.7;
  position: relative;
}}
.redline-remove::before {{
  content: '−';
  color: var(--high);
  font-weight: 700;
  margin-right: 8px;
  font-size: 14px;
}}

.redline-add {{
  background: rgba(82,183,136,0.07);
  border: 1px solid rgba(82,183,136,0.18);
  padding: 10px 14px;
  font-family: 'DM Mono', monospace;
  font-size: 11.5px;
  color: #7ecfaa;
  line-height: 1.7;
}}
.redline-add::before {{
  content: '+';
  color: var(--ok);
  font-weight: 700;
  margin-right: 8px;
  font-size: 14px;
}}

/* New clauses */
.new-clause-block {{
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 5px;
  overflow: hidden;
  margin-bottom: 10px;
}}
.new-clause-head {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}}
.new-clause-title {{
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  margin-bottom: 2px;
}}
.new-clause-reason {{
  font-size: 12px;
  color: var(--muted);
  font-style: italic;
}}
.new-clause-text {{
  padding: 12px 14px;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--text2);
  white-space: pre-wrap;
  line-height: 1.75;
  max-height: 220px;
  overflow-y: auto;
  background: #0a0b0d;
}}

/* Reasoning */
.reasoning-box {{
  margin-top: 14px;
  padding: 12px 16px;
  background: var(--accent-dim);
  border: 1px solid rgba(201,169,110,0.18);
  border-radius: 5px;
  font-size: 13px;
  color: var(--text2);
  line-height: 1.7;
}}
.reasoning-label {{
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 5px;
}}

/* Original text */
.original-btn {{
  background: none;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--muted);
  font-family: 'DM Sans', sans-serif;
  font-size: 11px;
  padding: 4px 11px;
  cursor: pointer;
  margin-top: 14px;
  transition: all 0.14s;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}}
.original-btn:hover {{ border-color: var(--border2); color: var(--text); }}

.original-text {{
  display: none;
  margin-top: 8px;
  padding: 14px;
  background: #080909;
  border: 1px solid var(--border);
  border-radius: 5px;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  white-space: pre-wrap;
  line-height: 1.8;
  max-height: 280px;
  overflow-y: auto;
}}
.original-text.open {{ display: block; }}

/* ── Animations ── */
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

/* ── No results ── */
.no-results {{
  text-align: center;
  padding: 48px 24px;
  color: var(--muted);
  font-size: 13px;
  display: none;
}}
</style>
</head>
<body>
<div class="shell">

<!-- ══ SIDEBAR ══ -->
<aside class="sidebar">
  <div class="sb-brand">
    <div class="sb-logo">Contract Review</div>
    <div class="sb-filename" id="sb-filename"></div>
    <div id="sb-risk-pill" class="sb-risk-pill"></div>
  </div>

  <div class="sb-stats">
    <div class="stat-cell"><div class="stat-num h" id="stat-h">0</div><div class="stat-label">High</div></div>
    <div class="stat-cell"><div class="stat-num m" id="stat-m">0</div><div class="stat-label">Medium</div></div>
    <div class="stat-cell"><div class="stat-num l" id="stat-l">0</div><div class="stat-label">Low</div></div>
    <div class="stat-cell"><div class="stat-num o" id="stat-o">0</div><div class="stat-label">OK</div></div>
  </div>

  <div class="sb-search">
    <input class="search-input" type="text" placeholder="Search clauses…" id="search-input" autocomplete="off">
  </div>

  <div class="sb-filters">
    <div class="filter-heading">Filter</div>
    <button class="filter-btn active" data-f="ALL">All clauses <span class="filter-count" id="fc-all">—</span></button>
    <button class="filter-btn" data-f="HIGH">🔴 High <span class="filter-count" id="fc-high">—</span></button>
    <button class="filter-btn" data-f="MEDIUM">🟡 Medium <span class="filter-count" id="fc-med">—</span></button>
    <button class="filter-btn" data-f="LOW">🔵 Low <span class="filter-count" id="fc-low">—</span></button>
    <button class="filter-btn" data-f="ACCEPTABLE">✅ Acceptable <span class="filter-count" id="fc-ok">—</span></button>
  </div>

  <div class="sb-nav">
    <div class="nav-section-title">Clauses</div>
    <div id="clause-nav"></div>
  </div>
</aside>

<!-- ══ MAIN ══ -->
<main class="main">

  <div class="page-header">
    <div class="page-eyebrow">Contract Review Report</div>
    <div class="page-title" id="main-title">Loading…</div>
    <div class="page-meta">
      <span id="meta-date"></span>
      <span id="meta-clauses"></span>
    </div>
    <span class="rec-badge" id="rec-badge"></span>
  </div>

  <div class="section" id="section-exec">
    <div class="section-title">Executive Summary</div>
    <div class="exec-card" id="exec-content"></div>
  </div>

  <div class="section">
    <div class="section-title">
      Clause Reviews
      <span class="section-count" id="section-clause-count"></span>
    </div>
    <div id="clauses-container"></div>
    <div class="no-results" id="no-results">No clauses match your filter.</div>
  </div>

</main>
</div>

<script>
const R = {data_json};

function esc(s) {{
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

function md(s) {{
  if (!s) return '';
  return s
    .replace(/[*][*](.+?)[*][*]/g,'<strong>$1</strong>')
    .replace(/[*](.+?)[*]/g,'<em>$1</em>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h3>$1</h3>')
    .replace(/^- (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>[\\s\\S]*?<\\/li>\\n?)+/g, s=>'<ul>'+s+'</ul>')
    .replace(/\\n\\n+/g,'</p><p>')
    .replace(/^(?!<)(.+)$/gm,'$1')
    .replace(/<p><\\/p>/g,'');
}}

// ── Populate header ──
document.getElementById('sb-filename').textContent  = R.filename;
document.getElementById('main-title').textContent   = R.filename;
document.getElementById('meta-date').textContent    = '📅 ' + R.reviewed_at;
document.getElementById('rec-badge').textContent    = R.recommendation;

const rs = R.risk_summary;
document.getElementById('stat-h').textContent = rs.high   || 0;
document.getElementById('stat-m').textContent = rs.medium || 0;
document.getElementById('stat-l').textContent = rs.low    || 0;
document.getElementById('stat-o').textContent = rs.acceptable || 0;
document.getElementById('meta-clauses').textContent = '📋 ' + (rs.total || 0) + ' clauses';
document.getElementById('section-clause-count').textContent = rs.total || 0;

document.getElementById('fc-all').textContent  = rs.total      || 0;
document.getElementById('fc-high').textContent = rs.high       || 0;
document.getElementById('fc-med').textContent  = rs.medium     || 0;
document.getElementById('fc-low').textContent  = rs.low        || 0;
document.getElementById('fc-ok').textContent   = rs.acceptable || 0;

const riskPill = document.getElementById('sb-risk-pill');
const riskEmoji = {{HIGH:'🔴',MEDIUM:'🟡',LOW:'🔵'}}[R.overall_risk] || '';
riskPill.className = 'sb-risk-pill ' + R.overall_risk;
riskPill.textContent = riskEmoji + ' ' + R.overall_risk + ' RISK';

// ── Executive summary ──
document.getElementById('exec-content').innerHTML = '<p>' + md(R.executive_summary) + '</p>';

// ── Build clauses ──
const nav   = document.getElementById('clause-nav');
const cont  = document.getElementById('clauses-container');

R.clauses.forEach((c, idx) => {{
  const id = 'c' + idx;

  // Nav
  const ni = document.createElement('div');
  ni.className = 'nav-item';
  ni.dataset.idx  = idx;
  ni.dataset.risk = c.risk_level;
  ni.innerHTML = `<span class="nav-dot ${{c.risk_level}}"></span><span class="nav-text">${{esc(c.heading)}}</span>`;
  ni.addEventListener('click', () => {{
    document.getElementById(id).scrollIntoView({{behavior:'smooth',block:'start'}});
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    ni.classList.add('active');
  }});
  nav.appendChild(ni);

  // Body content
  let body = '';

  if (c.issues && c.issues.length) {{
    body += `<div class="body-label">Issues Found</div>`;
    c.issues.forEach((iss, ii) => {{
      body += `<div class="issue-item">
        <span class="issue-num">${{ii+1}}.</span>${{esc(iss.text)}}`;
      if (iss.evidence) body += `
        <div class="evidence-quote">
          <div class="evidence-label">Evidence</div>
          "${{esc(iss.evidence)}}"
        </div>`;
      body += `</div>`;
    }});
  }}

  if (c.redlines && c.redlines.length) {{
    body += `<div class="body-label">Redlines</div>`;
    c.redlines.forEach(rd => {{
      body += `<div class="redline-block">
        <div class="redline-remove">${{esc(rd.replace)}}</div>
        <div class="redline-add">${{esc(rd.with)}}</div>
      </div>`;
    }});
  }}

  if (c.new_clauses && c.new_clauses.length) {{
    body += `<div class="body-label">Suggested New Clauses</div>`;
    c.new_clauses.forEach(nc => {{
      body += `<div class="new-clause-block">
        <div class="new-clause-head">
          <div class="new-clause-title">${{esc(nc.title)}}</div>
          <div class="new-clause-reason">${{esc(nc.reason)}}</div>
        </div>
        <div class="new-clause-text">${{esc(nc.text)}}</div>
      </div>`;
    }});
  }}

  if (c.reasoning) {{
    body += `<div class="reasoning-box">
      <div class="reasoning-label">Reasoning</div>
      ${{esc(c.reasoning)}}
    </div>`;
  }}

  if (c.original) {{
    body += `<button class="original-btn" onclick="toggleOrig(this)">▸ Show original text</button>
      <div class="original-text">${{esc(c.original)}}</div>`;
  }}

  const issCount   = (c.issues||[]).length;
  const hasRedline = (c.redlines||[]).length > 0;
  const hasNew     = (c.new_clauses||[]).length > 0;
  const tags = [
    c.clause_type ? `<span class="clause-tag">${{esc(c.clause_type)}}</span>` : '',
    c.clause_num  ? `<span class="clause-tag">§${{esc(c.clause_num)}}</span>` : '',
    issCount      ? `<span class="clause-tag">${{issCount}} issue${{issCount>1?'s':''}}</span>` : '',
    hasRedline    ? `<span class="clause-tag">redlines</span>` : '',
    hasNew        ? `<span class="clause-tag">new clauses</span>` : '',
  ].filter(Boolean).join('');

  const card = document.createElement('div');
  card.className = 'clause-card ' + c.risk_level + (c.risk_level==='HIGH'||c.risk_level==='MEDIUM'?' open':'');
  card.id = id;
  card.dataset.risk    = c.risk_level;
  card.dataset.heading = c.heading.toLowerCase();
  card.style.animationDelay = (idx * 15) + 'ms';

  card.innerHTML = `
    <div class="clause-header" onclick="this.closest('.clause-card').classList.toggle('open')">
      <span class="risk-chip ${{c.risk_level}}">${{c.risk_level}}</span>
      <div class="clause-info">
        <div class="clause-heading">${{esc(c.heading)}}</div>
        <div class="clause-sub">${{tags}}</div>
      </div>
      <span class="chevron">▾</span>
    </div>
    <div class="clause-body">${{body}}</div>`;

  cont.appendChild(card);
}});

// ── Filter ──
let activeFilter = 'ALL';
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    activeFilter = btn.dataset.f;
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    applyFilters();
  }});
}});

// ── Search ──
document.getElementById('search-input').addEventListener('input', applyFilters);

function applyFilters() {{
  const q = document.getElementById('search-input').value.toLowerCase().trim();
  let visible = 0;
  document.querySelectorAll('.clause-card').forEach((card, i) => {{
    const riskOk   = activeFilter === 'ALL' || card.dataset.risk === activeFilter;
    const searchOk = !q || card.dataset.heading.includes(q);
    const show = riskOk && searchOk;
    card.classList.toggle('hidden', !show);
    document.querySelectorAll('.nav-item')[i]?.classList.toggle('hidden', !show);
    if (show) visible++;
  }});
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
  document.getElementById('section-clause-count').textContent = visible;
}}

function toggleOrig(btn) {{
  const el = btn.nextElementSibling;
  el.classList.toggle('open');
  btn.textContent = el.classList.contains('open') ? '▾ Hide original text' : '▸ Show original text';
}}

// Scroll spy
const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      const idx = e.target.id.replace('c','');
      document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
      document.querySelectorAll('.nav-item')[parseInt(idx)]?.classList.add('active');
    }}
  }});
}}, {{threshold: 0.3}});

document.querySelectorAll('.clause-card').forEach(c => observer.observe(c));
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def find_latest_md() -> Path:
    reviews_dir = Path(__file__).parent.parent / "data" / "reviews"
    mds = sorted(reviews_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mds:
        raise FileNotFoundError(f"No .md files found in {reviews_dir}")
    return mds[0]


def main():
    parser = argparse.ArgumentParser(description="Convert contract review .md to HTML dashboard")
    parser.add_argument("input", nargs="?", help=".md file to convert (default: latest in data/reviews/)")
    parser.add_argument("-o", "--output", help="Output .html path (default: same name as input)")
    parser.add_argument("--open", action="store_true", help="Open in browser after converting")
    args = parser.parse_args()

    md_path = Path(args.input) if args.input else find_latest_md()
    if not md_path.exists():
        print(f"Error: {md_path} not found"); sys.exit(1)

    out_path = Path(args.output) if args.output else md_path.with_suffix(".html")

    print(f"Parsing  {md_path.name}…")
    data = parse_report(md_path)
    print(f"  {len(data['clauses'])} clauses · overall {data['overall_risk']}")

    print(f"Rendering {out_path.name}…")
    html = render_html(data)
    out_path.write_text(html, encoding="utf-8")
    print(f"  Done → {out_path}")

    if args.open:
        import webbrowser
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
