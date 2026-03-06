# """
# core/review_pipeline.py — Parallel Contract Review Pipeline

# Architecture:
#   - Metadata extraction runs concurrently with first clause batch
#   - All clauses reviewed in parallel (asyncio + semaphore, 10 workers)
#   - Single-pass fused prompt (evidence + review in ONE LLM call)
#   - Sync wrapper so existing main.py / CLI code needs zero changes

# Performance on RTX 6000 Pro (95GB) with Qwen2.5 14B:
#   Sequential (old): ~4s/clause × 46 = ~184s
#   Parallel fused:   ~15-20s total wall clock
# """

# import asyncio
# import json
# import re
# import time
# from dataclasses import dataclass, field
# from datetime import datetime
# from pathlib import Path
# from typing import Optional

# from loguru import logger
# from rich.console import Console
# from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

# from core.llm import llm, async_llm
# from core.config import config
# from ingestion.parser import parser, ParsedDocument
# from ingestion.segmenter import segmenter, Clause
# from prompts.review_prompts import (
#     SYSTEM_CONTRACT_REVIEWER,
#     SYSTEM_METADATA_EXTRACTOR,
#     prompt_extract_metadata,
#     prompt_review_clause_fused,
#     prompt_triage_clause,
#     prompt_contract_summary,
# )

# # RAG retriever (optional)
# try:
#     from rag.retriever import retriever
#     RAG_ENABLED = True
# except Exception:
#     retriever = None
#     RAG_ENABLED = False

# console = Console()

# _SIG_FRAGMENT_RE = re.compile(
#     r"^(signed|printed|approved as to|consultant\s*consultant|commission\s*commission"
#     r"|transportation commission\s*transportation|distribution\s*:|exhibit\s+[ab]"
#     r"|fee schedule|in witness whereof)",
#     re.IGNORECASE,
# )


# # ------------------------------------------------------------------
# # Data Models (unchanged)
# # ------------------------------------------------------------------

# @dataclass
# class ClauseReview:
#     clause_id:          str
#     number:             str
#     heading:            str
#     clause_type:        str
#     risk_level:         str
#     issues:             list[str]  = field(default_factory=list)
#     evidence_quotes:    list[str]  = field(default_factory=list)
#     redline_suggestion: str        = ""
#     redlines:           list[dict] = field(default_factory=list)
#     new_clauses:        list[dict] = field(default_factory=list)
#     reasoning:          str        = ""
#     original_text:      str        = ""
#     page_num:           int        = 0
#     escalated:          bool       = False


# @dataclass
# class ContractReviewReport:
#     filename:          str
#     reviewed_at:       str
#     metadata:          dict
#     total_clauses:     int
#     high_risk_count:   int
#     medium_risk_count: int
#     low_risk_count:    int
#     acceptable_count:  int
#     clause_reviews:    list[ClauseReview] = field(default_factory=list)
#     executive_summary: str = ""
#     recommendation:    str = ""

#     @property
#     def overall_risk(self) -> str:
#         if self.high_risk_count > 0:
#             return "HIGH"
#         elif self.medium_risk_count > 2:
#             return "MEDIUM"
#         return "LOW"


# # ------------------------------------------------------------------
# # Review Pipeline
# # ------------------------------------------------------------------

# class ReviewPipeline:

#     def review_file(self, file_path) -> ContractReviewReport:
#         """Sync entry point — wraps async pipeline for CLI/main.py compat."""
#         return asyncio.run(self._review_file_async(file_path))

#     # ------------------------------------------------------------------
#     # Async orchestrator
#     # ------------------------------------------------------------------

#     async def _review_file_async(self, file_path) -> ContractReviewReport:
#         start = time.time()
#         path  = Path(file_path)

#         console.print(f"\n[bold cyan]📄 Contract Review Agent[/bold cyan]")
#         console.print(f"[dim]File: {path.name}[/dim]\n")

#         # ── Step 1: Parse ───────────────────────────────────────────────
#         t = time.time()
#         with console.status("[bold]Parsing document...[/bold]"):
#             doc = parser.parse(path)
#         parse_time = time.time() - t
#         console.print(f"[green]✓[/green] Parsed: {doc.word_count} words, {len(doc.pages)} pages [dim]({parse_time:.2f}s)[/dim]")

#         # ── Step 2: Segment ─────────────────────────────────────────────
#         t = time.time()
#         with console.status("[bold]Segmenting clauses...[/bold]"):
#             clauses = segmenter.segment(doc)
#             summary = segmenter.get_clause_summary(clauses)
#         segment_time = time.time() - t
#         console.print(f"[green]✓[/green] Found {summary['total_clauses']} clauses [dim]({segment_time:.2f}s)[/dim]")

#         # ── Step 3+4: Metadata + Clause review IN PARALLEL ─────────────
#         console.print(f"\n[bold]Reviewing {len(clauses)} clauses in parallel...[/bold]")
#         t = time.time()

#         # Fire metadata and all clause reviews simultaneously
#         metadata_task = asyncio.create_task(self._extract_metadata_async(doc))
#         review_tasks  = [
#             asyncio.create_task(self._review_single_clause_async(clause))
#             for clause in clauses
#         ]

#         # Progress bar — updates as each clause completes
#         clause_reviews_ordered = [None] * len(clauses)
#         completed = 0

#         with Progress(
#             SpinnerColumn(),
#             TextColumn("[progress.description]{task.description}"),
#             BarColumn(),
#             MofNCompleteColumn(),
#             console=console,
#             transient=False,
#         ) as progress:
#             task_bar = progress.add_task("Reviewing...", total=len(clauses))

