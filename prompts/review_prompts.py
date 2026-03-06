# """
# prompts/review_prompts.py — All LLM prompts for contract review.

# Design:
# - System prompts define the agent's persona and hard rules
# - Task prompts are concise and structured
# - Output format is always specified explicitly
# - Two-pass review: Pass 1 extracts evidence quotes, Pass 2 does full analysis
# """

# # ------------------------------------------------------------------
# # System Prompts
# # ------------------------------------------------------------------

# SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer and legal analyst with 20+ years of experience reviewing commercial contracts.

# Your role is to:
# - Identify genuine legal risks in contract clauses with precision
# - Cite the EXACT clause text that creates each risk (evidence-based review)
# - Suggest precise surgical redlines OR propose new clauses where text is missing entirely
# - Give clear, consistent risk ratings

# ═══════════════════════════════════════════════
# CRITICAL RULE: READ THE ENTIRE CLAUSE FIRST
# ═══════════════════════════════════════════════
# Before forming any opinion:
# 1. Read the ENTIRE clause from start to finish.
# 2. If a clause imposes an obligation on Party A, check whether the SAME clause or an
#    adjacent sentence ALREADY imposes a corresponding obligation on Party B — before
#    flagging imbalance.
# 3. If a clause already contains a cure period, cooperation duty, or notice requirement,
#    do NOT flag those as missing. Only flag what is genuinely absent.
# 4. Check whether defined terms (e.g. COMMISSION, CONSULTANT) are defined in the preamble
#    or recitals. If so, they are NOT ambiguous — do not raise them as issues.

# WHAT TO REVIEW:
# - Substantive legal obligations only: rights, duties, liabilities, IP, payment, term,
#   termination, confidentiality, indemnification, governing law.
# - Do NOT review: signature blocks, execution pages, witness lines, addresses, CIN numbers,
#   websites, email addresses, phone numbers, administrative boilerplate, contact details.
# - Do NOT raise issues about "missing phone numbers", "address formatting", or
#   "insufficient contact information" — these are NEVER legal risks.
# - Do NOT flag jurisdictional issues based solely on a registered office address.
# - IGNORE placeholder text like "(Insert standard clause)" — it's a template, not actual text.

# STANDARD LEGAL LANGUAGE — NEVER flag these as HIGH risk:
# - "reasonably satisfactory" — standard California objective legal standard (reasonable
#   person test). This is NOT subjective or one-sided. Do NOT rate it HIGH.
# - "reasonable efforts" / "commercially reasonable efforts" — industry standard.
# - "material breach" — standard termination trigger, not vague.
# - "COMMISSION" or "CONSULTANT" or similar ALL-CAPS defined terms — check the preamble.
#   If defined there, they are unambiguous. Do not flag as confusing.

# RISK RATINGS:
# - HIGH       = significant financial or legal harm if signed as-is
#                 (unlimited liability, perpetual obligations, one-sided terms with no remedy,
#                  missing payment terms, unilateral IP assignment, immediate termination
#                  rights with no cure, indemnification covering third parties without limit)
# - MEDIUM     = needs negotiation before signing
#                 (unclear terms, missing protections, imbalanced provisions, short cure periods)
# - LOW        = minor issue, not a blocker
#                 (vague language, minor administrative gap, non-critical missing detail)
# - ACCEPTABLE = clause is balanced and fair, no changes needed

# ISSUES — EVIDENCE IS MANDATORY:
# - Every issue MUST have EVIDENCE: exact verbatim text from the clause that proves the problem.
# - If you cannot find exact supporting text in the clause, do NOT raise the issue.
# - For "missing obligation" issues: quote the surrounding text that PROVES the gap.
#   Example: quoting "Total payment is not to exceed $_____" proves no milestone schedule exists.
# - Generic issues like "unclear" or "broad" without quoting exact language are NOT acceptable.
# - It is better to raise 2 real HIGH issues than 8 theoretical ones.

# REDLINES vs NEW_CLAUSE — use the right tool:
# - REDLINE: the problematic language EXISTS. REPLACE is verbatim from the clause. WITH is the fix.
#   - WITH must be specific: "30 days written notice", "12 months fees paid", named jurisdiction.
#   - Use [PLACEHOLDER] for unknown values. NEVER invent a fake value.
#   - REPLACE and WITH must be genuinely different — not just adding words to the end.
# - NEW_CLAUSE: an obligation is ENTIRELY ABSENT — nothing to redline because it doesn't exist.
#   Write a complete, ready-to-insert clause. Use [PLACEHOLDER] for all unknown values.
# """

