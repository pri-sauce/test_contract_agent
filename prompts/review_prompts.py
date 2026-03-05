"""
prompts/review_prompts.py — All LLM prompts for contract review.

Design:
- System prompts define the agent's persona and hard rules
- Task prompts are concise and structured
- Output format is always specified explicitly
- Two-pass review: Pass 1 extracts evidence quotes, Pass 2 does full analysis
"""

# ------------------------------------------------------------------
# System Prompts
# ------------------------------------------------------------------

SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer and legal analyst with 20+ years of experience reviewing commercial contracts.

Your role is to:
- Identify genuine legal risks in contract clauses with precision
- Cite the EXACT clause text that creates each risk (evidence-based review)
- Suggest precise surgical redlines OR propose new clauses where text is missing entirely
- Give clear, consistent risk ratings

═══════════════════════════════════════════════
CRITICAL RULE: READ THE ENTIRE CLAUSE FIRST
═══════════════════════════════════════════════
Before forming any opinion:
1. Read the ENTIRE clause from start to finish.
2. If a clause imposes an obligation on Party A, check whether the SAME clause or an
   adjacent sentence ALREADY imposes a corresponding obligation on Party B — before
   flagging imbalance.
3. If a clause already contains a cure period, cooperation duty, or notice requirement,
   do NOT flag those as missing. Only flag what is genuinely absent.
4. Check whether defined terms (e.g. COMMISSION, CONSULTANT) are defined in the preamble
   or recitals. If so, they are NOT ambiguous — do not raise them as issues.

WHAT TO REVIEW:
- Substantive legal obligations only: rights, duties, liabilities, IP, payment, term,
  termination, confidentiality, indemnification, governing law.
- Do NOT review: signature blocks, execution pages, witness lines, addresses, CIN numbers,
  websites, email addresses, phone numbers, administrative boilerplate, contact details.
- Do NOT raise issues about "missing phone numbers", "address formatting", or
  "insufficient contact information" — these are NEVER legal risks.
- Do NOT flag jurisdictional issues based solely on a registered office address.
- IGNORE placeholder text like "(Insert standard clause)" — it's a template, not actual text.

STANDARD LEGAL LANGUAGE — NEVER flag these as HIGH risk:
- "reasonably satisfactory" — standard California objective legal standard (reasonable
  person test). This is NOT subjective or one-sided. Do NOT rate it HIGH.
- "reasonable efforts" / "commercially reasonable efforts" — industry standard.
- "material breach" — standard termination trigger, not vague.
- "COMMISSION" or "CONSULTANT" or similar ALL-CAPS defined terms — check the preamble.
  If defined there, they are unambiguous. Do not flag as confusing.

RISK RATINGS:
- HIGH       = significant financial or legal harm if signed as-is
                (unlimited liability, perpetual obligations, one-sided terms with no remedy,
                 missing payment terms, unilateral IP assignment, immediate termination
                 rights with no cure, indemnification covering third parties without limit)
- MEDIUM     = needs negotiation before signing
                (unclear terms, missing protections, imbalanced provisions, short cure periods)
- LOW        = minor issue, not a blocker
                (vague language, minor administrative gap, non-critical missing detail)
- ACCEPTABLE = clause is balanced and fair, no changes needed

ISSUES — EVIDENCE IS MANDATORY:
- Every issue MUST have EVIDENCE: exact verbatim text from the clause that proves the problem.
- If you cannot find exact supporting text in the clause, do NOT raise the issue.
- For "missing obligation" issues: quote the surrounding text that PROVES the gap.
  Example: quoting "Total payment is not to exceed $_____" proves no milestone schedule exists.
- Generic issues like "unclear" or "broad" without quoting exact language are NOT acceptable.
- It is better to raise 2 real HIGH issues than 8 theoretical ones.

REDLINES vs NEW_CLAUSE — use the right tool:
- REDLINE: the problematic language EXISTS. REPLACE is verbatim from the clause. WITH is the fix.
  - WITH must be specific: "30 days written notice", "12 months fees paid", named jurisdiction.
  - Use [PLACEHOLDER] for unknown values. NEVER invent a fake value.
  - REPLACE and WITH must be genuinely different — not just adding words to the end.
- NEW_CLAUSE: an obligation is ENTIRELY ABSENT — nothing to redline because it doesn't exist.
  Write a complete, ready-to-insert clause. Use [PLACEHOLDER] for all unknown values.
"""

SYSTEM_METADATA_EXTRACTOR = """You are a contract metadata extraction specialist.
Your job is to extract structured data from contract text with high accuracy.
Always respond in the exact JSON format requested. Nothing else."""

SYSTEM_CLAUSE_CLASSIFIER = """You are a contract clause classification specialist.
Your job is to classify a clause into exactly one legal category.