#             pending = {t: i for i, t in enumerate(review_tasks)}
#             futures = set(review_tasks)

#             while futures:
#                 done, futures = await asyncio.wait(
#                     futures, return_when=asyncio.FIRST_COMPLETED
#                 )
#                 for fut in done:
#                     idx    = pending[fut]
#                     review = fut.result()
#                     clause_reviews_ordered[idx] = review
#                     completed += 1
#                     color = {"HIGH": "red", "MEDIUM": "yellow",
#                              "LOW": "blue", "ACCEPTABLE": "green"}.get(review.risk_level, "white")
#                     progress.console.print(
#                         f"  [{color}]{review.risk_level}[/{color}] — "
#                         f"{review.heading or review.clause_type or clauses[idx].clause_id}"
#                     )
#                     progress.advance(task_bar)

#         review_time = time.time() - t

#         # Wait for metadata (almost certainly done already)
#         metadata = await metadata_task
#         metadata_time = review_time   # ran in parallel — no extra wall time

#         parties_str = ", ".join(metadata.get("parties", ["Unknown"]))
#         console.print(f"[green]✓[/green] Metadata: {metadata.get('contract_type','Unknown')} | {parties_str}")

#         # ── Step 4.5: Contradiction resolver ───────────────────────────
#         clause_reviews = self._resolve_contradictions(clause_reviews_ordered)

#         # ── Step 5: Executive summary ───────────────────────────────────
#         t = time.time()
#         with console.status("[bold]Generating executive summary...[/bold]"):
#             reviews_as_dicts = [
#                 {
#                     "heading":    r.heading or r.clause_type,
#                     "risk_level": r.risk_level,
#                     "issues":     " | ".join(r.issues),
#                     "redlines":   r.redlines,
#                 }
#                 for r in clause_reviews
#             ]
#             exec_summary = self._generate_summary(reviews_as_dicts, metadata)
#         summary_time = time.time() - t

#         total_time = time.time() - start

#         report = self._assemble_report(
#             filename=path.name,
#             metadata=metadata,
#             clause_reviews=clause_reviews,
#             executive_summary=exec_summary,
#         )
#         report.metadata["timing"] = {
#             "total_seconds":          round(total_time, 2),
#             "parse_seconds":          round(parse_time, 2),
#             "segment_seconds":        round(segment_time, 2),
#             "metadata_seconds":       round(metadata_time, 2),
#             "review_seconds":         round(review_time, 2),
#             "summary_seconds":        round(summary_time, 2),
#             "avg_seconds_per_clause": round(review_time / len(clauses), 2) if clauses else 0,
#         }

#         color = "red" if report.overall_risk == "HIGH" else "yellow" if report.overall_risk == "MEDIUM" else "green"
#         console.print(f"\n[bold green]Review Complete[/bold green]")
#         console.print(f"Overall Risk: [{color}]{report.overall_risk}[/{color}]")
#         console.print(f"High: {report.high_risk_count} | Medium: {report.medium_risk_count} | Low: {report.low_risk_count} | Acceptable: {report.acceptable_count}")
#         console.print(f"\n[dim]⏱  Total: {total_time:.2f}s | Review: {review_time:.2f}s | Avg/clause: {review_time/len(clauses):.2f}s[/dim]")

#         return report

#     # ------------------------------------------------------------------
#     # Async Metadata Extraction
#     # ------------------------------------------------------------------

#     async def _extract_metadata_async(self, doc: ParsedDocument) -> dict:
#         prompt = prompt_extract_metadata(doc.raw_text)
#         try:
#             response = await async_llm.fast_generate(
#                 prompt=prompt,
#                 system=SYSTEM_METADATA_EXTRACTOR,
#             )
#             return self._parse_json_response(response) or {}
#         except Exception as e:
#             logger.warning(f"Metadata extraction failed: {e}")
#             return {
#                 "contract_type": doc.metadata.get("title", "Unknown"),
#                 "parties": [], "effective_date": None,
#                 "expiration_date": None, "governing_law": None,
#             }

#     # Keep sync version for backwards compat
#     def _extract_metadata(self, doc: ParsedDocument) -> dict:
#         prompt = prompt_extract_metadata(doc.raw_text)
#         try:
#             response = llm.generate(
#                 prompt=prompt, system=SYSTEM_METADATA_EXTRACTOR,
#                 model=config.FAST_MODEL, temperature=0.0, max_tokens=512,
#             )
#             return self._parse_json_response(response) or {}
#         except Exception as e:
#             logger.warning(f"Metadata extraction failed: {e}")
#             return {}

#     # ------------------------------------------------------------------
#     # Async Single-Clause Review (fused single pass)
#     # ------------------------------------------------------------------

#     async def _review_single_clause_async(self, clause, governing_law: str = "") -> ClauseReview:
#         """
#         Two-tier triage + deep review.

#         Tier 1 (all clauses): fast triage - just RISK_LEVEL + one line. ~60 tokens.
#         Tier 2 (HIGH/MEDIUM only): full deep review with redlines + new clauses. ~700 tokens.

#         LOW/ACCEPTABLE clauses skip Tier 2 entirely - 60-70% of clauses never hit deep review.
#         Result: 60% fewer total output tokens -> ~60% faster wall clock.
#         """
#         text_stripped    = clause.text.strip()
#         heading_stripped = (clause.heading or "").strip()

