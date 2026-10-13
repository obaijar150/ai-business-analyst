from .base import AnalysisProviderError
from .gemini_provider import GeminiAnalysisProvider
from .local_provider import LocalAnalysisProvider
from .openai_provider import OpenAIAnalysisProvider


def get_analysis_provider(name=None):
    from django.conf import settings

    provider_name = (name or settings.AI_PROVIDER).strip().lower()
    if provider_name in {"local", "heuristic", "built-in", "builtin"}:
        return LocalAnalysisProvider()
    if provider_name == "openai":
        return OpenAIAnalysisProvider()
    if provider_name == "gemini":
        return GeminiAnalysisProvider()
    raise AnalysisProviderError(f"Unsupported AI provider: {provider_name}.")
