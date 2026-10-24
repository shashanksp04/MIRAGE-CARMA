"""Worker-local, retrieval-only visual attribute extraction.

This module deliberately has no dependency on the ADK/RAG agent.  It makes one
multimodal request to the endpoint owned by the calling RAG worker and fails
closed to text-only retrieval when extraction is unavailable or unsafe.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

PROMPT_VERSION = "visual-attributes-v1"
EXTRACTION_PROMPT = (
    "Describe only the directly visible characteristics relevant to identifying "
    "the organism, plant, or plant condition in the image(s). Include distinctive "
    "color, shape, size only if visually inferable, surface texture, markings, "
    "anatomical features, leaf/plant symptoms, and clearly visible damage. "
    "Do not identify the species, name a diagnosis, recommend treatment, or guess "
    "details that are not visible. If the subject is unclear, say which traits are "
    "uncertain. Be concise (at most three short sentences) and use searchable terms."
)

_UNSAFE_OUTPUT = re.compile(
    r"\b(?:species|diagnos(?:e|is)|treat(?:ment|ing)?|spray|pesticide|herbicide|"
    r"fungicide|control|recommend|likely (?:a|an)|identified as|this is a|"
    r"it is a|looks like a)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractionResult:
    attributes: str = ""
    status: str = "skipped"
    error: Optional[str] = None
    latency_ms: int = 0

    def to_dict(self):
        return {
            "attributes": self.attributes,
            "status": self.status,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


def image_cache_key(image_paths: Iterable[str], model: str, timeout: float) -> str:
    """Return a versioned content key; paths alone never identify an image."""
    digest = hashlib.sha256()
    digest.update(PROMPT_VERSION.encode())
    digest.update(json.dumps({"model": model, "timeout": timeout}, sort_keys=True).encode())
    for path in list(image_paths)[:3]:
        p = Path(path)
        try:
            digest.update(p.read_bytes())
        except (OSError, ValueError):
            digest.update(f"missing:{p}".encode())
    return digest.hexdigest()


def _image_part(path: str) -> dict:
    mime, _ = mimetypes.guess_type(path)
    mime = mime if mime and mime.startswith("image/") else "image/jpeg"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _validate(text: object) -> str:
    if not isinstance(text, str):
        raise ValueError("model response was not text")
    value = re.sub(r"\s+", " ", text).strip()
    value = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", value, flags=re.IGNORECASE).strip()
    if value.startswith("{"):
        try:
            parsed = json.loads(value)
            value = str(parsed.get("attributes", ""))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("model response was not valid attribute text")
    if not value:
        raise ValueError("model returned empty visual attributes")
    if len(value) > 1200:
        raise ValueError("visual attributes exceeded the output bound")
    if _UNSAFE_OUTPUT.search(value):
        raise ValueError("model response contained an identity or treatment claim")
    return value


class VisualAttributeExtractor:
    def __init__(self, api_base: str, model: str, timeout_seconds: float = 45):
        from openai import OpenAI

        self.api_base = api_base
        self.model = model
        self.timeout_seconds = float(timeout_seconds)
        self.client = OpenAI(api_key="token-abc123", base_url=api_base,
                             max_retries=0, timeout=self.timeout_seconds)

    def extract(self, image_paths: Iterable[str], original_query: str = "") -> ExtractionResult:
        started = time.monotonic()
        paths = list(image_paths or [])[:3]
        try:
            if not paths:
                return ExtractionResult(error="no readable images", latency_ms=0)
            valid = []
            for path in paths:
                if not os.path.isfile(path):
                    raise FileNotFoundError(path)
                _image_part(path)  # validate/read before making a request
                valid.append(path)
            content = [{"type": "text", "text": EXTRACTION_PROMPT}]
            content.extend(_image_part(path) for path in valid)
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_completion_tokens=180,
                temperature=0.0,
                top_p=1.0,
            )
            text = _validate(completion.choices[0].message.content)
            return ExtractionResult(text, "success", latency_ms=round((time.monotonic() - started) * 1000))
        except Exception as exc:
            return ExtractionResult(status="failed", error=f"{type(exc).__name__}: {exc}",
                                    latency_ms=round((time.monotonic() - started) * 1000))