#         # Hard skip: signature fragments
#         if _SIG_FRAGMENT_RE.match(text_stripped) or _SIG_FRAGMENT_RE.match(heading_stripped):
#             return ClauseReview(
#                 clause_id=clause.clause_id, number=clause.number,
#                 heading=clause.heading, clause_type=clause.clause_type,
#                 risk_level="ACCEPTABLE", issues=[],
#                 reasoning="Skipped - execution/signature fragment.",
#                 original_text=clause.text,
#                 page_num=getattr(clause, "page_hint", 0),
#             )

#         # Soft skip: short admin clauses
#         SKIP_KEYWORDS = {
#             "by name:", "title:", "cin :", "www.", "website :", "email :",
#             "address :", "signed by", "print name",
#         }
#         if (clause.clause_type == "general" and len(clause.text) < 300
#                 and any(kw in clause.text.lower() for kw in SKIP_KEYWORDS)):
#             return ClauseReview(
#                 clause_id=clause.clause_id, number=clause.number,
#                 heading=clause.heading, clause_type=clause.clause_type,
#                 risk_level="ACCEPTABLE", issues=[],
#                 reasoning="Skipped - administrative content.",
#                 original_text=clause.text,
#                 page_num=getattr(clause, "page_hint", 0),
#             )

#         is_recital      = clause.metadata.get("is_recital", False)
#         is_borello      = clause.metadata.get("is_borello_factor", False)
#         if is_borello:
#             is_recital = True
#         placeholder_pct = clause.metadata.get("placeholder_pct", 0.0)
#         is_template     = placeholder_pct > 0.04

#         try:
#             # ── TIER 1: Fast triage (every clause) ───────────────────────
#             triage_enabled = getattr(config, "ENABLE_TRIAGE", True)

#             if triage_enabled and not is_recital:
#                 triage_response = await async_llm.generate(
#                     prompt=prompt_triage_clause(
#                         clause_text=clause.text,
#                         clause_type=clause.clause_type,
#                         clause_heading=clause.heading or "",
#                     ),
#                     system=SYSTEM_CONTRACT_REVIEWER,
#                     temperature=0.0,
#                     max_tokens=80,
#                 )
#                 triage_risk = self._parse_triage_risk(triage_response)

#                 # LOW / ACCEPTABLE: skip deep review, return triage result directly
#                 if triage_risk in ("LOW", "ACCEPTABLE"):
#                     triage_reason = self._parse_triage_reason(triage_response)
#                     return ClauseReview(
#                         clause_id=clause.clause_id, number=clause.number,
#                         heading=clause.heading, clause_type=clause.clause_type,
#                         risk_level=triage_risk,
#                         issues=[triage_reason] if triage_reason and triage_reason != "No significant issues" else [],
#                         reasoning=triage_reason,
#                         original_text=clause.text,
#                         page_num=getattr(clause, "page_hint", 0),
#                     )
#                 # HIGH / MEDIUM: fall through to full deep review below

#             # ── TIER 2: Full deep review (HIGH/MEDIUM only) ──────────────
#             playbook_context = ""
#             if RAG_ENABLED and retriever is not None:
#                 try:
#                     playbook_context = retriever.get_context_for_clause(
#                         clause_type=clause.clause_type,
#                         clause_text=clause.text,
#                         governing_law=governing_law or None,
#                     )
#                 except Exception:
#                     pass

#             response = await async_llm.generate(
#                 prompt=prompt_review_clause_fused(
#                     clause_text=clause.text,
#                     clause_type=clause.clause_type,
#                     clause_heading=clause.heading,
#                     playbook_context=playbook_context,
#                     is_recital=is_recital,
#                     is_template=is_template,
#                 ),
#                 system=SYSTEM_CONTRACT_REVIEWER,
#                 temperature=0.1,
#                 max_tokens=2048,
#             )

#             review = self._parse_review_response(response, clause)

#             # Recital cap
#             if is_recital:
#                 if review.risk_level in ("HIGH", "MEDIUM"):
#                     review.risk_level = "LOW"
#                     review.reasoning  = (
#                         "[Recital/WHEREAS clause - narrative only, no legal force. "
#                         "Risk capped at LOW.] " + review.reasoning
#                     )

#             # Template note
#             if is_template and not review.reasoning.startswith("[Template"):
#                 review.reasoning = (
#                     f"[Template clause - {placeholder_pct*100:.0f}% unfilled placeholders. "
#                     "Review once values are filled in.] " + review.reasoning
#                 )
#                 review.evidence_quotes = [""] * len(review.evidence_quotes)

#             review.evidence_quotes = self._filter_hallucinated_evidence(
#                 review.evidence_quotes, clause.text
#             )
#             return review

#         except Exception as e:
#             logger.error(f"Failed to review clause {clause.clause_id}: {e}")
#             return ClauseReview(
#                 clause_id=clause.clause_id, number=clause.number,
#                 heading=clause.heading, clause_type=clause.clause_type,
#                 risk_level="LOW",
#                 issues=[f"Review failed: {str(e)}"],
#                 original_text=clause.text,
#             )

#     def _parse_triage_risk(self, response: str) -> str:
#         """Extract RISK_LEVEL from triage response."""
#         m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
#         return m.group(1).upper() if m else "MEDIUM"  # default to MEDIUM if unparseable

#     def _parse_triage_reason(self, response: str) -> str:
#         """Extract REASON from triage response."""
#         m = re.search(r"REASON:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
#         return m.group(1).strip() if m else ""

#     # ------------------------------------------------------------------
#     # Evidence Filter
#     # ------------------------------------------------------------------

#     def _filter_hallucinated_evidence(self, evidence_quotes: list, clause_text: str) -> list:
#         clause_lower = clause_text.lower()
#         cleaned = []
#         for ev in evidence_quotes:
#             ev_clean = ev.strip().strip('"').strip("'")
#             key = ev_clean[:max(12, int(len(ev_clean) * 0.85))].lower()
#             cleaned.append(ev_clean if key and key in clause_lower else "")
#         return cleaned

