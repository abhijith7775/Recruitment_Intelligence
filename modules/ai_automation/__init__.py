"""AI Automation module for resume extraction and skill dictionary enrichment."""

from .document_reader import DocumentReadResult, infer_mime_type, read_resume_document
from .extractor import FieldExtraction, ResumeExtractionResult, extract_resume_fields
from .pipeline import (
    AIAutomationPipeline,
    PipelineRunReport,
    run_ai_automation,
    validate_contract_payload,
)
from .skill_matcher import (
    ExtractedSkill,
    SkillDictionaryManager,
    SkillMatcher,
    normalize_canonical_skill,
)

__all__ = [
    "AIAutomationPipeline",
    "DocumentReadResult",
    "ExtractedSkill",
    "FieldExtraction",
    "PipelineRunReport",
    "ResumeExtractionResult",
    "SkillDictionaryManager",
    "SkillMatcher",
    "extract_resume_fields",
    "infer_mime_type",
    "normalize_canonical_skill",
    "read_resume_document",
    "run_ai_automation",
    "validate_contract_payload",
]
