"""
ingestion/segmenter.py — Improved Clause Segmentation Pipeline
Breaks a contract into individual clauses for per-clause analysis.

Strategy: Enhanced pattern matching to handle various numbering formats dynamically.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from ingestion.parser import ParsedDocument


# ------------------------------------------------------------------
# Clause Data Model
# ------------------------------------------------------------------

@dataclass
class Clause:
    """
    A single extracted clause from a contract.
    """
    clause_id: str              # e.g. "clause_003"
    number: str                 # e.g. "3.2" or "Article IV" or ""
    heading: str                # e.g. "Limitation of Liability"
    text: str                   # Full clause text
    clause_type: str = ""       # Classified type (filled in review pipeline)
    risk_level: str = ""        # HIGH / MEDIUM / LOW (filled in review pipeline)
    page_hint: int = 0          # Approximate page number
    parent_clause: str = ""     # Parent clause number if nested
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Heading + body for display and LLM prompts."""
        if self.heading:
            return f"{self.number} {self.heading}\n{self.text}".strip()
        return f"{self.number}\n{self.text}".strip() if self.number else self.text

    def __len__(self):
        return len(self.text)


# ------------------------------------------------------------------
# Enhanced Clause Patterns (Rule-Based Detection)
# ------------------------------------------------------------------

# These patterns cover the most common contract numbering styles
CLAUSE_HEADER_PATTERNS = [
    # Numbered with leading zeros: 1.01, 2.01, 3.01, 10.01, etc. (with optional markdown bold)
    r"^\*?\*?(\d{1,2}\.\d{2})\*?\*?\s*[.:]?\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
    # Standard numbered: 1. , 1.1 , 1.1.1 , 12.3.4 (with optional markdown bold)
    r"^\*?\*?(\d{1,2}(?:\.\d{1,2}){0,3})\*?\*?\s*[.)]\s+\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
    # Numbered with colon: 1: Title, 2.1: Subtitle (with optional markdown bold)
    r"^\*?\*?(\d{1,2}(?:\.\d{1,2})?)\*?\*?\s*:\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*$",
    # Article: ARTICLE I , Article 1 , ARTICLE ONE
    r"^(ARTICLE\s+(?:[IVX]+|\d+))\s*[.:\-]?\s*\*?\*?([A-Z][^\n]{0,80})\*?\*?\s*$",
    # Section: SECTION 1 , Section 2.3
    r"^(SECTION\s+\d+(?:\.\d+)?)\s*[.:\-]?\s*\*?\*?([A-Z][^\n]{0,80})\*?\*?\s*$",
    # Lettered: A. , (a) , A)
    r"^([A-Z]\.|[A-Z]\)|[(][a-z][)])\s+\*?\*?([A-Z][^\n]{2,80})\*?\*?\s*$",
    # ALL CAPS heading (common in NDAs, employment contracts)
    r"^([A-Z][A-Z\s]{4,50}[A-Z])\s*:?\s*$",
    # Recitals / Whereas
    r"^(WHEREAS|RECITALS?|BACKGROUND|PREAMBLE)\b",
    # Definitions section entries
    r"^\"([A-Z][a-zA-Z\s]+)\"\s+(?:means|shall mean|refers to)",
]

COMPILED_PATTERNS = [re.compile(p, re.MULTILINE) for p in CLAUSE_HEADER_PATTERNS]