#     # ------------------------------------------------------------------
#     # Summary (sync — runs after all clauses done)
#     # ------------------------------------------------------------------

#     def _generate_summary(self, reviews: list, metadata: dict) -> str:
#         prompt = prompt_contract_summary(reviews, metadata)
#         try:
#             return llm.generate(
#                 prompt=prompt, system=SYSTEM_CONTRACT_REVIEWER,
#                 temperature=0.2, max_tokens=1500,
#             )
#         except Exception as e:
#             logger.error(f"Summary generation failed: {e}")
#             return "Summary generation failed. Please review individual clause results."

#     # ------------------------------------------------------------------
#     # Report Assembly
#     # ------------------------------------------------------------------

#     def _assemble_report(self, filename, metadata, clause_reviews, executive_summary) -> ContractReviewReport:
#         counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "ACCEPTABLE": 0}
#         for r in clause_reviews:
#             level = r.risk_level.upper()
#             if level in counts:
#                 counts[level] += 1

#         recommendation = "Negotiate before signing"
#         if "do not sign" in executive_summary.lower():
#             recommendation = "Do not sign"
#         elif "sign as-is" in executive_summary.lower() or "sign as is" in executive_summary.lower():
#             recommendation = "Sign as-is"

#         return ContractReviewReport(
#             filename=filename,
#             reviewed_at=datetime.now().isoformat(),
#             metadata=metadata,
#             total_clauses=len(clause_reviews),
#             high_risk_count=counts["HIGH"],
#             medium_risk_count=counts["MEDIUM"],
#             low_risk_count=counts["LOW"],
#             acceptable_count=counts["ACCEPTABLE"],
#             clause_reviews=clause_reviews,
#             executive_summary=executive_summary,
#             recommendation=recommendation,
#         )

#     # ------------------------------------------------------------------
#     # Contradiction Resolver (unchanged)
#     # ------------------------------------------------------------------

#     def _resolve_contradictions(self, reviews: list) -> list:
#         RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "ACCEPTABLE": 0}
#         RISK_NAMES = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "ACCEPTABLE"}
#         SKIP_TYPES = {
#             "general", "definitions", "entire_agreement", "amendment",
#             "notices", "code_of_conduct", "assignment", "warranties",
#         }

#         type_counts: dict[str, int] = {}
#         for r in reviews:
#             type_counts[r.clause_type] = type_counts.get(r.clause_type, 0) + 1

#         max_risk_per_type: dict[str, int] = {}
#         for r in reviews:
#             if type_counts.get(r.clause_type, 0) < 2:
#                 continue
#             if r.clause_type in SKIP_TYPES:
#                 continue
#             cur = max_risk_per_type.get(r.clause_type, 0)
#             lvl = RISK_ORDER.get(r.risk_level, 0)
#             if lvl > cur:
#                 max_risk_per_type[r.clause_type] = lvl

#         for r in reviews:
#             if r.clause_type not in max_risk_per_type:
#                 continue
#             type_max = max_risk_per_type[r.clause_type]
#             this_lvl = RISK_ORDER.get(r.risk_level, 0)
#             if type_max - this_lvl >= 2:
#                 old_level = r.risk_level
#                 new_level = RISK_NAMES[this_lvl + 1]
#                 r.risk_level = new_level
#                 r.escalated  = True
#                 r.reasoning  = (
#                     f"[Consistency: escalated {old_level} → {new_level} because another "
#                     f"{r.clause_type} clause was rated {RISK_NAMES[type_max]}.] " + r.reasoning
#                 )
#         return reviews

#     # ------------------------------------------------------------------
#     # Response Parser (unchanged)
#     # ------------------------------------------------------------------

#     def _parse_review_response(self, response: str, clause) -> ClauseReview:
#         risk_level      = "LOW"
#         issues          = []
#         evidence_quotes = []
#         redlines        = []
#         new_clauses     = []
#         redline_summary = ""
#         reasoning       = ""

#         m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
#         if m:
#             risk_level = m.group(1).upper()

#         issues_match = re.search(
#             r"ISSUES:\s*(.*?)(?=REDLINE:|NEW_CLAUSE:|REASONING:|$)", response, re.DOTALL
#         )
#         if issues_match:
#             issues_text = issues_match.group(1).strip()
#             if issues_text.lower() not in ("none", "none."):
#                 blocks = re.split(r"(?=\n?-\s*ISSUE:)", issues_text)
#                 for block in blocks:
#                     block = block.strip()
#                     if not block or "ISSUE:" not in block.upper():
#                         continue
#                     issue_m    = re.search(r"ISSUE:\s*(.+?)(?=EVIDENCE:|IMPACT:|$)",  block, re.DOTALL | re.IGNORECASE)
#                     evidence_m = re.search(r'EVIDENCE:\s*["\']?(.+?)["\']?(?=\s*IMPACT:|$)', block, re.DOTALL | re.IGNORECASE)
#                     impact_m   = re.search(r"IMPACT:\s*(.+?)$", block, re.DOTALL | re.IGNORECASE)
#                     if not issue_m:
#                         continue
#                     issue_text  = issue_m.group(1).strip()
#                     impact_text = impact_m.group(1).strip() if impact_m else ""
#                     issues.append(issue_text + (f" — {impact_text}" if impact_text else ""))
#                     evidence_quotes.append(
#                         evidence_m.group(1).strip().strip('"').strip("'") if evidence_m else ""
#                     )
#                 if not issues:
#                     for line in issues_text.split("\n"):
#                         line = line.strip().lstrip("-•").strip()
#                         if line and len(line) > 10:
#                             issues.append(line)
#                             evidence_quotes.append("")

