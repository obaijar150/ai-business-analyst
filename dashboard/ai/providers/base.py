from abc import ABC, abstractmethod


class AnalysisProvider(ABC):
    @abstractmethod
    def create_plan(self, question, schema):
        """Return a structured analysis plan using only the supplied schema."""


class AnalysisProviderError(Exception):
    """Raised for provider configuration, network, or response errors."""