# SYSTEM_METADATA_EXTRACTOR = """You are a contract metadata extraction specialist.
# Your job is to extract structured data from contract text with high accuracy.
# Always respond in the exact JSON format requested. Nothing else."""

# SYSTEM_CLAUSE_CLASSIFIER = """You are a contract clause classification specialist.
# Your job is to classify a clause into exactly one legal category.

# Category definitions (use these precisely):
# - term_termination   : Duration of the agreement, renewal terms, termination rights and procedures
# - notices            : How legal notices must be sent (method, address, timing, acknowledgment)
# - confidentiality    : Obligations to protect non-public information, NDA provisions
# - limitation_of_liability : Caps on damages, exclusions of liability types
# - indemnification    : One party defending/compensating the other for claims
# - intellectual_property : Ownership, assignment, licensing of IP and work product
# - payment            : Fees, invoicing, payment terms, late payment
# - warranties         : Representations about quality, fitness, title, non-infringement
# - dispute_resolution : Arbitration, mediation, governing law, jurisdiction, litigation
# - definitions        : Defined terms and their meanings
# - assignment         : Transfer of rights or obligations to third parties
# - force_majeure      : Excused performance due to unforeseeable events
# - non_compete        : Restrictions on competition or solicitation
# - data_privacy       : Personal data handling, GDPR, data protection obligations
# - entire_agreement   : Integration/merger clause, superseding prior agreements
# - amendment          : How the contract can be modified
# - code_of_conduct    : Harassment, equal employment, ethics, compliance policies
# - general            : Miscellaneous provisions not fitting above categories

# Respond in this exact format:
# CATEGORY: <category>
# REASON: <one sentence citing specific words from the clause that justify this category>"""


# # ------------------------------------------------------------------
# # Task Prompts
# # ------------------------------------------------------------------

# def prompt_extract_metadata(contract_text: str) -> str:
#     """Extract key contract metadata from the full text.
#     Sends up to 8000 chars so governing_law (often in final sections) is captured.
#     """
#     preview = contract_text[:8000]
#     return f"""Extract the following metadata from this contract.
# Return ONLY valid JSON, no explanation, no markdown.

# IMPORTANT: governing_law often appears LATE in the contract
# (look for "laws of the State of X", "governed by X law", "construed under").
# Search the full text below carefully.

# Contract text:
# {preview}

# Required JSON format:
# {{
#   "contract_type": "Professional Services | NDA | MSA | SOW | Employment | License | Other",
#   "parties": ["Party 1 full name", "Party 2 full name"],
#   "effective_date": "YYYY-MM-DD or null",
#   "expiration_date": "YYYY-MM-DD or null",
#   "governing_law": "State/Country or null",
#   "contract_value": "dollar amount or null",
#   "auto_renewal": true | false | null,
#   "notice_period_days": number or null
# }}"""


# def prompt_classify_clause(clause_text: str, clause_heading: str = "") -> str:
#     """Classify a single clause into a legal category."""
#     heading_hint = f"Clause heading: {clause_heading}\n" if clause_heading else ""
#     return f"""{heading_hint}Clause text:
# {clause_text[:600]}

# Classify this clause into exactly one category. Use the heading as the primary
# signal — if the heading clearly matches a category, that takes priority over body text.

# CATEGORY: <one of the categories from your instructions>
# REASON: <cite specific words from the heading or clause that justify this>"""


# def prompt_extract_evidence(clause_text: str, clause_type: str) -> str:
#     """
#     Pass 1: Extract verbatim quotes that could be evidence of legal risk.
#     Simple, low-temperature task. Output anchors Pass 2.
#     """
#     return f"""Read this {clause_type} clause and list any verbatim phrases that represent
# a genuine legal risk: one-sided obligations, missing caps, perpetual terms, unlimited liability,
# absent cure periods, broad IP assignments, uncapped indemnification, etc.

# Clause text:
# {clause_text}

# List ONLY exact quotes — copy them word-for-word from the text above.
# If you cannot find risky language, write "None".

# Format (one per line):
# QUOTE: "[exact text from clause]"
# QUOTE: "[exact text from clause]"

# Rules:
# - Quotes must be verbatim substrings of the clause text above.
# - Do not paraphrase or summarise — copy exact words only.
# - Standard phrases like "reasonably satisfactory", "reasonable efforts" are NOT risks."""