#         redline_match = re.search(r"REDLINE:\s*(.*?)(?=NEW_CLAUSE:|REASONING:|$)", response, re.DOTALL)
#         if redline_match:
#             redline_text = redline_match.group(1).strip()
#             if "no changes needed" not in redline_text.lower():
#                 pairs = re.findall(
#                     r'REPLACE:\s*["\']?(.+?)["\']?\s*WITH:\s*["\']?(.+?)["\']?(?=REPLACE:|$)',
#                     redline_text, re.DOTALL
#                 )
#                 for replace_text, with_text in pairs:
#                     r_ = re.sub(r'(?i)^replace\s*:\s*', '', replace_text.strip()).strip().strip('"').strip("'")
#                     w_ = re.sub(r'(?i)^with\s*:\s*', '', with_text.strip()).strip().strip('"').strip("'")
#                     JUNK = {"none", "-", "**", "no changes needed", ""}
#                     if r_.lower() in JUNK or w_.lower() in JUNK or r_ == w_:
#                         continue
#                     r_ = r_.rstrip("*\n").strip().rstrip('"').strip()
#                     w_ = w_.rstrip("*\n").strip().rstrip('"').strip()
#                     if r_ and w_ and r_ != w_:
#                         redlines.append({"replace": r_, "with": w_})
#                 redline_summary = redline_text[:500]

#         nc_match = re.search(r"NEW_CLAUSE:\s*(.*?)(?=REASONING:|$)", response, re.DOTALL)
#         if nc_match:
#             nc_text = nc_match.group(1).strip()
#             if nc_text.lower() not in ("none", "none.", ""):
#                 for entry in re.split(r"(?=TITLE:)", nc_text):
#                     entry = entry.strip()
#                     if not entry:
#                         continue
#                     title_m  = re.search(r"TITLE:\s*(.+?)(?=REASON:|TEXT:|$)",  entry, re.DOTALL)
#                     reason_m = re.search(r"REASON:\s*(.+?)(?=TEXT:|$)",          entry, re.DOTALL)
#                     text_m   = re.search(r"TEXT:\s*(.+?)$",                      entry, re.DOTALL)
#                     if title_m and text_m:
#                         nc_title  = title_m.group(1).strip().strip('"')
#                         nc_reason = reason_m.group(1).strip() if reason_m else ""
#                         nc_text_v = text_m.group(1).strip().strip('"')
#                         nc_title  = re.sub(r"[\n\r]*[-*]+\s*$", "", nc_title).strip()
#                         nc_text_v = re.sub(r"\*\*\s*$", "", nc_text_v).strip()
#                         if nc_title and nc_text_v and len(nc_text_v) >= 20:
#                             new_clauses.append({"title": nc_title, "reason": nc_reason, "text": nc_text_v})

#         reason_match = re.search(r"REASONING:\s*(.*?)$", response, re.DOTALL)
#         if reason_match:
#             reasoning = reason_match.group(1).strip()
#             reasoning = re.sub(r"\s*\*\*\s*$", "", reasoning).strip()

#         _FORMAT_LEAK = re.compile(
#             r"^(RISK_LEVEL|REDLINES?|REPLACE|WITH|NEW_CLAUSE|REASONING|ISSUES?)\s*:\s*",
#             re.IGNORECASE | re.MULTILINE
#         )
#         issues          = [_FORMAT_LEAK.sub("", i).strip() for i in issues if i.strip()]
#         cleaned_pairs   = [
#             (iss, ev) for iss, ev in zip(issues, evidence_quotes)
#             if len(iss.strip()) >= 10
#         ]
#         issues          = [p[0] for p in cleaned_pairs]
#         evidence_quotes = [p[1] for p in cleaned_pairs]

#         for nc in new_clauses:
#             nc["text"] = re.sub(r"\*\*\s*$", "", nc.get("text", "")).strip().strip('"')

#         return ClauseReview(
#             clause_id=clause.clause_id,
#             number=clause.number,
#             heading=clause.heading,
#             clause_type=clause.clause_type,
#             risk_level=risk_level,
#             issues=issues,
#             evidence_quotes=evidence_quotes,
#             redline_suggestion=redline_summary,
#             redlines=redlines,
#             new_clauses=new_clauses,
#             reasoning=reasoning,
#             original_text=clause.text,
#             page_num=getattr(clause, "page_hint", 0),
#         )

#     def _parse_json_response(self, response: str) -> Optional[dict]:
#         clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
#         try:
#             return json.loads(clean)
#         except json.JSONDecodeError:
#             m = re.search(r"\{.*\}", clean, re.DOTALL)
#             if m:
#                 try:
#                     return json.loads(m.group())
#                 except Exception:
#                     pass
#         return None


# # Singleton
# review_pipeline = ReviewPipeline()

