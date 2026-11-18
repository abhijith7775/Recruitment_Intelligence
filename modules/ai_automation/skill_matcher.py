"""Skill matching against the project's canonical skill dictionary.

Strictly matches words and phrases in the candidate's resume (prioritizing the
skills section) against entries defined in ``data/skill_dictionary.csv``. Only
matching skills present in the dictionary are extracted; extraneous words and
unmapped technologies are excluded.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional


MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent.parent
DEFAULT_DICTIONARY_PATH = REPO_ROOT / "data" / "skill_dictionary.csv"


@dataclass
class ExtractedSkill:
    """A matched skill with its canonical mapping and contract metadata."""

    skill: str
    canonical_skill: str
    confidence: float = 0.95
    review_required: bool = False

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "canonical_skill": self.canonical_skill,
            "confidence": round(self.confidence, 2),
            "review_required": self.review_required,
        }


class SkillMatcher:
    """Matches resume text strictly against data/skill_dictionary.csv."""

    def __init__(
        self,
        dictionary_path: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        self.repo_root = repo_root or REPO_ROOT
        self.dictionary_path = dictionary_path or DEFAULT_DICTIONARY_PATH
        self.term_to_canonical: dict[str, str] = {}
        self.canonical_skills: set[str] = set()
        self._multi_word_terms: list[str] = []
        self._single_word_terms: list[str] = []
        self._load_dictionary()

    def _load_dictionary(self) -> None:
        """Load and index mappings from data/skill_dictionary.csv."""
        if not self.dictionary_path.exists():
            return

        with self.dictionary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                original = (row.get("original_skill") or "").strip()
                canonical = (row.get("canonical_skill") or "").strip().lower()
                if not canonical:
                    continue

                self.canonical_skills.add(canonical)

                if original:
                    self.term_to_canonical[original.lower()] = canonical

                self.term_to_canonical[canonical] = canonical
                self.term_to_canonical[canonical.replace("_", " ")] = canonical
                self.term_to_canonical[canonical.replace("_", "-")] = canonical

        # Common known variants for canonical entries in this dictionary.
        variant_hints: dict[str, list[str]] = {
            "c++": ["c++", "cpp"],
            "c": ["c"],
            "scikit_learn": ["scikit-learn", "scikit learn", "sklearn"],
            "rest_apis": ["rest apis", "rest api", "restful api", "restful apis"],
            "power_bi": ["power bi", "powerbi", "ms power bi"],
            "deep_learning": ["deep learning"],
            "machine_learning": ["machine learning"],
            "generative_ai": ["generative ai", "gen ai", "genai"],
            "eda": ["eda"],
            "knn": ["knn"],
            "mtcnn": ["mtcnn"],
            "facenet": ["facenet"],
        }
        for canon, variants in variant_hints.items():
            if canon in self.canonical_skills:
                for v in variants:
                    self.term_to_canonical[v.lower()] = canon

        terms = set(self.term_to_canonical.keys())
        terms.discard("c")
        terms.discard("c++")

        multi: list[str] = []
        single: list[str] = []
        for t in terms:
            if " " in t or "-" in t:
                multi.append(t)
            else:
                single.append(t)

        # Sort multi-word phrases by length descending to match longest phrases first
        self._multi_word_terms = sorted(multi, key=len, reverse=True)
        self._single_word_terms = sorted(single, key=len, reverse=True)

    def match_skills(
        self,
        resume_text: str,
        skills_section_text: Optional[str] = None,
    ) -> list[ExtractedSkill]:
        """Extract skills matching data/skill_dictionary.csv across the entire resume."""
        target_text = (resume_text or "").strip()
        matched_canonicals: dict[str, ExtractedSkill] = {}
        lower_target = target_text.lower()
        skills_sec = (skills_section_text or "").strip()

        # 1. Match multi-word dictionary terms
        for term in self._multi_word_terms:
            canon = self.term_to_canonical[term]
            if canon in matched_canonicals:
                continue
            pattern = r"\b" + re.escape(term) + r"\b"
            m = re.search(pattern, lower_target)
            if m:
                matched_canonicals[canon] = ExtractedSkill(
                    skill=term.title(),
                    canonical_skill=canon,
                    confidence=0.95,
                    review_required=False,
                )

        # 2. Match single-word dictionary terms
        for term in self._single_word_terms:
            canon = self.term_to_canonical[term]
            if canon in matched_canonicals:
                continue
            pattern = r"\b" + re.escape(term) + r"\b"
            m = re.search(pattern, lower_target)
            if m:
                matched_canonicals[canon] = ExtractedSkill(
                    skill=term.capitalize() if len(term) > 3 else term.upper(),
                    canonical_skill=canon,
                    confidence=0.95,
                    review_required=False,
                )

        # 3. Handle special symbols: C++
        if "c++" in self.canonical_skills and "c++" not in matched_canonicals:
            if re.search(r"(?:^|[^\w#+])c\+\+(?:[^\w#+]|$)", lower_target):
                matched_canonicals["c++"] = ExtractedSkill(
                    skill="C++",
                    canonical_skill="c++",
                    confidence=0.95,
                    review_required=False,
                )

        # 4. Handle special single-letter: C
        if "c" in self.canonical_skills and "c" not in matched_canonicals:
            # Match standalone 'C' in skills section or with programming language companions
            if skills_sec and re.search(r"(?:^|(?<=[\s,;:|/]))C(?=(?:[\s,;:|/]|$))", skills_sec):
                matched_canonicals["c"] = ExtractedSkill(
                    skill="C",
                    canonical_skill="c",
                    confidence=0.92,
                    review_required=False,
                )
            elif re.search(r"\bC\s*[,/]\s*(?:C\+\+|Python|Java|HTML|SQL)\b", target_text) or re.search(
                r"\b(?:C\+\+|Python|Java|HTML|SQL)\s*[,/]\s*C\b", target_text
            ):
                matched_canonicals["c"] = ExtractedSkill(
                    skill="C",
                    canonical_skill="c",
                    confidence=0.90,
                    review_required=False,
                )

        return list(matched_canonicals.values())


def normalize_canonical_skill(name: str) -> str:
    """Convert an arbitrary skill name to snake_case canonical format."""
    cleaned = re.sub(r"[^a-zA-Z0-9+#]+", "_", (name or "").strip().lower()).strip("_")
    return cleaned


# Backward compatibility alias
SkillDictionaryManager = SkillMatcher