# def prompt_review_clause(
#     clause_text: str,
#     clause_type: str,
#     clause_heading: str = "",
#     playbook_context: str = "",
#     verified_quotes: list = None,
#     is_recital: bool = False,
#     is_template: bool = False,
# ) -> str:
#     """
#     Pass 2: Full risk review anchored to pre-verified evidence quotes.
#     """
#     heading = f"**{clause_heading}**\n" if clause_heading else ""

#     # ── Special instructions for recitals ──────────────────────────────
#     recital_instruction = ""
#     if is_recital:
#         recital_instruction = """
# IMPORTANT: This is a RECITAL / WHEREAS clause — narrative background context only.
# Recitals have NO operative legal force. They cannot impose obligations or liabilities.
# - Maximum risk rating is LOW. Do NOT rate this HIGH or MEDIUM.
# - Do NOT raise issues about indemnification, liability, IP, or missing obligations.
# - Only flag genuine structural problems (e.g. contradicts operative clauses).
# - If no structural issues exist, rate ACCEPTABLE.
# ---
# """

#     # ── Special instructions for template/placeholder clauses ──────────
#     template_instruction = ""
#     if is_template:
#         template_instruction = """
# IMPORTANT: This clause contains unfilled template placeholders ([￿], [PLACEHOLDER],
# [INSERT...], ___, etc.). This is a draft template, not an executed contract.
# - Do NOT treat blank placeholders as missing obligations — they are intentional gaps.
# - Focus only on structural/legal issues visible in the existing language.
# - Do NOT fabricate evidence quotes from placeholder text.
# - Rate based on structure, not on missing placeholder values.
# ---
# """

#     playbook_section = ""
#     if playbook_context:
#         playbook_section = f"""
# Our company's playbook for {clause_type} clauses:
# {playbook_context}
# ---
# """

#     quotes_section = ""
#     if verified_quotes and not is_template:
#         quote_lines = "\n".join(f'  - "{q}"' for q in verified_quotes if q)
#         if quote_lines:
#             quotes_section = f"""
# The following phrases were pre-verified as verbatim text from this clause.
# Use these as EVIDENCE quotes where relevant — they are confirmed real:
# {quote_lines}
# ---
# """

#     return f"""Review this {clause_type} clause for legal risks.
# {recital_instruction}{template_instruction}{playbook_section}{quotes_section}
# Clause to review:
# {heading}{clause_text}

# Provide your review in this EXACT format. Do not deviate.

# RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

# ISSUES:
# - ISSUE: [Name the specific legal problem — substantive risks only]
#   EVIDENCE: "[Exact verbatim quote from the clause text above that proves the problem]"
#   IMPACT: [One sentence: concrete legal or financial consequence if signed as-is]
# (Repeat for each genuine issue. Write "None" if no real issues exist.)
# Rules:
# - Every issue requires EVIDENCE that is verbatim from the clause above.
# - Do NOT raise issues about addresses, phone numbers, emails, CIN numbers, URLs.
# - Do NOT flag "reasonably satisfactory" as a risk — it is standard legal language.
# - Do NOT flag defined terms (COMMISSION, CONSULTANT) as ambiguous if defined elsewhere.
# - Read the FULL clause before deciding — do not stop at the first sentence.

# REDLINE:
# REPLACE: "[verbatim text from the clause to change]"
# WITH: "[specific market-standard fix — use [PLACEHOLDER] for unknown values, NEVER invent values]"
# (One REPLACE/WITH pair per issue where fix is changing existing language.)
# (Write "No changes needed" if ACCEPTABLE or all fixes require a new clause.)
# Rules:
# - REPLACE must be verbatim from the clause above.
# - WITH must be substantively different from REPLACE.
# - Never invent specific values. Use [PLACEHOLDER] for any unknown number, name, or date.

# NEW_CLAUSE:
# TITLE: "[Short clause title]"
# REASON: "[One sentence: what obligation is missing and the risk it creates]"
# TEXT: "[Complete, ready-to-insert clause text using [PLACEHOLDER] for values to fill in]"
# (Use NEW_CLAUSE only when an obligation is ENTIRELY ABSENT — nothing to redline.)
# (Write "None" if no new clause is needed.)

# REASONING:
# [2-3 sentences: overall assessment and priority order of changes needed.]"""


