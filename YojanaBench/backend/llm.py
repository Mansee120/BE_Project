"""
llm.py
------
Optional local LLM client for Ollama (zero API cost).

The whole pipeline is fully functional WITHOUT an LLM: every decision is made by
deterministic code. When a local Ollama server is running, the Orchestrator may
use it to *polish* the natural-language explanation. If Ollama is absent the
client silently degrades to a template-based explanation, so the project always
works offline and reproducibly.
"""
import json

import requests

from . import config


class LLMClient:
    def __init__(self, host: str = None, model: str = None):
        self.host = host or config.OLLAMA_HOST
        self.model = model or config.OLLAMA_MODEL
        self._available = None  # memoised availability flag

    def available(self) -> bool:
        """Ping Ollama's tag endpoint once and cache the result."""
        if self._available is not None:
            return self._available
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            self._available = resp.status_code == 200
        except requests.RequestException:
            self._available = False
        return self._available

    def generate(self, prompt: str, timeout: float = None) -> str:
        """Return generated text, or None if the LLM is unavailable/fails."""
        if not self.available():
            return None
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=timeout or config.OLLAMA_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            return None
        return None

    def status(self) -> dict:
        return {
            "available": self.available(),
            "host": self.host,
            "model": self.model,
        }


# Module-level singleton so agent code can share one client instance.
llm_client = LLMClient()
