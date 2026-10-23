import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI

import prompts

load_dotenv()

MODEL = "gpt-6.1-sol"
API_VERSION = "2024-12-01-preview"
CACHE_DIR = Path(__file__).parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_client = None
_mem_cache: dict[str, str] = {}


def get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_key=os.getenv("HACK_API_KEY"),
            azure_endpoint=os.getenv("HACK_ENDPOINT"),
            api_version=API_VERSION,
        )
    return _client


def _key(kind: str, *parts) -> str:
    raw = json.dumps([kind, *parts], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _cached(key: str, producer) -> str:
    """Memory cache + disk cache, so a restarted demo never waits twice."""
    if key in _mem_cache:
        return _mem_cache[key]
    path = CACHE_DIR / f"{key}.txt"
    if path.exists():
        _mem_cache[key] = path.read_text(encoding="utf-8")
        return _mem_cache[key]
    result = producer()
    _mem_cache[key] = result
    path.write_text(result, encoding="utf-8")
    return result


def ask(system: str, user: str) -> str:
    resp = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


def run_committee(facts: dict) -> str:
    return _cached(
        _key("committee", facts),
        lambda: ask(prompts.COMMITTEE_PROMPT, json.dumps(facts)),
    )


def run_report(facts: dict) -> str:
    return _cached(
        _key("report", facts),
        lambda: ask(prompts.REPORT_PROMPT, json.dumps(facts)),
    )


def challenge(facts: dict, history: list[dict], question: str) -> str:
    """history = [{"role": "user"|"assistant", "content": str}, ...] (before `question`)."""

    def produce():
        messages = [
            {
                "role": "system",
                "content": prompts.CHALLENGE_PROMPT.format(facts=json.dumps(facts)),
            },
            *history,
            {"role": "user", "content": question},
        ]
        resp = get_client().chat.completions.create(model=MODEL, messages=messages)
        return resp.choices[0].message.content

    return _cached(_key("challenge", facts, history, question), produce)
