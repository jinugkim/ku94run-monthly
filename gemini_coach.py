"""Generate a Korean Run-teller coaching report with Gemini."""

from datetime import datetime
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
DEFAULT_CACHE_PATH = Path("data/coaching_cache.json")


class GeminiCoachError(RuntimeError):
    """Raised when Gemini cannot generate the coaching report."""


class GeminiCoach:
    """Call the Gemini Generate Content API for a strategy prompt."""

    def __init__(
        self,
        api_key: str,
        model: str,
        cache_path: Path = DEFAULT_CACHE_PATH,
    ) -> None:
        """Configure Gemini using an API key, model name, and optional cache path."""
        self.api_key = api_key
        self.model = model
        self.cache_path = cache_path

    def generate(self, prompt: str) -> str:
        """Generate a Korean coaching report from the supplied prompt."""
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=300,
                    temperature=0.7,
                ),
            )
            report = (response.text or "").strip()
            if not report:
                raise GeminiCoachError("Gemini returned an empty coaching report")
            return report
        except GeminiCoachError:
            raise
        except Exception as exc:
            logger.exception("Gemini coaching report generation failed")
            raise GeminiCoachError("Could not generate a coaching report with Gemini") from exc

    def generate_with_cache(
        self,
        prompt: str,
        fingerprint: str,
        force_refresh: bool = False,
    ) -> str:
        """Return cached report if fingerprint matches and not forcing refresh."""
        today = datetime.now(KST).date().isoformat()
        if not force_refresh and self.cache_path.exists():
            try:
                cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if (
                    cache.get("date") == today
                    and cache.get("fingerprint") == fingerprint
                    and isinstance(cache.get("report"), str)
                    and cache["report"].strip()
                ):
                    logger.info(
                        "Standings unchanged today (fingerprint: %s); reusing cached AI coaching (0 tokens)",
                        fingerprint[:8],
                    )
                    return cache["report"].strip()
            except Exception as exc:
                logger.debug("Coaching cache read note: %s", exc)

        report = self.generate(prompt)

        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(
                    {
                        "date": today,
                        "fingerprint": fingerprint,
                        "generated_at": datetime.now(KST).isoformat(),
                        "report": report,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            logger.info("Saved fresh AI coaching to cache (fingerprint: %s)", fingerprint[:8])
        except Exception as exc:
            logger.warning("Could not persist coaching cache: %s", exc)

        return report
