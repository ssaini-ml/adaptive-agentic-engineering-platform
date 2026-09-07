from adaptive_platform.extraction.models import (
    ExtractedRelationship,
    ExtractedSymbol,
    RelationshipType,
    ResolutionStatus,
    SymbolType,
)
from adaptive_platform.extraction.protocol import (
    ExtractionDocument,
    ExtractionRequest,
    ExtractionResult,
    ExtractorAdapter,
    ExtractorDescriptor,
    ExtractorStatus,
)
from adaptive_platform.extraction.python_ast import PythonAstExtractor
from adaptive_platform.extraction.registry import ExtractorRegistry
from adaptive_platform.extraction.source_loader import (
    SourceSnapshotError,
    load_extraction_documents,
)


def default_extractor_registry() -> ExtractorRegistry:
    return ExtractorRegistry((PythonAstExtractor(),))


__all__ = [
    "ExtractedRelationship",
    "ExtractedSymbol",
    "ExtractionDocument",
    "ExtractionRequest",
    "ExtractionResult",
    "ExtractorAdapter",
    "ExtractorDescriptor",
    "ExtractorRegistry",
    "ExtractorStatus",
    "PythonAstExtractor",
    "RelationshipType",
    "ResolutionStatus",
    "SourceSnapshotError",
    "SymbolType",
    "default_extractor_registry",
    "load_extraction_documents",
]
