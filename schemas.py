"""
Gemini function declarations for all Verdict tools.
Used as the 'tools' argument in the agent loop.
"""

# ── Shared ─────────────────────────────────────────────────────────────────────

FETCH_PAGE = {
    "name": "fetch_page",
    "description": (
        "Fetch the full HTML content of a URL. Falls back to Playwright headless "
        "Chromium if the page appears to be JavaScript-rendered. Returns raw HTML string."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch."}
        },
        "required": ["url"],
    },
}

ENRICH_PROJECT = {
    "name": "enrich_project",
    "description": (
        "Enrich a shallow project record by fetching its submission page and extracting "
        "links (GitHub, demo, video), tech stack tags, and track chips. "
        "Returns the record with links, tracks, and tech_stack populated."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "object",
                "description": "Shallow project record with at least title, submission_url.",
                "properties": {
                    "title": {"type": "string"},
                    "team": {"type": "string"},
                    "description": {"type": "string"},
                    "submission_url": {"type": "string"},
                },
            }
        },
        "required": ["project"],
    },
}

WRITE_PROJECT_DESCRIPTION = {
    "name": "write_project_description",
    "description": (
        "Use Gemini Flash to write a 2-3 sentence plain-language AI description of the project "
        "and one judicial verdict line. Adds ai_description and verdict_line to the record."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "object",
                "description": "Enriched project record.",
            }
        },
        "required": ["project"],
    },
}

PARSE_RULES = {
    "name": "parse_rules",
    "description": (
        "Parse a free-form judging rubric text into a structured list of criteria with "
        "weights summing to 100. If text is empty, returns the default rubric. "
        "Returns list of {criterion, weight, description}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "rules_text": {
                "type": "string",
                "description": "Free-form rubric text, or empty string for defaults.",
            }
        },
        "required": ["rules_text"],
    },
}

# ── Scout-only ─────────────────────────────────────────────────────────────────

FETCH_AND_EXTRACT_PROJECTS = {
    "name": "fetch_and_extract_projects",
    "description": (
        "Fetch a hackathon submissions page and extract all project records in one step. "
        "Returns [{title, team, description, submission_url}]. "
        "Use this instead of fetch_page + extract_projects_from_html separately."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The hackathon submissions page URL."},
        },
        "required": ["url"],
    },
}

CLUSTER_PROJECTS = {
    "name": "cluster_projects",
    "description": (
        "Use Gemini Pro to theme-group a list of enriched projects. "
        "Returns {clusters: {cluster_id: {label, project_ids: []}}}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projects": {
                "type": "array",
                "description": "List of enriched project records.",
                "items": {"type": "object"},
            }
        },
        "required": ["projects"],
    },
}

IDENTIFY_GAPS = {
    "name": "identify_gaps",
    "description": (
        "Use Gemini Pro to identify 3-5 gaps — things no one is building. "
        "Returns [{headline, reasoning}]."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projects": {"type": "array", "items": {"type": "object"}},
            "clusters": {"type": "object"},
        },
        "required": ["projects", "clusters"],
    },
}

IDENTIFY_THREATS = {
    "name": "identify_threats",
    "description": (
        "Use Gemini Pro to identify the top 5 most polished or ambitious projects. "
        "Returns [{project_id, reasoning}]."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projects": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["projects"],
    },
}

PICK_FAVORITE = {
    "name": "pick_favorite",
    "description": (
        "Use Gemini Pro to pick the dark-horse winner of the field. "
        "Returns {project_id, reasoning}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projects": {"type": "array", "items": {"type": "object"}},
            "clusters": {"type": "object"},
            "gaps": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["projects", "clusters", "gaps"],
    },
}

WRITE_SCOUT_REPORT = {
    "name": "write_scout_report",
    "description": (
        "Assemble and persist the final Scout report JSON. "
        "Saves to data/verdicts/<id>.json and returns the verdict ID string."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_url": {"type": "string"},
            "projects": {"type": "array", "items": {"type": "object"}},
            "clusters": {"type": "object"},
            "gaps": {"type": "array", "items": {"type": "object"}},
            "threats": {"type": "array", "items": {"type": "object"}},
            "favorite": {"type": "object"},
        },
        "required": ["source_url", "projects", "clusters", "gaps", "threats", "favorite"],
    },
}