"""
core/review_pipeline.py — Parallel Contract Review Pipeline

Architecture:
  - Metadata extraction runs concurrently with first clause batch
  - All clauses reviewed in parallel (asyncio + semaphore, 10 workers)
  - Single-pass fused prompt (evidence + review in ONE LLM call)
  - Sync wrapper so existing main.py / CLI code needs zero changes

Performance on RTX 6000 Pro (95GB) with Qwen2.5 14B:
  Sequential (old): ~4s/clause × 46 = ~184s
  Parallel fused:   ~15-20s total wall clock
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from core.llm import llm, async_llm
from core.config import config
from ingestion.parser import parser, ParsedDocument
from ingestion.segmenter import segmenter, Clause
from prompts.review_prompts import (
    SYSTEM_CONTRACT_REVIEWER,
    SYSTEM_METADATA_EXTRACTOR,
    prompt_extract_metadata,
    prompt_review_clause_fused,
    prompt_triage_clause,
    prompt_contract_summary,
)

# RAG retriever (optional)
try:
    from rag.retriever import retriever
    RAG_ENABLED = True
except Exception:
    retriever = None
    RAG_ENABLED = False

console = Console()

_SIG_FRAGMENT_RE = re.compile(
    r"^(signed|printed|approved as to|consultant\s*consultant|commission\s*commission"
    r"|transportation commission\s*transportation|distribution\s*:|exhibit\s+[ab]"
    r"|fee schedule|in witness whereof)",
    re.IGNORECASE,
)


# ------------------------------------------------------------------
# Data Models (unchanged)
# ------------------------------------------------------------------

@dataclass
class ClauseReview:
    clause_id:          str
    number:             str
    heading:            str
    clause_type:        str
    risk_level:         str
    issues:             list[str]  = field(default_factory=list)
    evidence_quotes:    list[str]  = field(default_factory=list)
    redline_suggestion: str        = ""
    redlines:           list[dict] = field(default_factory=list)
    new_clauses:        list[dict] = field(default_factory=list)
    reasoning:          str        = ""
    original_text:      str        = ""
    page_num:           int        = 0
    escalated:          bool       = False


@dataclass
class ContractReviewReport:
    filename:          str
    reviewed_at:       str
    metadata:          dict
    total_clauses:     int
    high_risk_count:   int
    medium_risk_count: int
    low_risk_count:    int
    acceptable_count:  int
    clause_reviews:    list[ClauseReview] = field(default_factory=list)
    executive_summary: str = ""
    recommendation:    str = ""

    @property
    def overall_risk(self) -> str:
        if self.high_risk_count > 0:
            return "HIGH"
        elif self.medium_risk_count > 2:
            return "MEDIUM"
        return "LOW"


# ------------------------------------------------------------------
# Review Pipeline
# ------------------------------------------------------------------

class ReviewPipeline:

    def review_file(self, file_path) -> ContractReviewReport:
        """Sync entry point — wraps async pipeline for CLI/main.py compat."""
        return asyncio.run(self._review_file_async(file_path))

    # ------------------------------------------------------------------
    # Async orchestrator
    # ------------------------------------------------------------------

    async def _review_file_async(self, file_path) -> ContractReviewReport:
        start = time.time()
        path  = Path(file_path)

        console.print(f"\n[bold cyan]📄 Contract Review Agent[/bold cyan]")
        console.print(f"[dim]File: {path.name}[/dim]\n")

        # ── Step 1: Parse ───────────────────────────────────────────────
        t = time.time()
        with console.status("[bold]Parsing document...[/bold]"):
            doc = parser.parse(path)
        parse_time = time.time() - t
        console.print(f"[green]✓[/green] Parsed: {doc.word_count} words, {len(doc.pages)} pages [dim]({parse_time:.2f}s)[/dim]")

        # ── Step 2: Segment ─────────────────────────────────────────────
        t = time.time()
        with console.status("[bold]Segmenting clauses...[/bold]"):
            clauses = segmenter.segment(doc)
            summary = segmenter.get_clause_summary(clauses)
        segment_time = time.time() - t
        console.print(f"[green]✓[/green] Found {summary['total_clauses']} clauses [dim]({segment_time:.2f}s)[/dim]")

        # ── Step 3+4: Metadata + Clause review IN PARALLEL ─────────────
        console.print(f"\n[bold]Reviewing {len(clauses)} clauses in parallel...[/bold]")
        t = time.time()

        # Fire metadata and all clause reviews simultaneously
        metadata_task = asyncio.create_task(self._extract_metadata_async(doc))
        review_tasks  = [
            asyncio.create_task(self._review_single_clause_async(clause))
            for clause in clauses
        ]

        # Progress bar — updates as each clause completes
        clause_reviews_ordered = [None] * len(clauses)
        completed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
            transient=False,
        ) as progress:
            task_bar = progress.add_task("Reviewing...", total=len(clauses))

            pending = {t: i for i, t in enumerate(review_tasks)}
            futures = set(review_tasks)

            while futures:
                done, futures = await asyncio.wait(
                    futures, return_when=asyncio.FIRST_COMPLETED
                )
                for fut in done:
                    idx    = pending[fut]
                    review = fut.result()
                    clause_reviews_ordered[idx] = review
                    completed += 1
                    color = {"HIGH": "red", "MEDIUM": "yellow",
                             "LOW": "blue", "ACCEPTABLE": "green"}.get(review.risk_level, "white")
                    progress.console.print(
                        f"  [{color}]{review.risk_level}[/{color}] — "
                        f"{review.heading or review.clause_type or clauses[idx].clause_id}"
                    )
                    progress.advance(task_bar)

        review_time = time.time() - t

        # Wait for metadata (almost certainly done already)
        metadata = await metadata_task
        metadata_time = review_time   # ran in parallel — no extra wall time

        parties_str = ", ".join(metadata.get("parties", ["Unknown"]))
        console.print(f"[green]✓[/green] Metadata: {metadata.get('contract_type','Unknown')} | {parties_str}")

        # ── Step 4.5: Contradiction resolver ───────────────────────────
        clause_reviews = self._resolve_contradictions(clause_reviews_ordered)

        # ── Step 5: Executive summary ───────────────────────────────────
        t = time.time()
        with console.status("[bold]Generating executive summary...[/bold]"):
            reviews_as_dicts = [
                {
                    "heading":    r.heading or r.clause_type,
                    "risk_level": r.risk_level,
                    "issues":     " | ".join(r.issues),
                    "redlines":   r.redlines,
                }
                for r in clause_reviews
            ]
            exec_summary = self._generate_summary(reviews_as_dicts, metadata)
        summary_time = time.time() - t

        total_time = time.time() - start

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
    # Async Metadata Extraction
    # ------------------------------------------------------------------

    async def _extract_metadata_async(self, doc: ParsedDocument) -> dict:
        prompt = prompt_extract_metadata(doc.raw_text)
        try:
            response = await async_llm.fast_generate(
                prompt=prompt,
                system=SYSTEM_METADATA_EXTRACTOR,
            )
            return self._parse_json_response(response) or {}
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            return {
                "contract_type": doc.metadata.get("title", "Unknown"),
                "parties": [], "effective_date": None,
                "expiration_date": None, "governing_law": None,
            }

    # Keep sync version for backwards compat
    def _extract_metadata(self, doc: ParsedDocument) -> dict:
        prompt = prompt_extract_metadata(doc.raw_text)
        try:
            response = llm.generate(
                prompt=prompt, system=SYSTEM_METADATA_EXTRACTOR,
                model=config.FAST_MODEL, temperature=0.0, max_tokens=512,
            )
            return self._parse_json_response(response) or {}
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            return {}

    # ------------------------------------------------------------------
    # Async Single-Clause Review (fused single pass)
    # ------------------------------------------------------------------

    async def _review_single_clause_async(self, clause, governing_law: str = "") -> ClauseReview:
        """
        Two-tier triage + deep review.

        Tier 1 (all clauses): fast triage - just RISK_LEVEL + one line. ~60 tokens.
        Tier 2 (HIGH/MEDIUM only): full deep review with redlines + new clauses. ~700 tokens.

        LOW/ACCEPTABLE clauses skip Tier 2 entirely - 60-70% of clauses never hit deep review.
        Result: 60% fewer total output tokens -> ~60% faster wall clock.
        """
        text_stripped    = clause.text.strip()
        heading_stripped = (clause.heading or "").strip()

        # Hard skip: signature fragments
        if _SIG_FRAGMENT_RE.match(text_stripped) or _SIG_FRAGMENT_RE.match(heading_stripped):
            return ClauseReview(
                clause_id=clause.clause_id, number=clause.number,
                heading=clause.heading, clause_type=clause.clause_type,
                risk_level="ACCEPTABLE", issues=[],
                reasoning="Skipped - execution/signature fragment.",
                original_text=clause.text,
                page_num=getattr(clause, "page_hint", 0),
            )

        # Soft skip: short admin clauses
        SKIP_KEYWORDS = {
            "by name:", "title:", "cin :", "www.", "website :", "email :",
            "address :", "signed by", "print name",
        }
        if (clause.clause_type == "general" and len(clause.text) < 300
                and any(kw in clause.text.lower() for kw in SKIP_KEYWORDS)):
            return ClauseReview(
                clause_id=clause.clause_id, number=clause.number,
                heading=clause.heading, clause_type=clause.clause_type,
                risk_level="ACCEPTABLE", issues=[],
                reasoning="Skipped - administrative content.",
                original_text=clause.text,
                page_num=getattr(clause, "page_hint", 0),
            )

        is_recital      = clause.metadata.get("is_recital", False)
        is_borello      = clause.metadata.get("is_borello_factor", False)
        if is_borello:
            is_recital = True
        placeholder_pct = clause.metadata.get("placeholder_pct", 0.0)
        is_template     = placeholder_pct > 0.04

        try:
            # ── TIER 1: Fast triage (every clause) ───────────────────────
            triage_enabled = getattr(config, "ENABLE_TRIAGE", True)

            if triage_enabled and not is_recital:
                triage_response = await async_llm.triage(
                    prompt=prompt_triage_clause(
                        clause_text=clause.text,
                        clause_type=clause.clause_type,
                        clause_heading=clause.heading or "",
                    ),
                    system=SYSTEM_CONTRACT_REVIEWER,
                )
                triage_risk = self._parse_triage_risk(triage_response)

                # LOW / ACCEPTABLE: skip deep review, return triage result directly
                if triage_risk in ("LOW", "ACCEPTABLE"):
                    triage_reason = self._parse_triage_reason(triage_response)
                    return ClauseReview(
                        clause_id=clause.clause_id, number=clause.number,
                        heading=clause.heading, clause_type=clause.clause_type,
                        risk_level=triage_risk,
                        issues=[triage_reason] if triage_reason and triage_reason != "No significant issues" else [],
                        reasoning=triage_reason,
                        original_text=clause.text,
                        page_num=getattr(clause, "page_hint", 0),
                    )
                # HIGH / MEDIUM: fall through to full deep review below

            # ── TIER 2: Full deep review (HIGH/MEDIUM only) ──────────────
            playbook_context = ""
            if RAG_ENABLED and retriever is not None:
                try:
                    playbook_context = retriever.get_context_for_clause(
                        clause_type=clause.clause_type,
                        clause_text=clause.text,
                        governing_law=governing_law or None,
                    )
                except Exception:
                    pass

            response = await async_llm.generate(
                prompt=prompt_review_clause_fused(
                    clause_text=clause.text,
                    clause_type=clause.clause_type,
                    clause_heading=clause.heading,
                    playbook_context=playbook_context,
                    is_recital=is_recital,
                    is_template=is_template,
                ),
                system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.1,
                max_tokens=2048,
                num_ctx=1024,
            )

            review = self._parse_review_response(response, clause)

            # Recital cap
            if is_recital:
                if review.risk_level in ("HIGH", "MEDIUM"):
                    review.risk_level = "LOW"
                    review.reasoning  = (
                        "[Recital/WHEREAS clause - narrative only, no legal force. "
                        "Risk capped at LOW.] " + review.reasoning
                    )

            # Template note
            if is_template and not review.reasoning.startswith("[Template"):
                review.reasoning = (
                    f"[Template clause - {placeholder_pct*100:.0f}% unfilled placeholders. "
                    "Review once values are filled in.] " + review.reasoning
                )
                review.evidence_quotes = [""] * len(review.evidence_quotes)

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

    def _parse_triage_risk(self, response: str) -> str:
        """Extract RISK_LEVEL from triage response."""
        m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
        return m.group(1).upper() if m else "MEDIUM"  # default to MEDIUM if unparseable

    def _parse_triage_reason(self, response: str) -> str:
        """Extract REASON from triage response."""
        m = re.search(r"REASON:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    # ------------------------------------------------------------------
    # Evidence Filter
    # ------------------------------------------------------------------

    def _filter_hallucinated_evidence(self, evidence_quotes: list, clause_text: str) -> list:
        clause_lower = clause_text.lower()
        cleaned = []
        for ev in evidence_quotes:
            ev_clean = ev.strip().strip('"').strip("'")
            key = ev_clean[:max(12, int(len(ev_clean) * 0.85))].lower()
            cleaned.append(ev_clean if key and key in clause_lower else "")
        return cleaned

    # ------------------------------------------------------------------
    # Summary (sync — runs after all clauses done)
    # ------------------------------------------------------------------

    def _generate_summary(self, reviews: list, metadata: dict) -> str:
        prompt = prompt_contract_summary(reviews, metadata)
        try:
            return llm.generate(
                prompt=prompt, system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.2, max_tokens=1500,
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Summary generation failed. Please review individual clause results."

    # ------------------------------------------------------------------
    # Report Assembly
    # ------------------------------------------------------------------

    def _assemble_report(self, filename, metadata, clause_reviews, executive_summary) -> ContractReviewReport:
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "ACCEPTABLE": 0}
        for r in clause_reviews:
            level = r.risk_level.upper()
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
    # Contradiction Resolver (unchanged)
    # ------------------------------------------------------------------

    def _resolve_contradictions(self, reviews: list) -> list:
        RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "ACCEPTABLE": 0}
        RISK_NAMES = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "ACCEPTABLE"}
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
            type_max = max_risk_per_type[r.clause_type]
            this_lvl = RISK_ORDER.get(r.risk_level, 0)
            if type_max - this_lvl >= 2:
                old_level = r.risk_level
                new_level = RISK_NAMES[this_lvl + 1]
                r.risk_level = new_level
                r.escalated  = True
                r.reasoning  = (
                    f"[Consistency: escalated {old_level} → {new_level} because another "
                    f"{r.clause_type} clause was rated {RISK_NAMES[type_max]}.] " + r.reasoning
                )
        return reviews

    # ------------------------------------------------------------------
    # Response Parser (unchanged)
    # ------------------------------------------------------------------

    def _parse_review_response(self, response: str, clause) -> ClauseReview:
        risk_level      = "LOW"
        issues          = []
        evidence_quotes = []
        redlines        = []
        new_clauses     = []
        redline_summary = ""
        reasoning       = ""

        m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
        if m:
            risk_level = m.group(1).upper()

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
                if not issues:
                    for line in issues_text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line and len(line) > 10:
                            issues.append(line)
                            evidence_quotes.append("")

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
                    w_ = re.sub(r'(?i)^with\s*:\s*', '', with_text.strip()).strip().strip('"').strip("'")
                    JUNK = {"none", "-", "**", "no changes needed", ""}
                    if r_.lower() in JUNK or w_.lower() in JUNK or r_ == w_:
                        continue
                    r_ = r_.rstrip("*\n").strip().rstrip('"').strip()
                    w_ = w_.rstrip("*\n").strip().rstrip('"').strip()
                    if r_ and w_ and r_ != w_:
                        redlines.append({"replace": r_, "with": w_})
                redline_summary = redline_text[:500]

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
                        nc_title  = re.sub(r"[\n\r]*[-*]+\s*$", "", nc_title).strip()
                        nc_text_v = re.sub(r"\*\*\s*$", "", nc_text_v).strip()
                        if nc_title and nc_text_v and len(nc_text_v) >= 20:
                            new_clauses.append({"title": nc_title, "reason": nc_reason, "text": nc_text_v})

        reason_match = re.search(r"REASONING:\s*(.*?)$", response, re.DOTALL)
        if reason_match:
            reasoning = reason_match.group(1).strip()
            reasoning = re.sub(r"\s*\*\*\s*$", "", reasoning).strip()

        _FORMAT_LEAK = re.compile(
            r"^(RISK_LEVEL|REDLINES?|REPLACE|WITH|NEW_CLAUSE|REASONING|ISSUES?)\s*:\s*",
            re.IGNORECASE | re.MULTILINE
        )
        issues          = [_FORMAT_LEAK.sub("", i).strip() for i in issues if i.strip()]
        cleaned_pairs   = [
            (iss, ev) for iss, ev in zip(issues, evidence_quotes)
            if len(iss.strip()) >= 10
        ]
        issues          = [p[0] for p in cleaned_pairs]
        evidence_quotes = [p[1] for p in cleaned_pairs]

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