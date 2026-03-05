"""
utils/report_exporter.py — Export review reports to Markdown and JSON.
"""

import json
import re
from pathlib import Path
from loguru import logger

# Emoji constants (unicode escapes for Windows compatibility)
E_HIGH   = "\U0001f534"  # 🔴
E_MEDIUM = "\U0001f7e1"  # 🟡
E_LOW    = "\U0001f535"  # 🔵
E_OK     = "\u2705"      # ✅
E_GREY   = "\u26aa"      # ⚪
E_PIN    = "\U0001f4cc"  # 📌
E_X      = "\u274c"      # ❌

# Signature/execution fragment pattern — omit from report entirely
_SIG_SKIP_RE = re.compile(
    r"^(signed|printed|approved as to|consultant\s*consultant|commission\s*commission"
    r"|transportation commission|distribution\s*:|exhibit\s+[ab]|fee schedule"
    r"|in witness whereof)",
    re.IGNORECASE,
)


class ReportExporter:

    # ------------------------------------------------------------------
    # JSON Export
    # ------------------------------------------------------------------

    def export_json(self, report, output_path: Path) -> Path:
        data = {
            "filename":          report.filename,
            "reviewed_at":       report.reviewed_at,
            "overall_risk":      report.overall_risk,
            "recommendation":    report.recommendation,
            "metadata":          report.metadata,
            "summary": {
                "total_clauses": report.total_clauses,
                "high_risk":     report.high_risk_count,
                "medium_risk":   report.medium_risk_count,
                "low_risk":      report.low_risk_count,
                "acceptable":    report.acceptable_count,
            },
            "executive_summary": report.executive_summary,
            "clause_reviews": [
                {
                    "clause_id":          r.clause_id,
                    "number":             r.number,
                    "heading":            r.heading,
                    "clause_type":        r.clause_type,
                    "risk_level":         r.risk_level,
                    "page_num":           getattr(r, "page_num", None),
                    "issues":             r.issues,
                    "evidence_quotes":    getattr(r, "evidence_quotes", []),
                    "redlines":           getattr(r, "redlines", []),
                    "new_clauses":        getattr(r, "new_clauses", []),
                    "redline_suggestion": r.redline_suggestion,
                    "reasoning":          r.reasoning,
                    "original_text":      r.original_text[:500],
                }
                for r in report.clause_reviews
            ],
        }
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"JSON report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Markdown Export
    # ------------------------------------------------------------------

    def export_markdown(self, report, output_path: Path) -> Path:
        lines = []
        m = report.metadata
        risk_icon = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW}.get(report.overall_risk, E_GREY)

        def cmeta(val):
            if val is None:
                return "N/A"
            s = str(val).strip()
            return "N/A" if s.lower() in ("null", "none", "") else s

        # Header
        lines += [
            "# Contract Review Report", "",
            f"**File:** {report.filename}  ",
            f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}  ",
            f"**Overall Risk:** {risk_icon} {report.overall_risk}  ",
            f"**Recommendation:** {report.recommendation}",
            "",
        ]

        # Performance metrics (only if timing data exists and is non-zero)
        timing = m.get("timing", {})
        if timing and timing.get("total_seconds", 0) > 0:
            lines += [
                "## Performance Metrics", "",
                "| Metric | Time |",
                "|--------|------|",
                f"| Total Processing Time | {timing.get('total_seconds', 0):.2f}s |",
                f"| Document Parsing | {timing.get('parse_seconds', 0):.2f}s |",
                f"| Clause Segmentation | {timing.get('segment_seconds', 0):.2f}s |",
                f"| Metadata Extraction | {timing.get('metadata_seconds', 0):.2f}s |",
                f"| Clause Review | {timing.get('review_seconds', 0):.2f}s |",
                f"| Executive Summary | {timing.get('summary_seconds', 0):.2f}s |",
                f"| Average per Clause | {timing.get('avg_seconds_per_clause', 0):.2f}s |",
                "",
            ]

        # Contract Details
        lines += [
            "## Contract Details", "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Type | {cmeta(m.get('contract_type'))} |",
            f"| Parties | {', '.join(m.get('parties', [])) or 'N/A'} |",
            f"| Effective Date | {cmeta(m.get('effective_date'))} |",
            f"| Expiration Date | {cmeta(m.get('expiration_date'))} |",
            f"| Governing Law | {cmeta(m.get('governing_law'))} |",
            f"| Auto-Renewal | {cmeta(m.get('auto_renewal'))} |",
            "",
        ]

        # Risk Summary
        lines += [
            "## Risk Summary", "",
            "| Risk Level | Count |",
            "|------------|-------|",
            f"| {E_HIGH} HIGH | {report.high_risk_count} |",
            f"| {E_MEDIUM} MEDIUM | {report.medium_risk_count} |",
            f"| {E_LOW} LOW | {report.low_risk_count} |",
            f"| {E_OK} ACCEPTABLE | {report.acceptable_count} |",
            f"| **Total** | **{report.total_clauses}** |",
            "",
        ]

        # Executive Summary
        summary = re.sub(
            r"^\*\*Executive Summary[^*]*\*\*\s*", "",
            report.executive_summary or "",
            flags=re.IGNORECASE,
        ).strip()
        if summary:
            lines += ["## Executive Summary", "", summary, ""]

        # Clauses grouped by risk
        SECTIONS = [
            ("HIGH",       f"## {E_HIGH} High Risk Clauses",    False),
            ("MEDIUM",     f"## {E_MEDIUM} Medium Risk Clauses", False),
            ("LOW",        f"## {E_LOW} Low Risk Clauses",       True),
            ("ACCEPTABLE", f"## {E_OK} Acceptable Clauses",      True),
        ]
        for level, sec_heading, compact in SECTIONS:
            revs = [r for r in report.clause_reviews if r.risk_level == level]
            if not revs:
                continue
            lines += [sec_heading, ""]
            for r in revs:
                clause_lines = self._format_clause(r, compact=compact)
                if clause_lines:   # _format_clause returns [] for fragments to skip
                    lines += clause_lines

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Markdown report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Clause Formatter
    # ------------------------------------------------------------------

    def _format_clause(self, review, compact=False) -> list:
        CE = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW, "ACCEPTABLE": E_OK}
        emoji = CE.get(review.risk_level, E_GREY)

        # Clean and strip PDF artefact prefixes
        raw_heading = self._clean(review.heading or review.clause_type or review.clause_id)
        heading     = self._strip_pdf_prefix(raw_heading)
        if len(heading) > 72:
            heading = heading[:69] + "..."

        # Skip signature/execution fragments entirely
        if _SIG_SKIP_RE.match(heading.strip()) or _SIG_SKIP_RE.match((review.heading or "").strip()):
            return []

        number  = f"{review.number} " if review.number else ""
        esc_tag = " *(risk escalated)*" if getattr(review, "escalated", False) else ""
        page    = getattr(review, "page_num", None)
        page_ok = page and str(page).strip() not in ("0", "None", "null", "")

        lines = [f"### {emoji} {number}{heading}{esc_tag}", ""]

        # ── Compact view (LOW / ACCEPTABLE) ──────────────────────────
        if compact:
            if page_ok:
                lines += [f"**Location:** Page {page}  "]
            recital_badge = " *(recital — narrative only)*" if getattr(review, "escalated", False) is False and "Recital" in (review.reasoning or "") else ""
            lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}{recital_badge}", ""]
            if review.issues:
                lines += [f"_{self._clean(review.issues[0])}_", ""]
            lines += ["---", ""]
            return lines

        # ── Full view (HIGH / MEDIUM) ─────────────────────────────────
        lines += [f"**Risk Level:** {review.risk_level}"]
        lines += [f"**Clause Type:** {review.clause_type}"]
        if page_ok:
            lines += [f"**Location:** Page {page}"]
        lines += [""]

        # Issues + Evidence
        if review.issues:
            lines += ["**Issues Found:**", ""]
            evidence = getattr(review, "evidence_quotes", [])

            for i, issue in enumerate(review.issues):
                clean_issue = self._clean(issue)
                # Avoid double-bold if LLM already added **
                clean_issue = re.sub(r"^\*\*(.+?)\*\*\s*[—-]?\s*", r"\1 — ", clean_issue, count=1) \
                    if re.match(r"^\*\*", clean_issue) else clean_issue

                if " — " in clean_issue:
                    label, detail = clean_issue.split(" — ", 1)
                    issue_line = f"**{label.strip()}** — {detail.strip()}"
                elif " - " in clean_issue:
                    label, detail = clean_issue.split(" - ", 1)
                    issue_line = f"**{label.strip()}** - {detail.strip()}"
                else:
                    issue_line = f"**{clean_issue}**"

                lines += [f"**Issue {i+1}:** {issue_line}", ""]

                ev_raw = evidence[i] if i < len(evidence) else ""
                ev     = self._clean_evidence(ev_raw)

                if ev != "N/A":
                    line_ref  = self._find_line_ref(ev, getattr(review, "original_text", ""))
                    loc_parts = []
                    if page_ok:                    loc_parts.append(f"Page {page}")
                    if line_ref and line_ref > 0:  loc_parts.append(f"Line ~{line_ref}")
                    loc = f" *({', '.join(loc_parts)})*" if loc_parts else ""
                    lines += [
                        f"\n> {E_PIN} **Evidence{loc}:**",
                        f'> *"{ev}"*',
                        "",
                    ]
                else:
                    lines += [
                        f"\n> {E_PIN} **Evidence:** N/A — no direct quote found in this clause",
                        "",
                    ]

        # Suggested Changes (Redlines)
        redlines = getattr(review, "redlines", [])
        good = [rd for rd in redlines
                if self._is_real(rd.get("replace", "")) and self._is_real(rd.get("with", ""))]
        if good:
            lines += ["**Suggested Changes:**", ""]
            for j, rd in enumerate(good, 1):
                old_text  = self._clean_part(rd.get("replace", ""))
                new_text  = self._clean_part(rd.get("with", ""))
                full_sent = self._find_sentence(old_text, getattr(review, "original_text", ""))

                lines += [f"**Change {j} of {len(good)}:**", ""]
                if full_sent and full_sent.lower().strip() != old_text.lower().strip():
                    lines += [
                        "> **Contract context** — full sentence where this language appears:",
                        f'> *"{full_sent}"*',
                        "",
                    ]

                # Match redline to the most relevant issue
                why_text = self._best_why_text(old_text, review.issues, j)

                lines += [
                    "| | |",
                    "|---|---|",
                    f"| {E_X} **Current language** | {old_text} |",
                    f"| {E_OK} **Recommended change** | {new_text} |",
                    "",
                    f"> **Why:** {why_text}",
                    "",
                ]
        elif review.redline_suggestion:
            rl = self._clean(review.redline_suggestion)
            if rl:
                lines += ["**Suggested Change:**", "", f"> {rl}", ""]

        # Proposed New Clauses
        new_clauses = getattr(review, "new_clauses", [])
        # Filter out garbage new clauses (no text, or text is just placeholders/bullets)
        real_new_clauses = []
        for nc in new_clauses:
            text = nc.get("text", "").strip().strip('"').strip("**").strip("-").strip()
            if not text or len(text) < 20:
                continue
            # Skip if title or text is just a leaked format artifact
            title = nc.get("title", "")
            _junk = re.compile(r"^[-*]{1,3}$|^\s*$", re.MULTILINE)
            if _junk.match(title.strip()):
                continue
            # Clean up title: strip trailing "\n-**" artifacts
            title = re.sub(r"[\n\r]*[-*]+\s*$", "", title).strip().strip('"')
            real_new_clauses.append({"title": title, "reason": nc.get("reason", ""), "text": text})

        if real_new_clauses:
            lines += [
                "**Proposed New Clauses:**", "",
                "> These clauses do not exist in the current contract.",
                "> They should be **added** to address the missing obligations identified above.",
                "",
            ]
            for nc in real_new_clauses:
                title  = nc.get("title", "New Clause")
                reason = nc.get("reason", "")
                text   = nc.get("text", "")
                lines += [f"**✏ Proposed: {title}**", ""]
                if reason:
                    lines += [f"> **Why needed:** {reason}", ""]
                lines += ["```", text, "```", ""]

        # Overall Assessment
        if review.reasoning:
            r = self._clean(review.reasoning)
            if r:
                lines += ["**Overall Assessment:**", "", r, ""]

        lines += ["---", ""]
        return lines

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _strip_pdf_prefix(self, heading: str) -> str:
        """Strip single-letter PDF column-marker prefixes: 'S. ', 'N. ', 'M. M. '."""
        cleaned = re.sub(r"^([A-Z]\.\s+)+", "", heading).strip()
        # Collapse repeated words: "SIGNED SIGNED" → "SIGNED"
        parts = cleaned.split()
        if len(parts) >= 2 and parts[0].upper() == parts[1].upper():
            cleaned = " ".join(parts[: len(parts) // 2])
        return cleaned or heading

    def _best_why_text(self, old_text: str, issues_list: list, fallback_idx: int) -> str:
        """Find the issue that best explains why old_text is being changed."""
        if not issues_list:
            return "This change addresses the issue identified above."

        old_lower  = old_text.lower()
        best_issue = None
        best_score = -1
        for iss in issues_list:
            shared = sum(1 for w in old_lower.split() if len(w) > 3 and w in iss.lower())
            if shared > best_score:
                best_score = shared
                best_issue = iss

        # Positional fallback
        if best_score == 0 and fallback_idx - 1 < len(issues_list):
            best_issue = issues_list[fallback_idx - 1]

        if not best_issue:
            return "This change addresses the issue identified above."

        raw = self._clean(best_issue)
        raw = re.sub(r"^\*\*(.+?)\*\*\s*[—-]?\s*", r"\1: ", raw, count=1)
        for sep in (" — ", " - ", ": "):
            if sep in raw:
                return raw.split(sep, 1)[1].strip()
        return raw

    def _find_line_ref(self, evidence: str, original_text: str) -> int:
        if not evidence or not original_text:
            return 0
        key = evidence[:40].lower().strip()
        for i, line in enumerate(original_text.split("\n"), 1):
            if key in line.lower():
                return i
        return 0

    def _find_sentence(self, fragment: str, original_text: str) -> str:
        if not fragment or not original_text:
            return ""
        flat = re.sub(r"-[ \t]*\n[ \t]*", "", original_text)
        flat = re.sub(r"\n", " ", flat)
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", flat)
        frag_lower = fragment.lower().strip()
        for sent in sentences:
            if frag_lower in sent.lower():
                sent = sent.strip()
                if len(sent) > 220:
                    idx = sent.lower().find(frag_lower)
                    s = max(0, idx - 70)
                    e = min(len(sent), idx + len(fragment) + 70)
                    sent = ("..." if s > 0 else "") + sent[s:e] + ("..." if e < len(sent) else "")
                return sent
        return ""

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"^\s*\*\*\s*", "", text)
        text = re.sub(r"\s*\*\*\s*$", "", text)
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _clean_evidence(self, ev: str) -> str:
        if not ev:
            return "N/A"
        ev = ev.strip()
        if ev.lower() in ("none", "none.", "n/a", "-", "") or ev.lower().startswith("none ("):
            return "N/A"
        ev = re.split(r"\s*IMPACT\s*:", ev, maxsplit=1)[0]
        ev = re.sub(r"-[ \t]*\n[ \t]*", "", ev)
        ev = ev.rstrip(" -\n").strip()
        if ev.endswith('"') and ev.count('"') % 2 != 0:
            ev = ev[:-1].strip()
        if ev.startswith('"') and ev.count('"') % 2 != 0:
            ev = ev[1:].strip()
        return ev or "N/A"

    def _clean_part(self, text: str) -> str:
        text = re.sub(r"\*\*", "", text)
        text = re.sub(r'"\s*$', "", text)
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
        return text.strip()

    def _is_real(self, text: str) -> bool:
        return text.strip().lower() not in ("", "none", "-", "n/a")


# Singleton
exporter = ReportExporter()