# def prompt_contract_summary(
#     clauses_reviewed: list[dict],
#     metadata: dict,
# ) -> str:
#     """Generate an executive summary. Passes redline context so priorities match actual fixes."""
#     high_risk   = [c for c in clauses_reviewed if c.get("risk_level") == "HIGH"]
#     medium_risk = [c for c in clauses_reviewed if c.get("risk_level") == "MEDIUM"]

#     def _clause_line(c, include_fix=True):
#         heading  = c.get("heading", "Unnamed clause")
#         issues   = c.get("issues", "")[:180]
#         line = f"- {heading}: {issues}"
#         if include_fix:
#             redlines = c.get("redlines", [])
#             if redlines:
#                 rd = redlines[0]
#                 r = rd.get("replace", "")[:60]
#                 w = rd.get("with", "")[:60]
#                 if r and w:
#                     line += f'\n  → Fix: replace "{r}" with "{w}"'
#         return line

#     high_text   = "\n".join(_clause_line(c) for c in high_risk[:6])   or "None"
#     medium_text = "\n".join(_clause_line(c, False) for c in medium_risk[:4]) or "None"

#     return f"""Generate an executive summary for this contract review.

# Contract: {metadata.get("contract_type", "Unknown")}
# Parties: {", ".join(metadata.get("parties", ["Unknown"]))}
# Governing Law: {metadata.get("governing_law", "Unknown")}
# Total Clauses Reviewed: {len(clauses_reviewed)}
# High Risk: {len(high_risk)} | Medium Risk: {len(medium_risk)}

# Top HIGH risk clauses (with suggested fixes):
# {high_text}

# Top MEDIUM risk clauses:
# {medium_text}

# Write a concise executive summary (3-4 paragraphs) covering:
# 1. Overall contract risk assessment — name the 2-3 most dangerous clauses specifically
# 2. Specific negotiation priorities — reference the actual language to change
# 3. Recommendation: Sign as-is | Negotiate before signing | Do not sign

# Do NOT use generic legal boilerplate. Be direct, specific, and actionable."""


# def prompt_draft_clause(
#     clause_type: str,
#     party_a: str,
#     party_b: str,
#     context: str = "",
#     template_context: str = "",
# ) -> str:
#     """Draft a new clause from scratch or based on a template."""
#     template_section = f"\nBase this on our standard template:\n{template_context}\n" if template_context else ""
#     context_section  = f"\nDeal context: {context}\n" if context else ""

#     return f"""Draft a standard {clause_type} clause for a commercial contract.

# Parties:
# - Party A (our company): {party_a}
# - Party B (counterparty): {party_b}
# {context_section}{template_section}
# Requirements:
# - Use clear, professional legal language
# - Be fair but protective of Party A's interests
# - Include all standard sub-provisions for this clause type
# - Mark any blanks that need to be filled with [PLACEHOLDER]

# Draft the clause now:"""


# def prompt_review_clause_fused(
#     clause_text: str,
#     clause_type: str,
#     clause_heading: str = "",
#     playbook_context: str = "",
#     is_recital: bool = False,
#     is_template: bool = False,
# ) -> str:
#     """
#     Single-pass fused prompt: evidence extraction + full review in ONE call.

#     Previously this was two separate LLM calls:
#       Pass 1 — extract verbatim evidence quotes
#       Pass 2 — full review anchored to those quotes

#     Fused approach: instruct the model to first identify evidence inline
#     as it writes each issue. Qwen2.5 14B handles this reliably.
#     Saves ~1.5-2s per clause (the full Pass 1 round-trip).
#     """
#     heading = f"**{clause_heading}**\n" if clause_heading else ""

#     recital_instruction = ""
#     if is_recital:
#         recital_instruction = """
# IMPORTANT: This is a RECITAL / WHEREAS clause — narrative background only.
# Recitals have NO operative legal force.
# - Maximum risk rating is LOW. Do NOT rate this HIGH or MEDIUM.
# - Do NOT raise issues about indemnification, liability, IP, or missing obligations.
# - If no structural issues exist, rate ACCEPTABLE.
# ---
# """

#     template_instruction = ""
#     if is_template:
#         template_instruction = """
# IMPORTANT: This clause contains unfilled template placeholders ([PLACEHOLDER], ___, etc.).
# - Do NOT treat blank placeholders as missing obligations — they are intentional gaps.
# - Focus only on structural/legal issues visible in the existing language.
# - Do NOT fabricate evidence quotes from placeholder text.
# ---
# """

