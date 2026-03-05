"""
core/review_pipeline.py — Contract Review Pipeline

Flow:
  ParsedDocument → Clauses → Metadata → Per-clause review → Summary Report

Key improvements:
- Two-pass review (Pass 1: evidence extraction, Pass 2: full analysis)
- max_tokens=2048 for clause review (prevents cut-off clauses)
- max_tokens=1500 for executive summary
- Stronger signature/fragment filter
- Tightened hallucination evidence filter (85% match)
- Metadata extraction uses full 8000 chars (captures governing_law)
- Contradiction resolver excludes more noisy types
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from core.llm import llm
from core.config import config
from ingestion.parser import parser, ParsedDocument
from ingestion.segmenter import segmenter, Clause
from prompts.review_prompts import (
    SYSTEM_CONTRACT_REVIEWER,
    SYSTEM_METADATA_EXTRACTOR,
    prompt_extract_metadata,
    prompt_extract_evidence,
    prompt_classify_clause,
    prompt_review_clause,
    prompt_contract_summary,
)

# RAG retriever (optional — graceful fallback if not configured)
try:
    from rag.retriever import retriever
    RAG_ENABLED = True
except Exception as _rag_err:
    retriever = None
    RAG_ENABLED = False

console = Console()

# Signature/execution fragment pattern — these are PDF artefacts, not clauses
_SIG_FRAGMENT_RE = re.compile(
    r"^(signed|printed|approved as to|consultant\s*consultant|commission\s*commission"
    r"|transportation commission\s*transportation|distribution\s*:|exhibit\s+[ab]"
    r"|fee schedule|in witness whereof)",
    re.IGNORECASE,
)


# ------------------------------------------------------------------
# Output Data Models
# ------------------------------------------------------------------

@dataclass
class ClauseReview:
    """Review result for a single clause."""
    clause_id:          str
    number:             str
    heading:            str
    clause_type:        str
    risk_level:         str                             # HIGH | MEDIUM | LOW | ACCEPTABLE
    issues:             list[str]  = field(default_factory=list)
    evidence_quotes:    list[str]  = field(default_factory=list)
    redline_suggestion: str        = ""
    redlines:           list[dict] = field(default_factory=list)  # [{replace, with}]
    new_clauses:        list[dict] = field(default_factory=list)  # [{title, reason, text}]
    reasoning:          str        = ""
    original_text:      str        = ""
    page_num:           int        = 0
    escalated:          bool       = False


@dataclass
class ContractReviewReport:
    """Complete review report for a contract."""
    filename:         str
    reviewed_at:      str
    metadata:         dict
    total_clauses:    int
    high_risk_count:  int
    medium_risk_count: int
    low_risk_count:   int
    acceptable_count: int
    clause_reviews:   list[ClauseReview] = field(default_factory=list)
    executive_summary: str = ""
    recommendation:   str  = ""

    @property
    def overall_risk(self) -> str:
        if self.high_risk_count > 0:
            return "HIGH"
        elif self.medium_risk_count > 2:
            return "MEDIUM"
        else:
            return "LOW"


# ------------------------------------------------------------------
# Review Pipeline
# ------------------------------------------------------------------

class ReviewPipeline:
    """Orchestrates the full contract review process."""

    def review_file(self, file_path) -> ContractReviewReport:
        """Full pipeline: file path → complete review report."""
        import time

        start_time = time.time()
        path = Path(file_path)
        console.print(f"\n[bold cyan]📄 Contract Review Agent[/bold cyan]")
        console.print(f"[dim]File: {path.name}[/dim]\n")

        # Step 1: Parse
        t = time.time()
        with console.status("[bold]Parsing document...[/bold]"):
            doc = parser.parse(path)
        parse_time = time.time() - t
        console.print(f"[green]✓[/green] Parsed: {doc.word_count} words, {len(doc.pages)} pages [dim]({parse_time:.2f}s)[/dim]")

        # Step 2: Segment
        t = time.time()
        with console.status("[bold]Segmenting clauses...[/bold]"):
            clauses = segmenter.segment(doc)
            summary = segmenter.get_clause_summary(clauses)
        segment_time = time.time() - t
        console.print(f"[green]✓[/green] Found {summary['total_clauses']} clauses [dim]({segment_time:.2f}s)[/dim]")

        # Step 3: Metadata
        t = time.time()
        with console.status("[bold]Extracting contract metadata...[/bold]"):
            metadata = self._extract_metadata(doc)
        metadata_time = time.time() - t
        parties_str = ", ".join(metadata.get("parties", ["Unknown"]))
        console.print(f"[green]✓[/green] Metadata: {metadata.get('contract_type', 'Unknown')} | Parties: {parties_str} [dim]({metadata_time:.2f}s)[/dim]")

        # Step 4: Review clauses
        console.print(f"\n[bold]Reviewing {len(clauses)} clauses...[/bold]")
        t = time.time()
        clause_reviews = self._review_all_clauses(clauses, governing_law=metadata.get("governing_law", ""))
        review_time = time.time() - t

        # Step 4.5: Consistency check
        clause_reviews = self._resolve_contradictions(clause_reviews)

        # Step 5: Executive summary
        t = time.time()
        with console.status("[bold]Generating executive summary...[/bold]"):
            reviews_as_dicts = [
                {
                    "heading":  r.heading or r.clause_type,
                    "risk_level": r.risk_level,
                    "issues":   " | ".join(r.issues),
                    "redlines": r.redlines,
                }
                for r in clause_reviews
            ]
            exec_summary = self._generate_summary(reviews_as_dicts, metadata)
        summary_time = time.time() - t

        total_time = time.time() - start_time

        # Assemble
        report = self._assemble_report(
            filename=path.name,
            metadata=metadata,
            clause_reviews=clause_reviews,
            executive_summary=exec_summary,
        )
        report.metadata["timing"] = {
            "total_seconds":          round(total_time, 2),
            "parse_seconds":          round(parse_time, 2),
            "segment_seconds":        round(segment_time, 2),
            "metadata_seconds":       round(metadata_time, 2),
            "review_seconds":         round(review_time, 2),
            "summary_seconds":        round(summary_time, 2),
            "avg_seconds_per_clause": round(review_time / len(clauses), 2) if clauses else 0,
        }

        color = "red" if report.overall_risk == "HIGH" else "yellow" if report.overall_risk == "MEDIUM" else "green"
        console.print(f"\n[bold green]Review Complete[/bold green]")
        console.print(f"Overall Risk: [{color}]{report.overall_risk}[/{color}]")
        console.print(f"High: {report.high_risk_count} | Medium: {report.medium_risk_count} | Low: {report.low_risk_count} | Acceptable: {report.acceptable_count}")
        console.print(f"\n[dim]⏱  Total: {total_time:.2f}s | Review: {review_time:.2f}s | Avg/clause: {review_time/len(clauses):.2f}s[/dim]")

        return report

    # ------------------------------------------------------------------
    # Metadata Extraction
    # ------------------------------------------------------------------

    def _extract_metadata(self, doc: ParsedDocument) -> dict:
        """Extract structured metadata. Uses 8000 chars to capture late-appearing governing_law."""
        prompt = prompt_extract_metadata(doc.raw_text)
        try:
            response = llm.generate(
                prompt=prompt,
                system=SYSTEM_METADATA_EXTRACTOR,
                model=config.FAST_MODEL,
                temperature=0.0,
                max_tokens=512,
            )
            return self._parse_json_response(response) or {}
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            return {
                "contract_type": doc.metadata.get("title", "Unknown"),
                "parties": [],
                "effective_date": None,
                "expiration_date": None,
                "governing_law": None,
            }

    # ------------------------------------------------------------------
    # Clause Review
    # ------------------------------------------------------------------

    def _review_all_clauses(self, clauses: list, governing_law: str = "") -> list:
        """Review all clauses with progress bar."""
        reviews = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Reviewing clauses...", total=len(clauses))
            for clause in clauses:
                progress.update(task, description=f"[cyan]{clause.heading or clause.clause_type or 'clause'}[/cyan]")
                review = self._review_single_clause(clause, governing_law=governing_law)
                reviews.append(review)
                color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue", "ACCEPTABLE": "green"}.get(review.risk_level, "white")
                progress.console.print(
                    f"  [{color}]{review.risk_level}[/{color}] — "
                    f"{review.heading or review.clause_type or clause.clause_id}"
                )
                progress.advance(task)
        return reviews

    def _review_single_clause(self, clause, governing_law: str = "") -> ClauseReview:
        """
        Two-pass review for one clause.
        Pass 1 (quote extraction): low-temp, short — just extract verbatim evidence phrases.
        Pass 2 (full analysis): anchored to verified quotes, max_tokens=2048.
        """
        # ── Hard skip: signature/execution fragments ──────────────────
        text_stripped = clause.text.strip()
        heading_stripped = (clause.heading or "").strip()
        if _SIG_FRAGMENT_RE.match(text_stripped) or _SIG_FRAGMENT_RE.match(heading_stripped):
            return ClauseReview(
                clause_id=clause.clause_id, number=clause.number,
                heading=clause.heading, clause_type=clause.clause_type,
                risk_level="ACCEPTABLE", issues=[],
                reasoning="Skipped — execution/signature fragment.",
                original_text=clause.text,
                page_num=getattr(clause, "page_hint", 0),
            )

        # ── Soft skip: short admin clauses ───────────────────────────
        SKIP_TYPES = {"general"}
        SKIP_KEYWORDS = {
            "by name:", "title:", "cin :", "www.", "website :", "email :",
            "address :", "signed by", "print name",
        }
        clause_lower = clause.text.lower()
        if (clause.clause_type in SKIP_TYPES and len(clause.text) < 300
                and any(kw in clause_lower for kw in SKIP_KEYWORDS)):
            return ClauseReview(
                clause_id=clause.clause_id, number=clause.number,
                heading=clause.heading, clause_type=clause.clause_type,
                risk_level="ACCEPTABLE", issues=[],
                reasoning="Skipped — administrative content.",
                original_text=clause.text,
                page_num=getattr(clause, "page_hint", 0),
            )

        # ── Recital cap: WHEREAS / PREAMBLE / BACKGROUND are narrative, not operative.
        # They cannot be HIGH or MEDIUM — max risk is LOW.
        is_recital = clause.metadata.get("is_recital", False)

        # ── Placeholder density: template with unfilled blanks.
        # Don't hunt for evidence quotes — they don't exist yet.
        placeholder_pct = clause.metadata.get("placeholder_pct", 0.0)
        is_template     = placeholder_pct > 0.04   # >4% of tokens are blanks

        try:
            # RAG context
            playbook_context = ""
            if RAG_ENABLED and retriever is not None:
                playbook_context = retriever.get_context_for_clause(
                    clause_type=clause.clause_type,
                    clause_text=clause.text,
                    governing_law=governing_law or None,
                )

            # ── Pass 1: evidence extraction (skip for template clauses) ──
            if is_template:
                verified_quotes = []   # No real text to quote from blanks
            else:
                raw_quotes = llm.generate(
                    prompt=prompt_extract_evidence(clause.text, clause.clause_type),
                    system=SYSTEM_CONTRACT_REVIEWER,
                    temperature=0.0,
                    max_tokens=512,
                )
                verified_quotes = self._verify_quotes(raw_quotes, clause.text)

            # ── Pass 2: full review anchored to quotes (2048 tokens) ─
            response = llm.generate(
                prompt=prompt_review_clause(
                    clause_text=clause.text,
                    clause_type=clause.clause_type,
                    clause_heading=clause.heading,
                    playbook_context=playbook_context,
                    verified_quotes=verified_quotes,
                    is_recital=is_recital,
                    is_template=is_template,
                ),
                system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.1,
                max_tokens=2048,
            )

            review = self._parse_review_response(response, clause)

            # ── Recital cap: recitals cannot be HIGH or MEDIUM ──────────────
            if is_recital:
                RECITAL_MAX = {"HIGH": "LOW", "MEDIUM": "LOW"}
                if review.risk_level in RECITAL_MAX:
                    review.risk_level = RECITAL_MAX[review.risk_level]
                    review.reasoning  = (
                        "[Recital/WHEREAS clause — narrative context only, no legal force. "
                        "Risk capped at LOW.] " + review.reasoning
                    )

            # ── Template note: flag placeholder clauses clearly ─────────────
            if is_template and not review.reasoning.startswith("[Template"):
                review.reasoning = (
                    f"[Template clause — {placeholder_pct*100:.0f}% unfilled placeholders. "
                    "Evidence quotes unreliable; review once values are filled in.] "
                    + review.reasoning
                )
                # Suppress evidence for template clauses — it's all hallucinated
                review.evidence_quotes = [""] * len(review.evidence_quotes)

            # Post-parse: discard any evidence the model invented
            review.evidence_quotes = self._filter_hallucinated_evidence(
                review.evidence_quotes, clause.text
            )
            return review

        except Exception as e:
            logger.error(f"Failed to review clause {clause.clause_id}: {e}")
            return ClauseReview(
                clause_id=clause.clause_id, number=clause.number,
                heading=clause.heading, clause_type=clause.clause_type,
                risk_level="LOW",
                issues=[f"Review failed: {str(e)}"],
                original_text=clause.text,
            )

    # ------------------------------------------------------------------
    # Evidence Helpers
    # ------------------------------------------------------------------

    def _verify_quotes(self, raw_response: str, clause_text: str) -> list[str]:
        """Keep only quotes that appear verbatim in clause_text."""
        quotes = []
        clause_lower = clause_text.lower()

        for line in raw_response.split("\n"):
            line = line.strip()
            if not line or line.lower() in ("none", "none."):
                continue

            # Strip known prefixes
            candidate = line
            for prefix in ("QUOTE:", "- QUOTE:", "• QUOTE:", "•", "- "):
                if candidate.upper().startswith(prefix.upper()):
                    candidate = candidate[len(prefix):].strip()
                    break

            candidate = candidate.strip('"').strip("'").strip()
            if len(candidate) < 8:
                continue

            # Exact match
            if candidate.lower() in clause_lower:
                quotes.append(candidate)
                continue

            # 85% prefix match fallback for longer quotes
            if len(candidate) >= 20:
                key = candidate[:int(len(candidate) * 0.85)].lower()
                if key in clause_lower:
                    quotes.append(candidate)

        return quotes

    def _filter_hallucinated_evidence(self, evidence_quotes: list, clause_text: str) -> list:
        """Discard any evidence quote not present verbatim in clause_text."""
        clause_lower = clause_text.lower()
        cleaned = []
        for ev in evidence_quotes:
            ev_clean = ev.strip().strip('"').strip("'")
            # Must match 85% of the quote (min 12 chars)
            key = ev_clean[:max(12, int(len(ev_clean) * 0.85))].lower()
            if key and key in clause_lower:
                cleaned.append(ev_clean)
            else:
                cleaned.append("")   # blank → renders as N/A
        return cleaned

    # ------------------------------------------------------------------
    # Summary Generation
    # ------------------------------------------------------------------

    def _generate_summary(self, reviews: list, metadata: dict) -> str:
        """Generate executive summary from all clause reviews."""
        prompt = prompt_contract_summary(reviews, metadata)
        try:
            return llm.generate(
                prompt=prompt,
                system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.2,
                max_tokens=1500,
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Summary generation failed. Please review individual clause results."

    # ------------------------------------------------------------------
    # Report Assembly
    # ------------------------------------------------------------------

    def _assemble_report(self, filename, metadata, clause_reviews, executive_summary) -> ContractReviewReport:
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "ACCEPTABLE": 0}
        for review in clause_reviews:
            level = review.risk_level.upper()
            if level in counts:
                counts[level] += 1

        recommendation = "Negotiate before signing"
        if "do not sign" in executive_summary.lower():
            recommendation = "Do not sign"
        elif "sign as-is" in executive_summary.lower() or "sign as is" in executive_summary.lower():
            recommendation = "Sign as-is"

        return ContractReviewReport(
            filename=filename,
            reviewed_at=datetime.now().isoformat(),
            metadata=metadata,
            total_clauses=len(clause_reviews),
            high_risk_count=counts["HIGH"],
            medium_risk_count=counts["MEDIUM"],
            low_risk_count=counts["LOW"],
            acceptable_count=counts["ACCEPTABLE"],
            clause_reviews=clause_reviews,
            executive_summary=executive_summary,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Contradiction Resolver
    # ------------------------------------------------------------------

    def _resolve_contradictions(self, reviews: list) -> list:
        """
        Ensures risk consistency across clauses of the SAME type.
        Only fires when a 2+ level gap exists (HIGH vs LOW is contradictory).
        Escalates by exactly ONE step at a time. Excludes noisy/broad types.
        """
        RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "ACCEPTABLE": 0}
        RISK_NAMES = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "ACCEPTABLE"}

        # Types too generic or too varied to compare meaningfully
        SKIP_TYPES = {
            "general", "definitions", "entire_agreement", "amendment",
            "notices", "code_of_conduct", "assignment", "warranties",
        }

        type_counts: dict[str, int] = {}
        for r in reviews:
            type_counts[r.clause_type] = type_counts.get(r.clause_type, 0) + 1

        max_risk_per_type: dict[str, int] = {}
        for r in reviews:
            if type_counts.get(r.clause_type, 0) < 2:
                continue
            if r.clause_type in SKIP_TYPES:
                continue
            cur = max_risk_per_type.get(r.clause_type, 0)
            lvl = RISK_ORDER.get(r.risk_level, 0)
            if lvl > cur:
                max_risk_per_type[r.clause_type] = lvl

        for r in reviews:
            if r.clause_type not in max_risk_per_type:
                continue
            type_max  = max_risk_per_type[r.clause_type]
            this_lvl  = RISK_ORDER.get(r.risk_level, 0)
            if type_max - this_lvl >= 2:
                old_level = r.risk_level
                new_level = RISK_NAMES[this_lvl + 1]
                r.risk_level = new_level
                r.escalated  = True
                r.reasoning  = (
                    f"[Consistency: escalated {old_level} → {new_level} because another "
                    f"{r.clause_type} clause was rated {RISK_NAMES[type_max]}.] " + r.reasoning
                )
                logger.debug(f"Escalated {r.clause_id}: {old_level} → {new_level}")

        return reviews

    # ------------------------------------------------------------------
    # Response Parsers
    # ------------------------------------------------------------------

    def _parse_review_response(self, response: str, clause) -> ClauseReview:
        """Parse the structured LLM review response."""
        risk_level      = "LOW"
        issues          = []
        evidence_quotes = []
        redlines        = []
        new_clauses     = []
        redline_summary = ""
        reasoning       = ""

        # RISK_LEVEL
        m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
        if m:
            risk_level = m.group(1).upper()

        # ISSUES block
        issues_match = re.search(
            r"ISSUES:\s*(.*?)(?=REDLINE:|NEW_CLAUSE:|REASONING:|$)", response, re.DOTALL
        )
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text.lower() not in ("none", "none."):
                blocks = re.split(r"(?=\n?-\s*ISSUE:)", issues_text)
                for block in blocks:
                    block = block.strip()
                    if not block or "ISSUE:" not in block.upper():
                        continue

                    issue_m    = re.search(r"ISSUE:\s*(.+?)(?=EVIDENCE:|IMPACT:|$)",  block, re.DOTALL | re.IGNORECASE)
                    evidence_m = re.search(r'EVIDENCE:\s*["\']?(.+?)["\']?(?=\s*IMPACT:|$)', block, re.DOTALL | re.IGNORECASE)
                    impact_m   = re.search(r"IMPACT:\s*(.+?)$", block, re.DOTALL | re.IGNORECASE)

                    if not issue_m:
                        continue

                    issue_text  = issue_m.group(1).strip()
                    impact_text = impact_m.group(1).strip() if impact_m else ""
                    issues.append(issue_text + (f" — {impact_text}" if impact_text else ""))
                    evidence_quotes.append(
                        evidence_m.group(1).strip().strip('"').strip("'") if evidence_m else ""
                    )

                # Fallback: plain bullets
                if not issues:
                    for line in issues_text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line and len(line) > 10:
                            issues.append(line)
                            evidence_quotes.append("")

        # REDLINE block
        redline_match = re.search(r"REDLINE:\s*(.*?)(?=NEW_CLAUSE:|REASONING:|$)", response, re.DOTALL)
        if redline_match:
            redline_text = redline_match.group(1).strip()
            if "no changes needed" not in redline_text.lower():
                pairs = re.findall(
                    r'REPLACE:\s*["\']?(.+?)["\']?\s*WITH:\s*["\']?(.+?)["\']?(?=REPLACE:|$)',
                    redline_text, re.DOTALL
                )
                for replace_text, with_text in pairs:
                    r_ = re.sub(r'(?i)^replace\s*:\s*', '', replace_text.strip()).strip().strip('"').strip("'")
                    w_ = re.sub(r'(?i)^with\s*:\s*', '',  with_text.strip()).strip().strip('"').strip("'")
                    JUNK = {"none", "-", "**", "no changes needed", ""}
                    if r_.lower() in JUNK or w_.lower() in JUNK or r_ == w_:
                        continue
                    r_ = r_.rstrip("*\n").strip().rstrip('"').strip()
                    w_ = w_.rstrip("*\n").strip().rstrip('"').strip()
                    if r_ and w_ and r_ != w_:
                        redlines.append({"replace": r_, "with": w_})
                redline_summary = redline_text[:500]

        # NEW_CLAUSE block
        nc_match = re.search(r"NEW_CLAUSE:\s*(.*?)(?=REASONING:|$)", response, re.DOTALL)
        if nc_match:
            nc_text = nc_match.group(1).strip()
            if nc_text.lower() not in ("none", "none.", ""):
                for entry in re.split(r"(?=TITLE:)", nc_text):
                    entry = entry.strip()
                    if not entry:
                        continue
                    title_m  = re.search(r"TITLE:\s*(.+?)(?=REASON:|TEXT:|$)",  entry, re.DOTALL)
                    reason_m = re.search(r"REASON:\s*(.+?)(?=TEXT:|$)",          entry, re.DOTALL)
                    text_m   = re.search(r"TEXT:\s*(.+?)$",                      entry, re.DOTALL)
                    if title_m and text_m:
                        nc_title  = title_m.group(1).strip().strip('"')
                        nc_reason = reason_m.group(1).strip() if reason_m else ""
                        nc_text_v = text_m.group(1).strip().strip('"')
                        if nc_title and nc_text_v:
                            new_clauses.append({"title": nc_title, "reason": nc_reason, "text": nc_text_v})

        # REASONING
        reason_match = re.search(r"REASONING:\s*(.*?)$", response, re.DOTALL)
        if reason_match:
            reasoning = reason_match.group(1).strip()
            # Strip leaked ** from reasoning end
            reasoning = re.sub(r"\s*\*\*\s*$", "", reasoning).strip()

        # ── Sanitize: strip raw format labels that bled into field values ──
        # Happens when the model outputs format tags inside issues/reasoning blocks.
        _FORMAT_LEAK = re.compile(
            r"^(RISK_LEVEL|REDLINES?|REPLACE|WITH|NEW_CLAUSE|REASONING|ISSUES?)"
            r"\s*:\s*", re.IGNORECASE | re.MULTILINE
        )
        issues          = [_FORMAT_LEAK.sub("", i).strip() for i in issues if i.strip()]
        evidence_quotes = [e for e in evidence_quotes]   # preserve 1:1 with issues

        # Drop any issue that is just a format artifact (< 10 chars after cleanup)
        cleaned_pairs = [
            (iss, ev) for iss, ev in zip(issues, evidence_quotes)
            if len(iss.strip()) >= 10
        ]
        issues          = [p[0] for p in cleaned_pairs]
        evidence_quotes = [p[1] for p in cleaned_pairs]

        # Sanitize new_clause texts — strip leaked markdown bold/format
        for nc in new_clauses:
            nc["text"] = re.sub(r"\*\*\s*$", "", nc.get("text", "")).strip().strip('"')

        return ClauseReview(
            clause_id=clause.clause_id,
            number=clause.number,
            heading=clause.heading,
            clause_type=clause.clause_type,
            risk_level=risk_level,
            issues=issues,
            evidence_quotes=evidence_quotes,
            redline_suggestion=redline_summary,
            redlines=redlines,
            new_clauses=new_clauses,
            reasoning=reasoning,
            original_text=clause.text,
            page_num=getattr(clause, "page_hint", 0),
        )

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Safely parse JSON from LLM response."""
        clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        return None


# Singleton
review_pipeline = ReviewPipeline()