# ── Judgment-only ──────────────────────────────────────────────────────────────

INGEST_FROM_HACKATHON_URL = {
    "name": "ingest_from_hackathon_url",
    "description": (
        "Fetch a hackathon URL and extract all submission records. "
        "Returns [{title, team, description, submission_url}]."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
        },
        "required": ["url"],
    },
}

INGEST_FROM_FILE = {
    "name": "ingest_from_file",
    "description": (
        "Read an uploaded file (CSV, JSON, MD, TXT, PDF) and parse it into "
        "submission records. Returns [{title, team, description, submission_url}]."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "Upload ID (u_...) from /api/upload."},
        },
        "required": ["file_id"],
    },
}

INGEST_FROM_TEXT = {
    "name": "ingest_from_text",
    "description": (
        "Parse freeform text into submission records using Gemini Flash. "
        "Returns [{title, team, description, submission_url}]."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    },
}

SCORE_SUBMISSION = {
    "name": "score_submission",
    "description": (
        "Use Gemini Pro to score a submission against the rubric. "
        "Returns {overall_score, rubric_scores: [{criterion, weight, score, max, note}], verdict_line}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "submission": {"type": "object", "description": "Enriched submission record."},
            "rubric": {
                "type": "array",
                "description": "List of {criterion, weight, description}.",
                "items": {"type": "object"},
            },
        },
        "required": ["submission", "rubric"],
    },
}

RANK_AND_FINALIZE = {
    "name": "rank_and_finalize",
    "description": (
        "Sort scored submissions by overall_score descending, assign ranks, "
        "and return the leaderboard list."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scored": {
                "type": "array",
                "description": "List of submissions with overall_score.",
                "items": {"type": "object"},
            },
            "rubric": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["scored", "rubric"],
    },
}

WRITE_COURT_SUMMARY = {
    "name": "write_court_summary",
    "description": (
        "Use Gemini Pro to write one solemn judicial paragraph summarising the ruling. "
        "Returns a plain-text paragraph."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "leaderboard": {"type": "array", "items": {"type": "object"}},
            "rubric": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["leaderboard", "rubric"],
    },
}

WRITE_JUDGMENT_REPORT = {
    "name": "write_judgment_report",
    "description": (
        "Assemble and persist the final Judgment report JSON. "
        "Saves to data/verdicts/<id>.json and returns the verdict ID string."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_type": {"type": "string"},
            "source_details": {"type": "string"},
            "rules_raw": {"type": "string"},
            "rubric": {"type": "array", "items": {"type": "object"}},
            "leaderboard": {"type": "array", "items": {"type": "object"}},
            "summary": {"type": "string"},
        },
        "required": ["source_type", "source_details", "rules_raw", "rubric", "leaderboard", "summary"],
    },
}

# ── Tool sets per agent ────────────────────────────────────────────────────────

SCOUT_TOOLS = [
    FETCH_AND_EXTRACT_PROJECTS,
    ENRICH_PROJECT,
    WRITE_PROJECT_DESCRIPTION,
    CLUSTER_PROJECTS,
    IDENTIFY_GAPS,
    IDENTIFY_THREATS,
    PICK_FAVORITE,
    WRITE_SCOUT_REPORT,
]

JUDGMENT_TOOLS = [
    PARSE_RULES,
    INGEST_FROM_HACKATHON_URL,
    INGEST_FROM_FILE,
    INGEST_FROM_TEXT,
    FETCH_PAGE,
    ENRICH_PROJECT,
    WRITE_PROJECT_DESCRIPTION,
    SCORE_SUBMISSION,
    RANK_AND_FINALIZE,
    WRITE_COURT_SUMMARY,
    WRITE_JUDGMENT_REPORT,
]