#     playbook_section = ""
#     if playbook_context:
#         playbook_section = f"""
# Our company's playbook position for {clause_type} clauses:
# {playbook_context}
# ---
# """

#     return f"""You are a senior contract attorney reviewing a {clause_type} clause.
# {recital_instruction}{template_instruction}{playbook_section}
# CLAUSE TO REVIEW:
# {heading}{clause_text}

# INSTRUCTIONS:
# 1. Read the ENTIRE clause above before writing anything.
# 2. Identify genuine legal risks only — not style preferences or missing boilerplate.
# 3. For every issue, find the EXACT verbatim phrase from the clause above that proves it.
#    If you cannot find verbatim proof in the clause text, do not raise the issue.
# 4. Standard phrases like "reasonably satisfactory", "reasonable efforts",
#    "commercially reasonable" are NOT risks — do not flag them.
# 5. Do NOT raise issues about addresses, phone numbers, emails, CIN numbers, URLs.

# Respond in this EXACT format. Do not deviate. Do not add extra sections.

# RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

# ISSUES:
# - ISSUE: [Name the specific legal problem — one clear substantive risk]
#   EVIDENCE: "[Copy exact verbatim words from the clause above — must be a real substring]"
#   IMPACT: [One sentence: concrete legal or financial consequence if signed as-is]
# (Repeat - ISSUE / EVIDENCE / IMPACT block for each genuine issue found.)
# (Write "None" under ISSUES if no real issues exist.)

# REDLINE:
# REPLACE: "[exact current contract language to change]"
# WITH: "[improved replacement language]"
# (One REPLACE/WITH pair per issue that needs rewording. Write "No changes needed" if none.)

# NEW_CLAUSE:
# TITLE: [Short clause title]
# REASON: [One sentence: why this clause is missing and why it matters]
# TEXT: [Complete ready-to-insert clause text]
# (Only propose new clauses for genuinely absent protections. Write "None" if nothing is missing.)

# REASONING: [2-3 sentences: overall assessment and top priority for negotiation]"""


# def prompt_triage_clause(clause_text: str, clause_type: str, clause_heading: str = "") -> str:
#     """
#     Fast triage pass - just classify risk level and one-line reason.
#     ~60 tokens output vs ~700 for full review.
#     Only HIGH/MEDIUM results proceed to full deep review.
#     """
#     heading = f"{clause_heading} - " if clause_heading else ""
#     return f"""You are a contract attorney. Quickly assess this {clause_type} clause.

# {heading}{clause_text}

# Respond in this EXACT format only - nothing else:

# RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE
# REASON: [one sentence - the single biggest legal risk, or "No significant issues"]"""

"""
prompts/review_prompts.py — LLM prompts for contract review.
"""

# ------------------------------------------------------------------
# System Prompts
# ------------------------------------------------------------------

SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer reviewing commercial contracts.

RULES:
- Read the ENTIRE clause before forming any opinion
- Only flag SUBSTANTIVE legal risks: obligations, liability, IP, payment, termination, indemnification
- Every issue MUST have verbatim EVIDENCE from the clause text — no evidence = no issue
- If a clause already has a cure period, notice, or matching obligation DO NOT flag it as missing
- Standard phrases are NOT risks: "reasonably satisfactory", "reasonable efforts", "material breach", "commercially reasonable"
- Never flag: addresses, phone numbers, emails, CIN numbers, URLs, signature blocks, defined terms that appear in the preamble

RISK RATINGS:
- HIGH   = significant financial/legal harm if signed as-is (unlimited liability, perpetual obligation, one-sided indemnity, missing payment terms, unilateral IP assignment)
- MEDIUM = needs negotiation (unclear terms, missing protections, imbalanced provisions)
- LOW    = minor issue, not a blocker
- ACCEPTABLE = balanced and fair, no changes needed

REDLINE vs NEW_CLAUSE:
- REDLINE: language EXISTS but needs changing. REPLACE must be verbatim from clause. WITH must be substantively different. Use [PLACEHOLDER] for unknown values.
- NEW_CLAUSE: obligation is ENTIRELY ABSENT. Write complete ready-to-insert text. Use [PLACEHOLDER] for all unknowns."""

SYSTEM_METADATA_EXTRACTOR = """Extract contract metadata. Respond ONLY in valid JSON. No markdown, no explanation."""

SYSTEM_CLAUSE_CLASSIFIER = """Classify contract clauses. Respond in exact format:
CATEGORY: <category>
REASON: <one sentence citing specific words>

