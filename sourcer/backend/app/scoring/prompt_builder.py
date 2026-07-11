"""Prompt builder for Gemini LLM plan generation and scoring.

This module breaks down the monolithic prompt generation functions from gemini.py
into smaller, composable, testable components following Clean Development principles.
"""
from __future__ import annotations

from typing import Any


class PromptContext:
    """Context data for generating prompts.
    
    Attributes:
        title: Job title
        skills: List of required skills
        geo: Geographic location
        seniority: Seniority level (e.g., 'Mid-Senior', 'Junior')
        description: Job description text
        budget_min: Minimum budget (optional)
        budget_max: Maximum budget (optional)
    """
    
    def __init__(self, job: dict[str, Any]):
        """Initialize context from job dictionary.
        
        Args:
            job: Job dictionary containing vacancy details
        """
        self.title = job.get("title") or "the role"
        skills_raw = job.get("skills") or []
        self.skills = skills_raw if isinstance(skills_raw, list) else [str(skills_raw)]
        self.skills_str = ", ".join(self.skills)
        self.geo = job.get("geo") or "any location"
        self.seniority = job.get("seniority") or "Mid-Senior"
        self.description = (job.get("description") or "")[:600]
        self.budget_min = job.get("budget_min")
        self.budget_max = job.get("budget_max")
        self.primary_skill = self.skills[0] if self.skills else self.title
        
    @property
    def budget_hint(self) -> str:
        """Generate budget hint string for prompts."""
        if not self.budget_min:
            return ""
        budget_str = f"Budget/spend range: ${self.budget_min:,}"
        if self.budget_max:
            budget_str += f" – ${self.budget_max:,}"
        else:
            budget_str += "+"
        return budget_str + " per month."


def build_vacancy_context(ctx: PromptContext) -> str:
    """Build the vacancy context section for prompts.
    
    Args:
        ctx: Prompt context with job details
        
    Returns:
        Formatted vacancy context string
    """
    lines = [
        "VACANCY CONTEXT (use this to customise everything below):",
        f"  Title: {ctx.title}",
        f"  Skills: {ctx.skills_str}",
        f"  Seniority: {ctx.seniority}",
        f"  Target geo: {ctx.geo}",
    ]
    if ctx.budget_hint:
        lines.append(f"  {ctx.budget_hint}")
    lines.append(f"  Description excerpt: {ctx.description}")
    return "\n".join(lines)


def build_linkedin_query_instructions(ctx: PromptContext) -> str:
    """Build LinkedIn query generation instructions.
    
    Args:
        ctx: Prompt context with job details
        
    Returns:
        Formatted instructions for LinkedIn Boolean queries
    """
    return f"""1. linkedin_queries — Array of EXACTLY 3 OR-only LinkedIn Boolean strings, each targeting a DIFFERENT angle.
   CRITICAL RULES (Apify/LinkedIn scraping constraints — violating these causes 0 results):
   - MAX 200 chars each.
   - OR-only. NO AND operators. AND over-narrows LinkedIn pagination → Apify returns 0 items.
   - Specificity comes from TITLE VARIANTS, not AND filters. Use terms tightly linked to the role's PRIMARY tool/platform.
   - Use double quotes around all multi-word phrases.
   - NO location parameters — they are handled separately and invalid values kill results.
   Strategy (adapt to the actual role, these are examples for a generic case):
     query[0] — Primary skill/tool exact title variants in English.
       e.g. for "{ctx.title}": "{ctx.primary_skill} Specialist" OR "{ctx.title}" OR "{ctx.primary_skill} Expert"
     query[1] — Localised/translated title variants for the target market ({ctx.geo}), including any Russian/regional variants if relevant.
     query[2] — Seniority-scoped title variants (Senior/Lead/{ctx.seniority} — exclude overqualified Head/Director/CMO for IC roles).
   GOOD: OR-only strings with tight role-specific title words.
   BAD:  Any AND operator — kills Apify pagination → 0 results.
   BAD:  Overly generic strings unrelated to the actual role."""


def build_telegram_keywords_instructions(ctx: PromptContext) -> str:
    """Build Telegram keywords generation instructions.
    
    Args:
        ctx: Prompt context with job details
        
    Returns:
        Formatted instructions for Telegram keywords
    """
    return f"""2. tg_keywords — 25-40 items in relevant languages: job titles, synonyms, platform names, industry slang directly relevant to this vacancy.
   Include both English and any target-market language variants (Russian, Ukrainian, etc. as appropriate for the geo)."""


def build_hard_filters_instructions(ctx: PromptContext) -> str:
    """Build hard filters generation instructions.
    
    Args:
        ctx: Prompt context with job details
        
    Returns:
        Formatted instructions for hard filters
    """
    return """3. hard_filters — List of 3-6 DISQUALIFYING signals as short strings, derived from the vacancy's requirements.
   Examples: overqualified seniority levels, missing must-have skill, wrong industry vertical, etc.
   Base these on the actual skills and seniority requirements of THIS vacancy."""


