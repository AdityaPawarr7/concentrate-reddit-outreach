"""Concentrate.ai product context and subreddit targets."""

SUBREDDITS = [
    "ClaudeCode",
    "LLMDevs",
    "Claude",
    "AIAgents",
    "Cursor",
    "LocalLLM",
    "ClaudeAI",
]

CONCENTRATE_PROFILE = """
Concentrate.ai (https://concentrate.ai/) is a unified LLM gateway:
- One API for every major LLM provider (OpenAI, Anthropic, Google, etc.)
- Up to ~20% savings on token spend; least-cost routing and caching
- Free orchestration, analytics, unified billing, logs, spend management
- Guardrails: sensitive data redaction, RBAC, auditing, compliance
- Multi-provider redundancy when a provider is down
- Central API key management across teams and tools
- Use any model in Claude Code, Cursor, and OpenCode (not locked to one vendor)
- No vendor lock-in; token credits without minimum commitments
"""

DEFAULT_GRADING_PROMPT = """You grade Reddit posts for B2B outreach fit for Concentrate.ai.

{concentrate_profile}

Post from r/{subreddit}:
Title: {title}
Body: {body}

Rule-based pre-score: {rule_score}/100.

Return JSON only:
{{"alignment_score": <0-100>, "rationale": "<1-2 sentences>", "outreach_worthy": <true|false>}}
Score high if the poster has a problem Concentrate solves (multi-provider API, cost, governance, Cursor/Claude Code model access).
Score low for memes, show-offs, job posts, or unrelated chatter."""

DEFAULT_COMMENT_PROMPT = """Write a helpful, non-spammy Reddit comment replying to this post.
Promote Concentrate.ai naturally only if relevant. Be concise (2-4 sentences), authentic, and add value first.
Include https://concentrate.ai/ only if it fits naturally.

Post from r/{subreddit} by u/{author}:
Title: {title}
Body: {body}

Suggested angle: {suggested_angle}

Return JSON only:
{{"comment": "<your reddit comment text>"}}"""

SIGNAL_GROUPS = {
    "high_intent": {
        "weight": 35,
        "keywords": [
            "api gateway", "llm gateway", "unified api", "one api", "openrouter",
            "litellm", "portkey", "helicone", "langfuse", "multi provider",
            "multi-provider", "provider switch", "failover", "redundancy",
            "orchestrat", "routing", "proxy api", "api proxy", "spend management",
            "token cost", "llm cost", "billing", "rate limit", "api key management",
            "rbac", "guardrail", "pii", "redaction", "compliance", "audit log",
            "observability", "logging", "vendor lock",
        ],
    },
    "tool_fit": {
        "weight": 30,
        "keywords": [
            "claude code", "cursor", "opencode", "claude api", "anthropic",
            "openai api", "local llm", "ollama", "vllm", "ai agent", "agents",
            "mcp", "coding assistant", "copilot", "bedrock", "vertex", "groq",
            "together ai", "fireworks",
        ],
    },
    "pain_points": {
        "weight": 25,
        "keywords": [
            "expensive", "too much", "cost", "pricing", "outage", "down",
            "unreliable", "alternative", "recommend", "which provider", "best model",
            "compare", "switch", "migrate", "multiple keys", "scattered", "enterprise",
            "team", "production", "self-host", "privacy", "data leak", "sensitive",
        ],
    },
    "engagement": {
        "weight": 10,
        "keywords": [
            "how do", "how to", "help", "advice", "recommendation", "anyone",
            "question", "stuck", "issue", "problem", "?",
        ],
    },
}

OUTREACH_THRESHOLD = 45