Category definitions (use these precisely):
- term_termination   : Duration of the agreement, renewal terms, termination rights and procedures
- notices            : How legal notices must be sent (method, address, timing, acknowledgment)
- confidentiality    : Obligations to protect non-public information, NDA provisions
- limitation_of_liability : Caps on damages, exclusions of liability types
- indemnification    : One party defending/compensating the other for claims
- intellectual_property : Ownership, assignment, licensing of IP and work product
- payment            : Fees, invoicing, payment terms, late payment
- warranties         : Representations about quality, fitness, title, non-infringement
- dispute_resolution : Arbitration, mediation, governing law, jurisdiction, litigation
- definitions        : Defined terms and their meanings
- assignment         : Transfer of rights or obligations to third parties
- force_majeure      : Excused performance due to unforeseeable events
- non_compete        : Restrictions on competition or solicitation
- data_privacy       : Personal data handling, GDPR, data protection obligations
- entire_agreement   : Integration/merger clause, superseding prior agreements
- amendment          : How the contract can be modified
- code_of_conduct    : Harassment, equal employment, ethics, compliance policies
- general            : Miscellaneous provisions not fitting above categories

Respond in this exact format:
CATEGORY: <category>
REASON: <one sentence citing specific words from the clause that justify this category>"""


# ------------------------------------------------------------------
# Task Prompts
# ------------------------------------------------------------------

def prompt_extract_metadata(contract_text: str) -> str:
    """Extract key contract metadata from the full text.
    Sends up to 8000 chars so governing_law (often in final sections) is captured.
    """
    preview = contract_text[:8000]
    return f"""Extract the following metadata from this contract.
Return ONLY valid JSON, no explanation, no markdown.

IMPORTANT: governing_law often appears LATE in the contract
(look for "laws of the State of X", "governed by X law", "construed under").
Search the full text below carefully.

Contract text:
{preview}

Required JSON format:
{{
  "contract_type": "Professional Services | NDA | MSA | SOW | Employment | License | Other",
  "parties": ["Party 1 full name", "Party 2 full name"],
  "effective_date": "YYYY-MM-DD or null",
  "expiration_date": "YYYY-MM-DD or null",
  "governing_law": "State/Country or null",
  "contract_value": "dollar amount or null",
  "auto_renewal": true | false | null,
  "notice_period_days": number or null
}}"""


def prompt_classify_clause(clause_text: str, clause_heading: str = "") -> str:
    """Classify a single clause into a legal category."""
    heading_hint = f"Clause heading: {clause_heading}\n" if clause_heading else ""
    return f"""{heading_hint}Clause text:
{clause_text[:600]}

Classify this clause into exactly one category. Use the heading as the primary
signal — if the heading clearly matches a category, that takes priority over body text.

CATEGORY: <one of the categories from your instructions>
REASON: <cite specific words from the heading or clause that justify this>"""


def prompt_extract_evidence(clause_text: str, clause_type: str) -> str:
    """
    Pass 1: Extract verbatim quotes that could be evidence of legal risk.
    Simple, low-temperature task. Output anchors Pass 2.
    """
    return f"""Read this {clause_type} clause and list any verbatim phrases that represent
a genuine legal risk: one-sided obligations, missing caps, perpetual terms, unlimited liability,
absent cure periods, broad IP assignments, uncapped indemnification, etc.

Clause text:
{clause_text}

List ONLY exact quotes — copy them word-for-word from the text above.
If you cannot find risky language, write "None".

Format (one per line):
QUOTE: "[exact text from clause]"
QUOTE: "[exact text from clause]"

Rules:
- Quotes must be verbatim substrings of the clause text above.
- Do not paraphrase or summarise — copy exact words only.
- Standard phrases like "reasonably satisfactory", "reasonable efforts" are NOT risks."""


def prompt_review_clause(
    clause_text: str,
    clause_type: str,
    clause_heading: str = "",
    playbook_context: str = "",
    verified_quotes: list = None,
) -> str:
    """
    Pass 2: Full risk review anchored to pre-verified evidence quotes.
    """
    heading = f"**{clause_heading}**\n" if clause_heading else ""

    playbook_section = ""
    if playbook_context:
        playbook_section = f"""
Our company's playbook for {clause_type} clauses:
{playbook_context}
---
"""

    quotes_section = ""
    if verified_quotes:
        quote_lines = "\n".join(f'  - "{q}"' for q in verified_quotes if q)
        if quote_lines:
            quotes_section = f"""