def build_rubric_instructions(ctx: PromptContext) -> str:
    """Build scoring rubric generation instructions.
    
    Args:
        ctx: Prompt context with job details
        
    Returns:
        Formatted instructions for scoring rubric
    """
    budget_note = " (only if budget_min was provided) do they have relevant scale experience?" if ctx.budget_min else ""
    
    return f"""4. rubric — Scoring rubric (weights sum to 100). Generate dimension names and weights appropriate for THIS vacancy.
   Do NOT use generic placeholder dimensions — think about what really matters for "{ctx.title}".
   Typical dimensions to consider (adapt as needed):
     - skills_match: does the candidate have the primary required tools/platforms?
     - seniority_fit: are they the right level for a {ctx.seniority} role?
     - industry_fit: do they have relevant vertical/industry experience?
     - budget_scale:{budget_note}
     - availability: are they open to work or likely to respond?
   Each dimension must have: weight (int), description (str explaining what 100 vs 0 means).
   Weights must sum to exactly 100."""


def build_plan_system_prompt(job: dict[str, Any]) -> str:
    """Build the complete plan-generation system prompt.
    
    Dynamically generates prompt based on job details, avoiding hardcoded assumptions.
    
    Args:
        job: Job dictionary with vacancy details
        
    Returns:
        Complete system prompt for plan generation
    """
    ctx = PromptContext(job)
    
    sections = [
        "You are an expert technical recruiter building LinkedIn search queries for Apify scraping.",
        "",
        build_vacancy_context(ctx),
        "",
        "Given the vacancy above, produce:",
        "",
        build_linkedin_query_instructions(ctx),
        "",
        build_telegram_keywords_instructions(ctx),
        "",
        build_hard_filters_instructions(ctx),
        "",
        build_rubric_instructions(ctx),
        "",
        'Return STRICT JSON only — no markdown:',
        '{',
        '  "linkedin_queries": ["...", "...", "..."],',
        '  "tg_keywords": ["...", "..."],',
        '  "hard_filters": ["...", "..."],',
        '  "rubric": {',
        '    "dimension_name": {"weight": 35, "description": "..."},',
        '    "...": {"weight": 25, "description": "..."}',
        '  }',
        '}'
    ]
    
    return "\n".join(sections)


def build_score_system_prompt(job: dict[str, Any], rubric: dict[str, Any]) -> str:
    """Build the complete candidate scoring system prompt.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        
    Returns:
        Complete system prompt for candidate scoring
    """
    ctx = PromptContext(job)
    
    # Build rubric section
    rubric_lines = ["SCORING RUBRIC (weights sum to 100):"]
    for dim_name, dim_spec in rubric.items():
        weight = dim_spec.get("weight", 0)
        desc = dim_spec.get("description", "")
        rubric_lines.append(f"  - {dim_name} ({weight}%): {desc}")
    rubric_section = "\n".join(rubric_lines)
    
    sections = [
        f"You are scoring a candidate for: {ctx.title}",
        "",
        build_vacancy_context(ctx),
        "",
        rubric_section,
        "",
        "Score the candidate on each dimension (0-100). Return STRICT JSON:",
        '{',
        '  "overall_score": 75,',
        '  "reasoning": "Brief explanation of overall fit",',
        '  "dimensions": {',
        '    "dimension_name": 80,',
        '    "...": 70',
        '  },',
        '  "red_flags": ["flag1", "flag2"]',
        '}'
    ]
    
    return "\n".join(sections)


def build_batch_score_system_prompt(job: dict[str, Any], rubric: dict[str, Any], candidate_count: int) -> str:
    """Build the complete batch candidate scoring system prompt.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidate_count: Number of candidates in the batch
        
    Returns:
        Complete system prompt for batch candidate scoring
    """
    ctx = PromptContext(job)
    
    # Build rubric section
    rubric_lines = ["SCORING RUBRIC (weights sum to 100):"]
    for dim_name, dim_spec in rubric.items():
        weight = dim_spec.get("weight", 0)
        desc = dim_spec.get("description", "")
        rubric_lines.append(f"  - {dim_name} ({weight}%): {desc}")
    rubric_section = "\n".join(rubric_lines)
    
    sections = [
        f"You are scoring {candidate_count} candidates for: {ctx.title}",
        "",
        build_vacancy_context(ctx),
        "",
        rubric_section,
        "",
        f"You will receive {candidate_count} candidates. Score EACH candidate independently on each dimension (0-100).",
        "",
        "CRITICAL: Return scores for ALL candidates in the SAME ORDER as provided.",
        "",
        "Return STRICT JSON with this exact structure:",
        '{',
        '  "scores": [',
        '    {',
        '      "id": "0",',
        '      "score": 75,',
        '      "reasoning": "Brief explanation of overall fit",',
        '      "dimensions": {',
        '        "dimension_name": 80,',
        '        "...": 70',
        '      },',
        '      "red_flags": ["flag1", "flag2"]',
        '    },',
        '    {',
        '      "id": "1",',
        '      "score": 82,',
        '      "reasoning": "...",',
        '      "dimensions": {...},',
        '      "red_flags": [...]',
        '    }',
        '    // ... continue for all candidates',
        '  ]',
        '}',
        "",
        "IMPORTANT:",
        "- Each candidate must have an 'id' field matching their index (0, 1, 2, ...)",
        "- Return exactly " + str(candidate_count) + " score objects",
        "- Maintain the same order as the input candidates",
        "- Score each candidate independently - don't compare them to each other"
    ]
    
    return "\n".join(sections)