# Known clause type keywords for quick pre-classification
CLAUSE_TYPE_KEYWORDS = {
    "definitions": ["definition", "definitions", "defined terms", "means", "shall mean"],
    "term_termination": ["term of", "termination", "duration", "expire", "expiration",
                          "cancel", "cancellation", "auto-renew", "automatic renewal",
                          "notice of termination", "term and termination"],
    "payment": ["payment", "fees", "compensation", "invoice", "billing", "price", "cost", "financial terms"],
    "confidentiality": ["confidential", "nda", "non-disclosure", "proprietary", "trade secret"],
    "intellectual_property": ["intellectual property", "copyright", "patent", "trademark",
                                "ownership", "work for hire", "ip rights"],
    "limitation_of_liability": ["limitation of liability", "limit of liability", "liability cap",
                                  "not liable", "exclude liability", "shall not exceed",
                                  "consequential damages", "indirect damages", "unlimited liability"],
    "indemnification": ["indemnif", "defend", "hold harmless"],
    "warranties": ["warrant", "warranty", "representation", "represent", "guarantee"],
    "dispute_resolution": ["dispute", "arbitration", "mediation", "litigation",
                             "jurisdiction", "governing law"],
    "force_majeure": ["force majeure", "act of god", "beyond control"],
    "assignment": ["assign", "transfer", "novation", "subcontract"],
    "non_compete": ["non-compete", "noncompete", "competition", "competing",
                     "solicit", "non-solicit", "non-solicitation"],
    "data_privacy": ["personal data", "privacy", "gdpr", "personal information",
                      "data protection", "data subject"],
    "notices": ["notices", "notice shall be sent", "notice shall be given",
                 "written notice to", "notice address", "notice provision",
                 "notice section", "receipt of notice"],
    "entire_agreement": ["entire agreement", "merger clause", "integration clause", "supersede"],
    "amendment": ["amend", "amendment", "modify", "modification", "waiver"],
    "code_of_conduct": ["code of conduct", "ethical standards", "compliance", "company policies"],
    "acknowledgement": ["acknowledgement", "acceptance", "agree to the terms"],
}


