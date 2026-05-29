"""Shared Concentrate API helpers."""

from __future__ import annotations

import os
from typing import Any

import requests


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def extract_responses_text(resp_json: dict[str, Any]) -> str:
    parts: list[str] = []
    for out in resp_json.get("output", []) or []:
        for c in out.get("content", []) or []:
            if c.get("type") == "output_text" and isinstance(c.get("text"), str):
                parts.append(c["text"])
    return "\n".join(p for p in parts if p.strip()).strip()


def extract_chat_text(resp_json: dict[str, Any]) -> str:
    choices = resp_json.get("choices") or []
    if not choices:
        return ""
    content = (choices[0].get("message") or {}).get("content")
    return content.strip() if isinstance(content, str) else ""


def call_concentrate(
    prompt: str,
    *,
    json_schema: dict[str, Any] | None = None,
    json_object: bool = False,
) -> str:
    api_key = env("CONCENTRATE_API_KEY")
    if not api_key:
        return ""
    base_url = env("CONCENTRATE_BASE_URL", "https://api.concentrate.ai/v1").rstrip("/")
    model = env("CONCENTRATE_MODEL", "gpt-4o-mini")
    if model.lower() == "auto":
        model = "gpt-4o-mini"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "temperature": 0.2,
        "max_output_tokens": 400,
    }
    if json_schema:
        body["text"] = {"format": {"type": "json_schema", "name": "output", "schema": json_schema}}
    elif json_object:
        body["text"] = {"format": {"type": "json_object"}}

    resp = requests.post(f"{base_url}/responses", headers=headers, json=body, timeout=60)
    if resp.ok:
        return extract_responses_text(resp.json())

    chat_body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 400,
    }
    if json_object or json_schema:
        chat_body["response_format"] = {"type": "json_object"}
    resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=chat_body, timeout=60)
    if resp.ok:
        return extract_chat_text(resp.json())
    return ""