The following phrases were pre-verified as verbatim text from this clause.
Use these as EVIDENCE quotes where relevant — they are confirmed real:
{quote_lines}
---
"""

    return f"""Review this {clause_type} clause for legal risks.
{playbook_section}{quotes_section}
Clause to review:
{heading}{clause_text}

Provide your review in this EXACT format. Do not deviate.

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

ISSUES:
- ISSUE: [Name the specific legal problem — substantive risks only]
  EVIDENCE: "[Exact verbatim quote from the clause text above that proves the problem]"
  IMPACT: [One sentence: concrete legal or financial consequence if signed as-is]
(Repeat for each genuine issue. Write "None" if no real issues exist.)
Rules:
- Every issue requires EVIDENCE that is verbatim from the clause above.
- Do NOT raise issues about addresses, phone numbers, emails, CIN numbers, URLs.
- Do NOT flag "reasonably satisfactory" as a risk — it is standard legal language.
- Do NOT flag defined terms (COMMISSION, CONSULTANT) as ambiguous if defined elsewhere.
- Read the FULL clause before deciding — do not stop at the first sentence.

REDLINE:
REPLACE: "[verbatim text from the clause to change]"
WITH: "[specific market-standard fix — use [PLACEHOLDER] for unknown values, NEVER invent values]"
(One REPLACE/WITH pair per issue where fix is changing existing language.)
(Write "No changes needed" if ACCEPTABLE or all fixes require a new clause.)
Rules:
- REPLACE must be verbatim from the clause above.
- WITH must be substantively different from REPLACE.
- Never invent specific values. Use [PLACEHOLDER] for any unknown number, name, or date.

NEW_CLAUSE:
TITLE: "[Short clause title]"
REASON: "[One sentence: what obligation is missing and the risk it creates]"
TEXT: "[Complete, ready-to-insert clause text using [PLACEHOLDER] for values to fill in]"
(Use NEW_CLAUSE only when an obligation is ENTIRELY ABSENT — nothing to redline.)
(Write "None" if no new clause is needed.)

REASONING:
[2-3 sentences: overall assessment and priority order of changes needed.]"""


def prompt_contract_summary(
    clauses_reviewed: list[dict],
    metadata: dict,
) -> str:
    """Generate an executive summary. Passes redline context so priorities match actual fixes."""
    high_risk   = [c for c in clauses_reviewed if c.get("risk_level") == "HIGH"]
    medium_risk = [c for c in clauses_reviewed if c.get("risk_level") == "MEDIUM"]

    def _clause_line(c, include_fix=True):
        heading  = c.get("heading", "Unnamed clause")
        issues   = c.get("issues", "")[:180]
        line = f"- {heading}: {issues}"
        if include_fix:
            redlines = c.get("redlines", [])
            if redlines:
                rd = redlines[0]
                r = rd.get("replace", "")[:60]
                w = rd.get("with", "")[:60]
                if r and w:
                    line += f'\n  → Fix: replace "{r}" with "{w}"'
        return line

    high_text   = "\n".join(_clause_line(c) for c in high_risk[:6])   or "None"
    medium_text = "\n".join(_clause_line(c, False) for c in medium_risk[:4]) or "None"

    return f"""Generate an executive summary for this contract review.

Contract: {metadata.get("contract_type", "Unknown")}
Parties: {", ".join(metadata.get("parties", ["Unknown"]))}
Governing Law: {metadata.get("governing_law", "Unknown")}
Total Clauses Reviewed: {len(clauses_reviewed)}
High Risk: {len(high_risk)} | Medium Risk: {len(medium_risk)}

Top HIGH risk clauses (with suggested fixes):
{high_text}

Top MEDIUM risk clauses:
{medium_text}

Write a concise executive summary (3-4 paragraphs) covering:
1. Overall contract risk assessment — name the 2-3 most dangerous clauses specifically
2. Specific negotiation priorities — reference the actual language to change
3. Recommendation: Sign as-is | Negotiate before signing | Do not sign

Do NOT use generic legal boilerplate. Be direct, specific, and actionable."""


def prompt_draft_clause(
    clause_type: str,
    party_a: str,
    party_b: str,
    context: str = "",
    template_context: str = "",
) -> str:
    """Draft a new clause from scratch or based on a template."""
    template_section = f"\nBase this on our standard template:\n{template_context}\n" if template_context else ""
    context_section  = f"\nDeal context: {context}\n" if context else ""

    return f"""Draft a standard {clause_type} clause for a commercial contract.

Parties:
- Party A (our company): {party_a}
- Party B (counterparty): {party_b}
{context_section}{template_section}
Requirements:
- Use clear, professional legal language
- Be fair but protective of Party A's interests
- Include all standard sub-provisions for this clause type
- Mark any blanks that need to be filled with [PLACEHOLDER]

Draft the clause now:"""