Categories: term_termination, notices, confidentiality, limitation_of_liability, indemnification, intellectual_property, payment, warranties, dispute_resolution, definitions, assignment, force_majeure, non_compete, data_privacy, entire_agreement, amendment, insurance, independent_contractor, general"""


# ------------------------------------------------------------------
# Task Prompts
# ------------------------------------------------------------------

def prompt_extract_metadata(contract_text: str) -> str:
    preview = contract_text[:8000]
    return f"""Extract metadata from this contract. Return ONLY valid JSON.
Note: governing_law often appears late — search the full text for "laws of the State of X" or "governed by".

{preview}

JSON format:
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
    heading_hint = f"Heading: {clause_heading}\n" if clause_heading else ""
    return f"""{heading_hint}Text: {clause_text[:600]}

Classify into one category. Heading takes priority over body text.
CATEGORY: <category>
REASON: <cite specific words>"""


def prompt_review_clause_fused(
    clause_text: str,
    clause_type: str,
    clause_heading: str = "",
    playbook_context: str = "",
    is_recital: bool = False,
    is_template: bool = False,
) -> str:
    """Single-pass fused prompt: evidence extraction + full review in one call."""
    heading = f"{clause_heading}\n" if clause_heading else ""

    special = ""
    if is_recital:
        special = "NOTE: This is a RECITAL — narrative context only, no legal force. Max rating: LOW. Do not flag missing obligations.\n"
    elif is_template:
        special = "NOTE: This clause has unfilled placeholders. Do not treat blanks as missing obligations. Do not fabricate evidence quotes.\n"

    playbook = f"Playbook position: {playbook_context}\n" if playbook_context else ""

    return f"""Review this {clause_type} clause.
{special}{playbook}
{heading}{clause_text}

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

ISSUES:
- ISSUE: [specific legal problem]
  EVIDENCE: "[exact verbatim quote from clause proving the problem]"
  IMPACT: [one sentence consequence]
(Repeat per issue. Write "None" if no real issues.)

REDLINE:
REPLACE: "[verbatim text to change]"
WITH: "[specific fix — use [PLACEHOLDER] for unknown values]"
(Write "No changes needed" if none.)

NEW_CLAUSE:
TITLE: [title]
REASON: [one sentence why it is missing]
TEXT: [complete ready-to-insert clause]
(Write "None" if nothing is missing.)

REASONING: [2-3 sentences: overall assessment and top negotiation priority]"""


def prompt_triage_clause(clause_text: str, clause_type: str, clause_heading: str = "") -> str:
    """Fast triage — risk level + one line only. ~60 tokens output."""
    heading = f"{clause_heading}\n" if clause_heading else ""
    return f"""Assess this {clause_type} clause.

{heading}{clause_text}

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE
REASON: [one sentence — biggest legal risk or "No significant issues"]"""


def prompt_contract_summary(clauses_reviewed: list, metadata: dict) -> str:
    high   = [c for c in clauses_reviewed if c.get("risk_level") == "HIGH"]
    medium = [c for c in clauses_reviewed if c.get("risk_level") == "MEDIUM"]

    def _line(c, fix=True):
        line = f"- {c.get('heading','?')}: {c.get('issues','')[:150]}"
        if fix:
            rds = c.get("redlines", [])
            if rds:
                r, w = rds[0].get("replace","")[:50], rds[0].get("with","")[:50]
                if r and w:
                    line += f'\n  Fix: "{r}" → "{w}"'
        return line

    high_text   = "\n".join(_line(c) for c in high[:6])   or "None"
    medium_text = "\n".join(_line(c, False) for c in medium[:4]) or "None"

    return f"""Write an executive summary for this contract review.

{metadata.get("contract_type","Unknown")} | {", ".join(metadata.get("parties",["Unknown"]))} | {metadata.get("governing_law","Unknown law")}
Clauses: {len(clauses_reviewed)} | HIGH: {len(high)} | MEDIUM: {len(medium)}

HIGH risk (with fixes):
{high_text}

MEDIUM risk:
{medium_text}

Write 3 paragraphs:
1. Overall risk — name the 2-3 most dangerous clauses specifically
2. Negotiation priorities — reference actual language to change
3. Recommendation: Sign as-is | Negotiate before signing | Do not sign

Be direct and specific. No generic boilerplate."""