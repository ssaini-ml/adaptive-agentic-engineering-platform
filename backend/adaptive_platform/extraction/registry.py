from __future__ import annotations

from adaptive_platform.extraction.protocol import (
    ExtractorAdapter,
    ExtractorDescriptor,
    ExtractorStatus,
)


class ExtractorRegistry:
    def __init__(self, adapters: tuple[ExtractorAdapter, ...] = ()) -> None:
        self._adapters: dict[str, ExtractorAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ExtractorAdapter) -> None:
        for language in adapter.descriptor.languages:
            if language in self._adapters:
                raise ValueError(f"An extractor is already registered for {language}")
            self._adapters[language] = adapter

    def adapter_for(self, language: str) -> ExtractorAdapter | None:
        return self._adapters.get(language)

    def descriptor_for(self, language: str) -> ExtractorDescriptor:
        adapter = self.adapter_for(language)
        if adapter is None:
            return ExtractorDescriptor(
                name="none",
                version="none",
                languages=(language,),
                status=ExtractorStatus.UNSUPPORTED,
                diagnostics=("No approved extractor is registered for this language.",),
            )
        return adapter.descriptor

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