class ClauseSegmenter:
    """
    Segments a parsed contract into individual clauses.
    
    Approach:
    1. Enhanced pattern matching for various numbering formats
    2. Line-by-line boundary detection
    3. Smart merging of orphaned lines
    4. Keyword-based pre-classification
    """

    def segment(self, doc: ParsedDocument) -> list[Clause]:
        """
        Main entry. Returns list of Clause objects ordered as they appear.
        """
        logger.info(f"Segmenting '{doc.filename}' ({doc.word_count} words)")

        text = doc.raw_text
        lines = text.split("\n")

        # Step 1: Find clause boundaries
        boundaries = self._find_boundaries(lines)
        
        logger.debug(f"Found {len(boundaries)} potential clause boundaries")

        # Step 2: Extract clause blocks between boundaries
        clauses = self._extract_clauses(lines, boundaries)

        # Step 3: Pre-classify clause types (keyword-based, fast)
        clauses = self._pre_classify(clauses)

        # Step 4: Filter noise (very short fragments that aren't real clauses)
        clauses = [c for c in clauses if len(c.text.strip()) > 50]

        # Step 5: Remove signature blocks and execution pages — not reviewable clauses
        clauses = [c for c in clauses if not self._is_signature_block(c)]

        logger.success(f"Segmented into {len(clauses)} clauses")
        return clauses

    # ------------------------------------------------------------------
    # Boundary Detection
    # ------------------------------------------------------------------

    def _find_boundaries(self, lines: list[str]) -> list[tuple[int, str, str, str]]:
        """
        Returns list of (line_index, clause_number, clause_heading, original_line) tuples.
        original_line is stored so body text on the header line is not lost when heading is empty.
        """
        boundaries = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(stripped) < 2:
                continue

            match_result = self._is_clause_header(stripped)
            if match_result:
                number, heading = match_result
                boundaries.append((i, number, heading, stripped))
                logger.debug(f"Line {i}: Found clause header - Number: '{number}', Heading: '{heading}'")

        return boundaries

    def _is_clause_header(self, line: str) -> Optional[tuple[str, str]]:
        """
        Check if a line is a clause header.
        Returns (number, heading) if yes, None if no.
        Heading may be empty — _extract_clauses derives it from body text.
        """
        # Strip markdown bold markers first
        clean_line = line.strip().replace("**", "").strip()
        
        for pattern in COMPILED_PATTERNS:
            match = pattern.match(clean_line)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    num   = groups[0].strip()
                    body  = groups[1].strip().rstrip(":").strip()
                    # Clean up any remaining markdown or formatting
                    body = body.replace("**", "").strip()
                    # If 'heading' is actually a full sentence (heading-less clause),
                    # return empty heading — _extract_clauses will derive a short one
                    heading = body if len(body) <= 80 else ""
                    return num, heading
                elif len(groups) == 1:
                    return groups[0].strip(), ""
                else:
                    return clean_line, ""

        # ALL CAPS line that looks like a heading (no pattern matched above)
        if (clean_line.isupper() and 3 <= len(clean_line.split()) <= 8
                and not clean_line.startswith("WHEREAS")
                and clean_line[0].isalpha()):
            return "", clean_line

        return None

    # ------------------------------------------------------------------
    # Clause Extraction
    # ------------------------------------------------------------------

    def _extract_clauses(
        self,
        lines: list[str],
        boundaries: list[tuple[int, str, str, str]]
    ) -> list[Clause]:
        """Build Clause objects from boundary markers."""
        clauses = []

        if not boundaries:
            # No structure detected — treat whole document as one block
            logger.warning("No clause boundaries detected. Falling back to paragraph chunking.")
            return self._paragraph_fallback(lines)

        for idx, (line_idx, number, heading, original_line) in enumerate(boundaries):
            # Determine end of this clause
            if idx + 1 < len(boundaries):
                end_idx = boundaries[idx + 1][0]
            else:
                end_idx = len(lines)

            # Collect body lines
            body_lines = lines[line_idx + 1:end_idx]
            body = "\n".join(body_lines).strip()

            # heading-less numbered clause: "1. The Receiving Party agrees..."
            # The first sentence is on the boundary line itself — prepend it to body
            if not heading and original_line:
                # Strip the number prefix (e.g. "1. " or "3.01 ") from original_line to get body start
                body_start = re.sub(r"^\*?\*?\d{1,2}(?:\.\d{1,2}|\.\d{2}){0,3}\*?\*?\s*[.):]\s*", "", original_line).strip()
                body_start = body_start.replace("**", "").strip()
                if body_start:
                    body = body_start + ("\n" + body if body else "")
                # Derive short heading: first 5-7 words, capitalised
                words = body_start.split()
                heading = " ".join(words[:6]) + ("..." if len(words) > 6 else "")

            # Heading from ALL CAPS pattern (no body on header line)
            elif not heading and body:
                first_line = body.split("\n")[0].strip()
                if len(first_line) < 100:
                    heading = first_line

            # Heading IS the full body sentence (e.g. matched with long body group)
            elif heading and len(heading) > 80:
                words = heading.split()
                short = " ".join(words[:6]) + "..."
                body = (heading + ("\n" + body if body else "")).strip()
                heading = short

            clause = Clause(
                clause_id=f"clause_{idx + 1:03d}",
                number=number,
                heading=heading,
                text=body,
                page_hint=self._estimate_page(line_idx, len(lines)),
            )
            clauses.append(clause)

        return clauses

    def _is_signature_block(self, clause) -> bool:
        """
        Detect signature blocks, execution pages, and witness sections.
        """
        heading = (clause.heading or "").upper().strip()
        text = (clause.text or "").strip()
        combined = heading + " " + text

        # Explicit signature section headings
        SIG_HEADINGS = {
            "IN WITNESS WHEREOF", "SIGNATURE PAGE", "EXECUTED BY", "EXECUTION PAGE",
            "SIGNATURES", "AGREED AND ACCEPTED", "AUTHORIZED SIGNATURES", "COUNTERPARTS",
            "ACKNOWLEDGEMENT AND ACCEPTANCE", "EMPLOYEE SIGNATURE PAGE", "EMPLOYER SIGNATURE PAGE",
        }
        if heading in SIG_HEADINGS:
            return True

        # Side-by-side party name pattern in heading
        sig_name_pattern = re.compile(
            r"^[A-Z][A-Z\s,.]+(CORPORATION|CORP|INC|LLC|LTD|CO|COMPANY|PARTNERS)[.\s]+"
            r"[A-Z][A-Z\s,.]+(CORPORATION|CORP|INC|LLC|LTD|CO|COMPANY|PARTNERS)",
            re.IGNORECASE
        )
        if sig_name_pattern.match(heading):
            return True

        # Short text with signature line artifacts
        sig_artifacts = ["___", "---", "signature:", "print name:", "title:", "date:", "employee's signature", "employer's signature"]
        artifact_count = sum(1 for a in sig_artifacts if a in combined.lower())
        if artifact_count >= 2 and len(text) < 300:
            return True

        return False

    def _paragraph_fallback(self, lines: list[str]) -> list[Clause]:
        """
        Fallback: split by double newlines (paragraph boundaries).
        """
        full_text = "\n".join(lines)
        paragraphs = re.split(r"\n{2,}", full_text)
        clauses = []

        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) > 50:
                clauses.append(Clause(
                    clause_id=f"clause_{idx + 1:03d}",
                    number="",
                    heading="",
                    text=para,
                    page_hint=0,
                ))

        return clauses

    # ------------------------------------------------------------------
    # Pre-Classification (Keyword-Based)
    # ------------------------------------------------------------------

    # Heading → canonical clause type map
    HEADING_OVERRIDES = {
        "term": "term_termination",
        "term and termination": "term_termination",
        "term of agreement": "term_termination",
        "duration": "term_termination",
        "termination": "term_termination",
        "effective date and term": "term_termination",
        "notice": "notices",
        "notices": "notices",
        "notice provisions": "notices",
        "governing law": "dispute_resolution",
        "dispute resolution": "dispute_resolution",
        "arbitration": "dispute_resolution",
        "limitation of liability": "limitation_of_liability",
        "limitations of liability": "limitation_of_liability",
        "indemnification": "indemnification",
        "indemnity": "indemnification",
        "confidentiality": "confidentiality",
        "intellectual property": "intellectual_property",
        "ip ownership": "intellectual_property",
        "payment": "payment",
        "payment and financial terms": "payment",
        "fees": "payment",
        "entire agreement": "entire_agreement",
        "assignment": "assignment",
        "force majeure": "force_majeure",
        "warranties": "warranties",
        "warranty": "warranties",
        "representations and warranties": "warranties",
        "non-compete": "non_compete",
        "non compete": "non_compete",
        "non-solicitation": "non_compete",
        "data privacy": "data_privacy",
        "data protection": "data_privacy",
        "amendment": "amendment",
        "amendment and waiver": "amendment",
        "amendments": "amendment",
        "severability": "general",
        "definitions": "definitions",
        "code of conduct": "code_of_conduct",
        "acknowledgement": "acknowledgement",
        "acknowledgement and acceptance": "acknowledgement",
    }

    def _pre_classify(self, clauses: list[Clause]) -> list[Clause]:
        """
        Keyword-based clause type labeling with heading priority.
        """
        for clause in clauses:
            clause.clause_type = self._detect_type(
                body_text=clause.text,
                heading=clause.heading,
            )
        return clauses

    def _detect_type(self, body_text: str, heading: str = "") -> str:
        """
        Classify a clause by type.
        Heading carries 3x weight — it was written by lawyers to name the clause.
        """
        # Step 1: exact heading override — fastest and most reliable
        heading_lower = heading.strip().lower()
        if heading_lower in self.HEADING_OVERRIDES:
            return self.HEADING_OVERRIDES[heading_lower]

        # Step 2: weighted scoring — heading keywords score 3x body keywords
        scores = {}
        heading_text = heading.lower()
        body_text_lower = body_text.lower()

        for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
            heading_score = sum(3 for kw in keywords if kw in heading_text)
            body_score = sum(1 for kw in keywords if kw in body_text_lower)
            total = heading_score + body_score
            if total > 0:
                scores[clause_type] = total

        if not scores:
            return "general"

        return max(scores, key=scores.get)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _estimate_page(self, line_idx: int, total_lines: int) -> int:
        """Rough page estimate based on line position."""
        lines_per_page = 45  # Approximate
        return max(1, line_idx // lines_per_page + 1)

    def get_clause_summary(self, clauses: list[Clause]) -> dict:
        """Returns a summary of what was found — useful for logging."""
        type_counts = {}
        for c in clauses:
            type_counts[c.clause_type] = type_counts.get(c.clause_type, 0) + 1

        return {
            "total_clauses": len(clauses),
            "clause_types": type_counts,
            "avg_clause_length": sum(len(c.text) for c in clauses) // max(len(clauses), 1),
        }


# Singleton
segmenter = ClauseSegmenter()