def build_vacancy_structure_prompt(raw_text: str) -> str:
    """Build system prompt for extracting structured job data from raw text.
    
    Args:
        raw_text: Raw vacancy text (from email, job board, notes, etc.)
    
    Returns:
        System prompt for vacancy structuring
    """
    sections = [
        "You are an expert job description parser and normalizer.",
        "",
        "Your task: Extract structured job data from raw vacancy text.",
        "",
        "The raw text may come from various sources:",
        "- LinkedIn job posts",
        "- Email from recruiters",
        "- Telegram messages",
        "- Plain text notes",
        "- Bullet points",
        "- Multiple languages (translate to English)",
        "",
        "Extract and normalize the following fields:",
        "",
        "1. TITLE (string, required):",
        "   - Normalize to standard format (e.g., 'Sr. Engineer' → 'Senior Engineer')",
        "   - Remove company name if included",
        "   - Examples: 'Senior Python Developer', 'Marketing Manager', 'CTO'",
        "",
        "2. DESCRIPTION (string, optional):",
        "   - Full job description with responsibilities and requirements",
        "   - Clean up formatting (remove excessive newlines, fix spacing)",
        "   - Keep important details (team size, tech stack, benefits)",
        "   - Remove boilerplate (e.g., 'Apply now!', contact info)",
        "",
        "3. SKILLS (array of strings, optional):",
        "   - Extract technical skills, tools, technologies",
        "   - Normalize (e.g., 'React.js' → 'React', 'Python3' → 'Python')",
        "   - Deduplicate (case-insensitive)",
        "   - Examples: ['Python', 'Django', 'PostgreSQL', 'AWS']",
        "",
        "4. SENIORITY (string, optional):",
        "   - Infer from title and description",
        "   - Must be one of: 'Junior', 'Mid', 'Senior', 'Lead', 'Principal', 'Staff'",
        "   - If unclear, return null",
        "",
        "5. GEO (string, optional):",
        "   - Extract location/geography if mentioned",
        "   - Normalize to city/country format (e.g., 'San Francisco, USA', 'Remote', 'Europe')",
        "   - If remote, return 'Remote'",
        "   - If not mentioned, return null",
        "",
        "6. BUDGET_MIN (number, optional):",
        "   - Extract minimum salary/budget if mentioned",
        "   - Convert to annual USD (e.g., '$5k/month' → 60000)",
        "   - If range given, this is the lower bound",
        "   - If not mentioned, return null",
        "",
        "7. BUDGET_MAX (number, optional):",
        "   - Extract maximum salary/budget if mentioned",
        "   - Convert to annual USD",
        "   - If single number given, use same for min and max",
        "   - If not mentioned, return null",
        "",
        "Return STRICT JSON with this exact structure:",
        '{',
        '  "title": "Senior Python Developer",',
        '  "description": "We are looking for...",',
        '  "skills": ["Python", "Django", "PostgreSQL"],',
        '  "seniority": "Senior",',
        '  "geo": "San Francisco, USA",',
        '  "budget_min": 120000,',
        '  "budget_max": 180000',
        '}',
        "",
        "IMPORTANT:",
        "- Always return valid JSON (no markdown, no code blocks)",
        "- title is required, all other fields are optional (use null if not found)",
        "- Be conservative: only extract what's clearly stated",
        "- Normalize and clean all extracted data",
        "- If the text is ambiguous or unclear, make your best inference",
        "",
        "Examples:",
        "",
        "Input: 'Looking for Sr. React dev, 5+ yrs exp, $150k-200k, SF Bay Area'",
        "Output:",
        '{',
        '  "title": "Senior React Developer",',
        '  "description": "5+ years of experience required",',
        '  "skills": ["React"],',
        '  "seniority": "Senior",',
        '  "geo": "San Francisco Bay Area, USA",',
        '  "budget_min": 150000,',
        '  "budget_max": 200000',
        '}',
        "",
        "Input: 'Нужен middle Python разработчик, Django, PostgreSQL, удаленка'",
        "Output:",
        '{',
        '  "title": "Middle Python Developer",',
        '  "description": "Remote position",',
        '  "skills": ["Python", "Django", "PostgreSQL"],',
        '  "seniority": "Mid",',
        '  "geo": "Remote",',
        '  "budget_min": null,',
        '  "budget_max": null',
        '}',
    ]
    
    return "\n".join(sections)
