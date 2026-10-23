"""Generate a Korean Run-teller coaching report with Gemini."""

import logging

from google import genai

logger = logging.getLogger(__name__)


class GeminiCoachError(RuntimeError):
    """Raised when Gemini cannot generate the coaching report."""


class GeminiCoach:
    """Call the Gemini Generate Content API for a strategy prompt."""

    def __init__(self, api_key: str, model: str) -> None:
        """Configure Gemini using an API key and model name."""
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        """Generate a Korean coaching report from the supplied prompt."""
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(model=self.model, contents=prompt)
            report = (response.text or "").strip()
            if not report:
                raise GeminiCoachError("Gemini returned an empty coaching report")
            return report
        except GeminiCoachError:
            raise
        except Exception as exc:
            logger.exception("Gemini coaching report generation failed")
            raise GeminiCoachError("Could not generate a coaching report with Gemini") from exc
