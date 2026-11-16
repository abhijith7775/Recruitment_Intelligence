"""Resume structured information extraction for the AI Automation module.

Extracts candidate fields in strict alignment with
``contracts/ai_automation/output.schema.json`` while also returning optional
auxiliary metadata (such as ``location`` and normalized CSV fields) for the
module's CSV output. Missing values are never fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
from typing import Any, Callable, Optional

from .skill_matcher import ExtractedSkill, SkillMatcher, SkillDictionaryManager


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,5}\)?[\s.\-]?)?\d{3,5}[\s.\-]?\d{4,5}(?!\d)"
)

HEADER_NOISE_WORDS = {
    "resume",
    "curriculum",
    "vitae",
    "cv",
    "profile",
    "summary",
    "objective",
    "career",
    "contact",
    "personal",
    "details",
    "information",
    "portfolio",
    "bio",
    "biodata",
    "technical",
    "skills",
    "projects",
    "education",
    "experience",
    "experiences",
    "employment",
    "internship",
    "internships",
    "training",
    "trainings",
    "certifications",
    "certificates",
    "qualification",
    "qualifications",
    "academics",
    "academic",
    "soft",
    "languages",
    "language",
    "english",
    "malayalam",
    "hindi",
    "tamil",
    "telugu",
    "kannada",
    "bengali",
    "french",
    "german",
    "spanish",
    "interests",
    "hobbies",
    "strengths",
    "achievements",
    "awards",
    "activities",
    "extracurricular",
    "declaration",
    "reference",
    "references",
    "about",
    "technologies",
    "tools",
}

ROLE_TITLE_WORDS = {
    "developer",
    "engineer",
    "analyst",
    "scientist",
    "intern",
    "internship",
    "manager",
    "designer",
    "consultant",
    "architect",
    "administrator",
    "specialist",
    "associate",
    "trainee",
    "graduate",
    "fresher",
    "student",
    "aspirant",
    "lead",
}

INDIAN_STATES = {
    "kerala",
    "karnataka",
    "tamil nadu",
    "maharashtra",
    "telangana",
    "andhra pradesh",
    "gujarat",
    "rajasthan",
    "uttar pradesh",
    "madhya pradesh",
    "west bengal",
    "punjab",
    "haryana",
    "odisha",
    "bihar",
    "jharkhand",
    "assam",
    "uttarakhand",
    "himachal pradesh",
    "goa",
    "delhi",
}

CITY_STATE_COUNTRY_MAP: dict[str, tuple[str, str, str]] = {
    # Kerala Districts & Towns
    "kottayam": ("Kottayam", "Kerala", "India"),
    "kottyam": ("Kottayam", "Kerala", "India"),
    "pala": ("Kottayam", "Kerala", "India"),
    "cherpunkal": ("Kottayam", "Kerala", "India"),
    "changanassery": ("Kottayam", "Kerala", "India"),
    "kanjirappally": ("Kottayam", "Kerala", "India"),
    "vaikom": ("Kottayam", "Kerala", "India"),
    "anickad": ("Kottayam", "Kerala", "India"),
    "anlckad": ("Kottayam", "Kerala", "India"),
    "elampally": ("Kottayam", "Kerala", "India"),
    "pampady": ("Kottayam", "Kerala", "India"),
    "ettumanoor": ("Kottayam", "Kerala", "India"),

    "kochi": ("Kochi", "Kerala", "India"),
    "cochin": ("Kochi", "Kerala", "India"),
    "ernakulam": ("Ernakulam", "Kerala", "India"),
    "aluva": ("Aluva", "Kerala", "India"),
    "kakkanad": ("Kakkanad", "Kerala", "India"),
    "edappally": ("Edappally", "Kerala", "India"),
    "tripunithura": ("Tripunithura", "Kerala", "India"),
    "thrippunithura": ("Thrippunithura", "Kerala", "India"),
    "angamaly": ("Angamaly", "Kerala", "India"),
    "perumbavoor": ("Perumbavoor", "Kerala", "India"),
    "kothamangalam": ("Kothamangalam", "Kerala", "India"),
    "muvattupuzha": ("Muvattupuzha", "Kerala", "India"),
    "kalamassery": ("Kalamassery", "Kerala", "India"),
    "north paravur": ("North Paravur", "Kerala", "India"),
    "paravur": ("North Paravur", "Kerala", "India"),

    "thiruvananthapuram": ("Thiruvananthapuram", "Kerala", "India"),
    "trivandrum": ("Thiruvananthapuram", "Kerala", "India"),
    "attingal": ("Thiruvananthapuram", "Kerala", "India"),
    "nedumangad": ("Thiruvananthapuram", "Kerala", "India"),
    "neyyattinkara": ("Thiruvananthapuram", "Kerala", "India"),
    "varkala": ("Thiruvananthapuram", "Kerala", "India"),
    "kazhakkoottam": ("Thiruvananthapuram", "Kerala", "India"),

    "kozhikode": ("Kozhikode", "Kerala", "India"),
    "calicut": ("Kozhikode", "Kerala", "India"),
    "vadakara": ("Kozhikode", "Kerala", "India"),
    "koyilandy": ("Kozhikode", "Kerala", "India"),

    "thrissur": ("Thrissur", "Kerala", "India"),
    "trichur": ("Thrissur", "Kerala", "India"),
    "chalakudy": ("Chalakudy", "Kerala", "India"),
    "irinjalakuda": ("Irinjalakuda", "Kerala", "India"),
    "guruvayur": ("Thrissur", "Kerala", "India"),

    "kollam": ("Kollam", "Kerala", "India"),
    "quilon": ("Kollam", "Kerala", "India"),
    "karunagappally": ("Kollam", "Kerala", "India"),
    "punalur": ("Kollam", "Kerala", "India"),
    "kottarakkara": ("Kollam", "Kerala", "India"),

    "palakkad": ("Palakkad", "Kerala", "India"),
    "palghat": ("Palakkad", "Kerala", "India"),
    "ottapalam": ("Palakkad", "Kerala", "India"),
    "shoranur": ("Palakkad", "Kerala", "India"),

    "malappuram": ("Malappuram", "Kerala", "India"),
    "manjeri": ("Malappuram", "Kerala", "India"),
    "tirur": ("Malappuram", "Kerala", "India"),
    "perinthalmanna": ("Malappuram", "Kerala", "India"),
    "ponnani": ("Malappuram", "Kerala", "India"),

    "kannur": ("Kannur", "Kerala", "India"),
    "cannanore": ("Kannur", "Kerala", "India"),
    "thalassery": ("Kannur", "Kerala", "India"),
    "payyanur": ("Kannur", "Kerala", "India"),

    "alappuzha": ("Alappuzha", "Kerala", "India"),
    "alleppey": ("Alappuzha", "Kerala", "India"),
    "cherthala": ("Cherthala", "Kerala", "India"),
    "kayamkulam": ("Alappuzha", "Kerala", "India"),

    "pathanamthitta": ("Pathanamthitta", "Kerala", "India"),
    "thiruvalla": ("Thiruvalla", "Kerala", "India"),
    "adoor": ("Pathanamthitta", "Kerala", "India"),

    "kasaragod": ("Kasaragod", "Kerala", "India"),
    "kanhangad": ("Kasaragod", "Kerala", "India"),

    "wayanad": ("Wayanad", "Kerala", "India"),
    "kalpetta": ("Wayanad", "Kerala", "India"),
    "sulthan bathery": ("Wayanad", "Kerala", "India"),

    "idukki": ("Idukki", "Kerala", "India"),
    "thodupuzha": ("Thodupuzha", "Kerala", "India"),
    "munnar": ("Idukki", "Kerala", "India"),

    # Karnataka
    "bengaluru": ("Bengaluru", "Karnataka", "India"),
    "bangalore": ("Bengaluru", "Karnataka", "India"),
    "mysuru": ("Mysuru", "Karnataka", "India"),
    "mysore": ("Mysuru", "Karnataka", "India"),
    "mangaluru": ("Mangaluru", "Karnataka", "India"),
    "mangalore": ("Mangaluru", "Karnataka", "India"),
    "hubballi": ("Hubballi", "Karnataka", "India"),
    "hubli": ("Hubballi", "Karnataka", "India"),
    "belagavi": ("Belagavi", "Karnataka", "India"),
    "udupi": ("Udupi", "Karnataka", "India"),
    "manipal": ("Manipal", "Karnataka", "India"),

    # Tamil Nadu
    "chennai": ("Chennai", "Tamil Nadu", "India"),
    "madras": ("Chennai", "Tamil Nadu", "India"),
    "coimbatore": ("Coimbatore", "Tamil Nadu", "India"),
    "madurai": ("Madurai", "Tamil Nadu", "India"),
    "tiruchirappalli": ("Tiruchirappalli", "Tamil Nadu", "India"),
    "trichy": ("Tiruchirappalli", "Tamil Nadu", "India"),
    "salem": ("Salem", "Tamil Nadu", "India"),
    "vellore": ("Vellore", "Tamil Nadu", "India"),
    "tirunelveli": ("Tirunelveli", "Tamil Nadu", "India"),
    "erode": ("Erode", "Tamil Nadu", "India"),
    "nagercoil": ("Nagercoil", "Tamil Nadu", "India"),

    # Telangana & Andhra Pradesh
    "hyderabad": ("Hyderabad", "Telangana", "India"),
    "secunderabad": ("Hyderabad", "Telangana", "India"),
    "warangal": ("Warangal", "Telangana", "India"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh", "India"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh", "India"),
    "vijayawada": ("Vijayawada", "Andhra Pradesh", "India"),
    "guntur": ("Guntur", "Andhra Pradesh", "India"),
    "tirupati": ("Tirupati", "Andhra Pradesh", "India"),

    # Maharashtra
    "mumbai": ("Mumbai", "Maharashtra", "India"),
    "bombay": ("Mumbai", "Maharashtra", "India"),
    "navi mumbai": ("Navi Mumbai", "Maharashtra", "India"),
    "thane": ("Thane", "Maharashtra", "India"),
    "pune": ("Pune", "Maharashtra", "India"),
    "nagpur": ("Nagpur", "Maharashtra", "India"),
    "nashik": ("Nashik", "Maharashtra", "India"),
    "aurangabad": ("Aurangabad", "Maharashtra", "India"),

    # Delhi NCR & North
    "delhi": ("New Delhi", "Delhi", "India"),
    "new delhi": ("New Delhi", "Delhi", "India"),
    "noida": ("Noida", "Uttar Pradesh", "India"),
    "greater noida": ("Greater Noida", "Uttar Pradesh", "India"),
    "gurgaon": ("Gurugram", "Haryana", "India"),
    "gurugram": ("Gurugram", "Haryana", "India"),
    "faridabad": ("Faridabad", "Haryana", "India"),
    "ghaziabad": ("Ghaziabad", "Uttar Pradesh", "India"),
    "lucknow": ("Lucknow", "Uttar Pradesh", "India"),
    "kanpur": ("Kanpur", "Uttar Pradesh", "India"),
    "chandigarh": ("Chandigarh", "Punjab", "India"),
    "mohali": ("Mohali", "Punjab", "India"),
    "kolkata": ("Kolkata", "West Bengal", "India"),
    "ahmedabad": ("Ahmedabad", "Gujarat", "India"),
    "surat": ("Surat", "Gujarat", "India"),
    "vadodara": ("Vadodara", "Gujarat", "India"),
    "jaipur": ("Jaipur", "Rajasthan", "India"),
    "indore": ("Indore", "Madhya Pradesh", "India"),
    "bhopal": ("Bhopal", "Madhya Pradesh", "India"),
    "patna": ("Patna", "Bihar", "India"),
    "ranchi": ("Ranchi", "Jharkhand", "India"),
    "bhubaneswar": ("Bhubaneswar", "Odisha", "India"),
    "guwahati": ("Guwahati", "Assam", "India"),
    "dehradun": ("Dehradun", "Uttarakhand", "India"),
    "goa": ("Panaji", "Goa", "India"),
    "panaji": ("Panaji", "Goa", "India"),
}

SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("internship", re.compile(r"^(?:internships?|industrial\s+training|apprenticeships?)\b", re.I)),
    ("experience", re.compile(r"^(?:work\s+experience|professional\s+experience|experience|employment(?:\s+history)?|work\s+history)\b", re.I)),
    ("education", re.compile(r"^(?:e\s*d\s*u\s*c\s*a\s*t\s*i\s*o\s*n(?:al)?(?:\s+qualifications?|\s+background|\s+details|\s+profile)?|academic(?:\s+background|\s+qualifications?|\s+profile|\s+details)?|academics|qualifications?)\b", re.I)),
    ("skills", re.compile(r"^(?:technical\s+skills|skills|key\s+skills|core\s+skills|soft\s+skills|core\s+competencies|technologies|tech\s+stack|tools(?:\s+&\s+technologies)?)\b", re.I)),
    ("projects", re.compile(r"^(?:(?:personal|academic|key|mini|major|capstone)\s+)?projects?\b", re.I)),
    ("certifications", re.compile(r"^(?:certifications?|certificates?|courses?|training|licenses?)\b", re.I)),
    ("summary", re.compile(r"^(?:summary|professional\s+summary|profile|objective|career\s+objective|about(?:\s+me)?)\b", re.I)),
    ("contact", re.compile(r"^(?:contact(?:\s+details|\s+info(?:rmation)?)?|personal\s+(?:details|profile|info(?:rmation)?))\b", re.I)),
    ("other", re.compile(r"^(?:languages?\s+known|spoken\s+languages?|interests?|hobbies|strengths?|achievements?|awards?|declaration|references?|extracurricular|extra[\s\-]?curricular|co[\s\-]?curricular|volunteering|activities)\b", re.I)),
]

DEGREE_RE = re.compile(
    r"(?:"
    r"\b(?:B\s*\.?\s*T\s*ech|M\s*\.?\s*T\s*ech|B\s*\.?\s*C\s*\.?\s*A|M\s*\.?\s*C\s*\.?\s*A|B\s*\.?\s*S\s*c|M\s*\.?\s*S\s*c|B\s*\.?\s*Com|M\s*\.?\s*Com|"
    r"B\s*\.?\s*B\s*\.?\s*A|M\s*\.?\s*B\s*\.?\s*A|B\s*\.?\s*Voc|M\s*\.?\s*Voc|B\s*\.?\s*Des|M\s*\.?\s*Des|B\s*\.?\s*Ed|M\s*\.?\s*Ed|"
    r"L\s*\.?\s*L\s*\.?\s*B|L\s*\.?\s*L\s*\.?\s*M|P\s*\.?\s*G\s*\.?\s*D\s*\.?\s*M|P\s*\.?\s*G\s*\.?\s*D\s*\.?\s*C\s*\.?\s*A|Ph\s*\.?\s*D)\.?(?=$|[\s,;:|/()\-])"
    r"|\b(?:Post[\s\-]?Graduate\s+Diploma|PG\s+Diploma|Post[\s\-]?Graduation|Graduation)\b"
    r"|\b(?:Bachelor(?:'s|s)?(?:\s+Degree)?\s+(?:of|in)\s+[A-Za-z &()/\-]+)"
    r"|\b(?:Master(?:'s|s)?(?:\s+Degree)?\s+(?:of|in)\s+[A-Za-z &()/\-]+)"
    r"|\b(?:Diploma\s+in\s+[A-Za-z &()/\-]+)"
    r")",
    re.IGNORECASE,
)

# Case-sensitive check for short dotted degrees like B.E., M.E., B.A., M.A., B.S., M.S.
SHORT_DOTTED_DEGREE_RE = re.compile(
    r"\b(?:B\.E\.?|M\.E\.?|B\.A\.?|M\.A\.?|B\.S\.?|M\.S\.?|BA|MA|BS|MS)(?=$|[\s,;:|/()\-])"
)

INSTITUTION_KEYWORDS = {
    "school",
    "college",
    "university",
    "institute",
    "polytechnic",
    "academy",
    "campus",
    "institution",
}

CGPA_RE = re.compile(
    r"\b(?:CGPA|GPA|Percentage|Marks)\s*[:\-–]?\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?%?)"
    r"|(?<!\d)(\d{1,2}(?:\.\d+)?%)(?!\d)",
    re.IGNORECASE,
)

SCHOOL_LEVEL_RE = re.compile(
    r"\b(?:10th|12th|sslc|hsc|plus\s*two|\+2|higher\s+secondary|secondary\s+school|"
    r"high\s+school|matriculation|cbse|icse|class\s*x\b|class\s*xii\b)\b",
    re.IGNORECASE,
)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

KNOWN_LOCATIONS = {
    "kochi", "cochin", "ernakulam", "aluva", "kakkanad", "edappally", "tripunithura",
    "thrippunithura", "angamaly", "perumbavoor", "kothamangalam", "muvattupuzha",
    "kollam", "thiruvananthapuram", "trivandrum", "thrissur", "chalakudy", "irinjalakuda",
    "kozhikode", "calicut", "palakkad", "kannur", "thalassery", "kottayam", "pala",
    "changanassery", "alappuzha", "alleppey", "cherthala", "pathanamthitta", "thiruvalla",
    "idukki", "thodupuzha", "malappuram", "manjeri", "tirur", "wayanad", "kalpetta", "kasaragod",
    "bengaluru", "bangalore", "mysuru", "mysore", "mangaluru", "mangalore", "udupi", "manipal",
    "chennai", "coimbatore", "madurai", "trichy", "tiruchirappalli", "salem", "vellore", "nagercoil",
    "hyderabad", "secunderabad", "warangal", "vijayawada", "visakhapatnam", "vizag",
    "pune", "mumbai", "navi mumbai", "thane", "nagpur", "nashik",
    "delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram", "faridabad", "ghaziabad",
    "kolkata", "ahmedabad", "surat", "vadodara", "rajkot", "jaipur", "udaipur",
    "indore", "bhopal", "lucknow", "kanpur", "chandigarh", "mohali", "patna", "ranchi",
    "bhubaneswar", "guwahati", "dehradun", "goa", "panaji",
    "kerala", "karnataka", "tamil nadu", "maharashtra", "telangana", "andhra pradesh",
    "gujarat", "rajasthan", "uttar pradesh", "madhya pradesh", "west bengal", "punjab",
    "haryana", "odisha", "bihar", "jharkhand", "assam", "uttarakhand", "himachal pradesh",
    "india", "dubai", "uae", "abu dhabi", "sharjah", "qatar", "doha", "singapore",
    "london", "uk", "usa", "canada", "remote",
}


@dataclass
class FieldExtraction:
    """Single extracted scalar field with confidence and review indicator."""

    value: Optional[Any]
    confidence: Optional[float]
    source_text: Optional[str]
    review_required: bool

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": round(self.confidence, 2) if self.confidence is not None else None,
            "source_text": self.source_text,
            "review_required": self.review_required,
        }


@dataclass
class ResumeExtractionResult:
    """Complete extraction result for a single resume document."""

    document_id: str
    candidate_id: Optional[str]
    name: FieldExtraction
    email: FieldExtraction
    phone: FieldExtraction
    experience_years: FieldExtraction
    skills: list[ExtractedSkill] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    location: Optional[str] = None
    missing_fields: list[str] = field(default_factory=list)
    processing_status: str = "success"
    newly_added_dictionary_entries: list[dict[str, str]] = field(default_factory=list)

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "candidate_id": self.candidate_id,
            "name": self.name.to_contract_dict(),
            "email": self.email.to_contract_dict(),
            "phone": self.phone.to_contract_dict(),
            "experience_years": self.experience_years.to_contract_dict(),
            "skills": [skill.to_contract_dict() for skill in self.skills],
            "education": self.education,
            "missing_fields": self.missing_fields,
            "processing_status": self.processing_status,
        }

    def canonical_skills(self) -> list[str]:
        seen: list[str] = []
        for item in self.skills:
            token = item.canonical_skill or item.skill.strip().lower().replace(" ", "_")
            if token and token not in seen:
                seen.append(token)
        return seen

    def education_summary(self) -> str:
        values = [entry["value"] for entry in self.education if entry.get("value")]
        return "; ".join(values)


def _split_sections(text: str) -> dict[str, list[str]]:
    """Group resume lines into logical sections based on section headings."""
    sections: dict[str, list[str]] = {
        "header": [],
        "summary": [],
        "experience": [],
        "internship": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certifications": [],
        "contact": [],
        "other": [],
    }
    current = "header"
    for line_idx, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue

        matched_section: Optional[str] = None
        clean_header = re.sub(r"[:\-–|]+$", "", line).strip()
        if len(clean_header.split()) <= 5:
            for sec_name, sec_re in SECTION_PATTERNS:
                if sec_re.match(clean_header):
                    matched_section = sec_name
                    break

        if matched_section:
            current = matched_section
            # Capture inline content after "Skills: ..." or "Education: ..."
            if ":" in line:
                _, rest = line.split(":", 1)
                if rest.strip():
                    sections[current].append(rest.strip())
            continue

        if current == "header" and line_idx > 14:
            current = "other"
        sections[current].append(line)

    return sections


def _extract_name(text: str, sections: dict[str, list[str]]) -> FieldExtraction:
    """Extract candidate name from explicit label, contact proximity, or header lines."""
    explicit_match = re.search(
        r"^(?:candidate\s+name|full\s+name|name)\s*[:\-–]\s*(.+)$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if explicit_match:
        candidate_name = re.split(r"[|•·\n]", explicit_match.group(1).strip())[0].strip()
        candidate_name = re.sub(r"[\ue000-\uf8ff\u25a0-\u27bf\u2022\u00b7📞✉|•—]+", "", candidate_name).strip()
        if 2 <= len(candidate_name) <= 60 and not EMAIL_RE.search(candidate_name):
            return FieldExtraction(
                value=candidate_name.title() if candidate_name.isupper() else candidate_name,
                confidence=0.98,
                source_text=explicit_match.group(0).strip()[:120],
                review_required=False,
            )

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    contact_indices: list[int] = []
    for idx, line in enumerate(lines[:30]):
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            contact_indices.append(idx)

    proximity_candidates: list[tuple[int, str]] = []
    for c_idx in contact_indices:
        for lookback in (1, 2):
            target_idx = c_idx - lookback
            if target_idx >= 0:
                proximity_candidates.append((target_idx, lines[target_idx]))

    header_candidates = [(idx, line) for idx, line in enumerate(lines[:14])]
    all_candidate_lines = proximity_candidates + header_candidates

    scored_names: list[tuple[float, str, str]] = []
    seen_cand_names: set[str] = set()

    for line_idx, raw_line in all_candidate_lines:
        cleaned_line = re.sub(r"[\ue000-\uf8ff\u25a0-\u27bf\u2022\u00b7📞✉]+", " | ", raw_line)
        for segment in re.split(r"[|•·—]|\s+[\-–]\s+", cleaned_line):
            seg = segment.strip(" :-–\t\"'#*")
            if not seg or len(seg) < 3 or len(seg) > 50:
                continue
            if EMAIL_RE.search(seg) or URL_RE.search(seg) or "linkedin" in seg.lower() or "github" in seg.lower():
                continue
            if any(ch.isdigit() for ch in seg):
                continue
            if _matches_degree(seg):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", seg)
            if not (1 <= len(words) <= 4):
                continue
            lowered_words = {w.lower().strip(".") for w in words}
            if lowered_words & HEADER_NOISE_WORDS:
                continue
            if lowered_words & ROLE_TITLE_WORDS:
                continue
            if any(loc in lowered_words for loc in KNOWN_LOCATIONS) and ("," in seg or len(words) == 1):
                continue

            upper_count = sum(1 for w in words if w[0].isupper() or len(w) == 1)
            if upper_count < max(1, len(words) - 1):
                continue

            formatted = seg.title() if (seg.isupper() and len(seg) > 3) else seg
            norm_key = formatted.lower()
            if norm_key in seen_cand_names:
                continue
            seen_cand_names.add(norm_key)

            score = 0.50
            if 2 <= len(words) <= 3:
                score += 0.25
            if line_idx == 0:
                score += 0.20
            elif line_idx == 1:
                score += 0.10
            if any(abs(line_idx - ci) == 1 for ci in contact_indices):
                score += 0.25

            scored_names.append((score, formatted, raw_line))

    if scored_names:
        scored_names.sort(key=lambda x: x[0], reverse=True)
        best_score, best_name, source_line = scored_names[0]
        conf = min(0.96, best_score)
        return FieldExtraction(
            value=best_name,
            confidence=conf,
            source_text=source_line[:120],
            review_required=(conf < 0.85),
        )

    return FieldExtraction(value=None, confidence=None, source_text=None, review_required=True)


def _extract_email(text: str) -> FieldExtraction:
    """Extract normalized lowercase email address."""
    matches = EMAIL_RE.findall(text)
    if not matches:
        return FieldExtraction(value=None, confidence=None, source_text=None, review_required=True)

    unique_emails = list(dict.fromkeys(m.strip().rstrip(".,;:") for m in matches))
    primary = unique_emails[0].lower()
    conf = 0.98 if len(unique_emails) == 1 else 0.78
    return FieldExtraction(
        value=primary,
        confidence=conf,
        source_text=unique_emails[0],
        review_required=(len(unique_emails) > 1),
    )


def _normalize_phone_digits(raw_phone: str) -> str:
    """Normalize a matched phone string to clean digits (never .0 float)."""
    digits = re.sub(r"\D", "", raw_phone)
    return digits


def _extract_phone(text: str) -> FieldExtraction:
    """Extract a valid phone number formatted with country code and a space."""
    candidates: list[tuple[str, str]] = []
    for match in PHONE_RE.finditer(text):
        raw = match.group(0).strip()
        # Reject year ranges like 2021 - 2024 or 2020-2025
        if re.fullmatch(r"(?:19|20)\d{2}[\s.\-]*(?:19|20)\d{2}", raw):
            continue
        digits = _normalize_phone_digits(raw)
        if 10 <= len(digits) <= 13:
            candidates.append((raw, digits))

    if not candidates:
        return FieldExtraction(value=None, confidence=None, source_text=None, review_required=True)

    # Deduplicate by trailing 10 digits.
    dedup: dict[str, tuple[str, str]] = {}
    for raw, digits in candidates:
        key = digits[-10:]
        if key not in dedup:
            dedup[key] = (raw, digits)

    raw_best, digits_best = next(iter(dedup.values()))
    # Format phone number:
    # First 2 digits is country code (e.g. 91 or +91 for Indian format); leave a blankspace between country code and 10-digit phone
    if len(digits_best) == 12 and digits_best.startswith("91"):
        formatted = f"+91 {digits_best[2:]}"
    elif len(digits_best) == 10 and digits_best[0] in "6789":
        formatted = f"+91 {digits_best}"
    elif len(digits_best) == 11 and digits_best.startswith("0") and digits_best[1] in "6789":
        formatted = f"+91 {digits_best[1:]}"
    elif len(digits_best) > 10:
        cc_len = len(digits_best) - 10
        formatted = f"+{digits_best[:cc_len]} {digits_best[cc_len:]}"
    else:
        formatted = digits_best

    conf = 0.94 if len(dedup) == 1 else 0.75
    return FieldExtraction(
        value=formatted,
        confidence=conf,
        source_text=raw_best,
        review_required=(len(dedup) > 1),
    )


URL_RE = re.compile(r"https?://\S+|(?:www\.|linkedin\.com|github\.com)\S*", re.IGNORECASE)
ICON_GLYPH_RE = re.compile(r"[\ue000-\uf8ff\u25a0-\u27bf\u2022\u00b7]+")


def _clean_location_candidate(segment: str) -> str:
    """Strip emails, URLs, phones, icon glyphs, and pin codes from a location candidate."""
    cleaned = ICON_GLYPH_RE.sub(" ", segment)
    cleaned = EMAIL_RE.sub(" ", cleaned)
    cleaned = URL_RE.sub(" ", cleaned)
    cleaned = PHONE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[-–,]?\s*\b\d{5,6}\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-|•:/")
    return cleaned


def _looks_like_location(segment: str) -> bool:
    """Determine whether a cleaned text segment represents a geographic location."""
    if not segment or len(segment) < 3 or len(segment) > 65:
        return False
    if len(segment.split()) > 7:
        return False
    if _matches_degree(segment):
        return False
    lower_clean = segment.lower()
    if any(bad in lower_clean for bad in ("email", "phone", "mobile", "linkedin", "github", "http", "portfolio", "resume", "cgpa", "gpa")):
        return False

    tokens = set(re.findall(r"[a-z]+", lower_clean))
    if any(loc in lower_clean for loc in KNOWN_LOCATIONS if " " in loc) or bool(tokens & KNOWN_LOCATIONS):
        return True

    # Match "City, State" or "Town, District, State" patterns (2–3 comma-separated proper names).
    if re.fullmatch(
        r"[A-Z][a-zA-Z.\s]{1,25}(?:,\s*[A-Z][a-zA-Z.\s]{1,25}){1,2}",
        segment,
    ):
        words = {w.lower().strip(".") for w in re.findall(r"[A-Za-z]+", segment)}
        if not (words & ROLE_TITLE_WORDS):
            return True
    return False


NON_LOCATION_WORDS = {
    "scheme", "service", "services", "system", "systems", "national",
    "international", "volunteer", "volunteering", "training", "internship",
    "project", "projects", "developer", "engineer", "college", "school",
    "university", "institute", "student", "graduate", "experience",
    "skills", "education",
}


def _extract_location(text: str, sections: dict[str, list[str]]) -> Optional[str]:
    """Extract candidate location formatted strictly as 'City, State, Country'."""
    lines = text.splitlines()
    label_re = re.compile(
        r"^[\s•●▪◦\-*]*(?<!email\s)(?<!web\s)(?<!ip\s)"
        r"(?:current\s+location|preferred\s+location|location|current\s+city|city|"
        r"present\s+address|permanent\s+address|residential\s+address|mailing\s+address|address|"
        r"place|hometown|residing\s+(?:in|at)|based\s+in)\s*[:\-–]\s*(.*)$",
        re.IGNORECASE,
    )
    labeled_candidates: list[str] = []
    for idx, line in enumerate(lines):
        match = label_re.match(line)
        if match:
            raw_val = match.group(1).strip()
            if not raw_val and idx + 1 < len(lines):
                raw_val = lines[idx + 1].strip()
            labeled_candidates.append(raw_val)

    search_lines = (
        labeled_candidates
        + sections["header"][:15]
        + lines[:15]
        + sections.get("contact", [])
    )

    candidate_segments: list[str] = []
    for line in search_lines:
        normalized_line = ICON_GLYPH_RE.sub(" | ", line)
        for seg in re.split(r"[|•·/]|\s{2,}|\s+[—–\-]\s+|—", normalized_line):
            cleaned = _clean_location_candidate(seg)
            if cleaned and len(cleaned) <= 80 and not _matches_degree(cleaned):
                words = set(re.findall(r"[a-z]+", cleaned.lower()))
                if not (words & NON_LOCATION_WORDS):
                    candidate_segments.append(cleaned)

    # 1. Check candidate segments for explicit multi-part location strings (e.g. "North Paravur, Kerala, India" or "Kochi, Kerala")
    for clean in candidate_segments:
        parts = [p.strip() for p in clean.split(",") if p.strip()]
        if len(parts) >= 3:
            c_part = parts[-1].lower()
            s_part = parts[-2].lower()
            city_part = parts[-3]
            words = set(re.findall(r"[a-z]+", city_part.lower()))
            if words & NON_LOCATION_WORDS:
                continue
            if c_part in {"india", "uae", "usa", "uk", "canada", "qatar", "singapore"}:
                return f"{city_part.title()}, {parts[-2].title()}, {parts[-1].title()}"
        elif len(parts) == 2:
            s_part = parts[1].lower()
            city_part = parts[0]
            words = set(re.findall(r"[a-z]+", city_part.lower()))
            if words & NON_LOCATION_WORDS:
                continue
            if s_part in INDIAN_STATES:
                if city_part.lower() in CITY_STATE_COUNTRY_MAP:
                    c, s, co = CITY_STATE_COUNTRY_MAP[city_part.lower()]
                    return f"{c}, {s}, {co}"
                return f"{city_part.title()}, {parts[1].title()}, India"
            if s_part == "india" and city_part.lower() in CITY_STATE_COUNTRY_MAP:
                c, s, co = CITY_STATE_COUNTRY_MAP[city_part.lower()]
                return f"{c}, {s}, {co}"

    # 2. Check candidate segments against CITY_STATE_COUNTRY_MAP
    sorted_loc_keys = sorted(CITY_STATE_COUNTRY_MAP.keys(), key=lambda k: -len(k))
    for clean in candidate_segments:
        lower_clean = clean.lower()
        for key in sorted_loc_keys:
            if re.search(r"\b" + re.escape(key) + r"\b", lower_clean):
                city, state, country = CITY_STATE_COUNTRY_MAP[key]
                return f"{city}, {state}, {country}"

    # 3. Check full document text (e.g. college or training institute town/district)
    full_lower = text.lower()
    for key in sorted_loc_keys:
        if re.search(r"\b" + re.escape(key) + r"\b", full_lower):
            city, state, country = CITY_STATE_COUNTRY_MAP[key]
            return f"{city}, {state}, {country}"

    return None


def _parse_month_year(token: str, today: date) -> Optional[int]:
    """Convert a month-year or year token into total months since year 0."""
    cleaned = token.strip().lower()
    if cleaned in {"present", "current", "now", "till date", "ongoing"}:
        return today.year * 12 + today.month

    month_year = re.match(r"^([a-z]{3,9})[\s.,/\-]+((?:19|20)\d{2})$", cleaned)
    if month_year:
        month = MONTH_MAP.get(month_year.group(1))
        year = int(month_year.group(2))
        if month:
            return year * 12 + month

    num_month_year = re.match(r"^(\d{1,2})[/\-]((?:19|20)\d{2})$", cleaned)
    if num_month_year:
        month = int(num_month_year.group(1))
        year = int(num_month_year.group(2))
        if 1 <= month <= 12:
            return year * 12 + month

    year_only = re.match(r"^((?:19|20)\d{2})$", cleaned)
    if year_only:
        return int(year_only.group(1)) * 12 + 1

    return None


def _merge_month_intervals(intervals: list[tuple[int, int]]) -> int:
    """Merge overlapping [start, end] month ranges and return total months."""
    if not intervals:
        return 0
    sorted_intervals = sorted(intervals)
    merged: list[list[int]] = [[sorted_intervals[0][0], sorted_intervals[0][1]]]
    for start, end in sorted_intervals[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(max(1, end - start + 1) for start, end in merged)


INTERNSHIP_INDICATOR_RE = re.compile(
    r"\b(?:intern|internship|internships|trainee|apprentice|apprenticeship|industrial\s+training)\b",
    re.IGNORECASE,
)


def _extract_experience_years(
    text: str,
    sections: dict[str, list[str]],
    today: Optional[date] = None,
) -> FieldExtraction:
    """Extract full-time work experience in years.

    Internships and fresher profiles without full-time employment return 0.
    Education durations are excluded.
    """
    ref_today = today or date.today()

    # 1. Explicit years/months statements outside education and internship contexts.
    explicit_year_re = re.compile(
        r"(?:(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+(?:work|industry|relevant|professional|total))?\s+experience"
        r"|(?:total\s+experience|work\s+experience|experience)\s*[:\-–]?\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?))",
        re.IGNORECASE,
    )
    explicit_month_re = re.compile(
        r"(?:(\d+)\s*\+?\s*(?:months?|mos?)(?:\s+of)?(?:\s+(?:work|industry|relevant|professional|total))?\s+experience"
        r"|(?:total\s+experience|work\s+experience|experience)\s*[:\-–]?\s*(\d+)\s*(?:months?|mos?))",
        re.IGNORECASE,
    )

    saw_internship = bool(sections.get("internship"))

    for line in text.splitlines():
        if INTERNSHIP_INDICATOR_RE.search(line):
            saw_internship = True
            continue
        if _matches_degree(line) or any(
            edu_kw in line.lower() for edu_kw in ("university", "college", "bachelor", "master", "diploma", "school")
        ):
            continue
        yr_match = explicit_year_re.search(line)
        if yr_match:
            val_str = yr_match.group(1) or yr_match.group(2)
            years = round(float(val_str), 1)
            return FieldExtraction(
                value=int(years) if years.is_integer() else years,
                confidence=0.92,
                source_text=yr_match.group(0).strip(),
                review_required=False,
            )
        mo_match = explicit_month_re.search(line)
        if mo_match:
            months = int(mo_match.group(1) or mo_match.group(2))
            years = round(months / 12.0, 1)
            return FieldExtraction(
                value=int(years) if years.is_integer() else years,
                confidence=0.86,
                source_text=mo_match.group(0).strip(),
                review_required=True,
            )

    # 2. Parse date ranges inside the Experience section, skipping internship entries.
    exp_lines = sections["experience"]
    range_re = re.compile(
        r"((?:[A-Za-z]{3,9}[\s.,/\-]+)?(?:19|20)\d{2}|\d{1,2}[/\-](?:19|20)\d{2})"
        r"\s*(?:-|–|—|to)\s*"
        r"(present|current|now|till\s+date|ongoing|(?:[A-Za-z]{3,9}[\s.,/\-]+)?(?:19|20)\d{2}|\d{1,2}[/\-](?:19|20)\d{2})",
        re.IGNORECASE,
    )
    intervals: list[tuple[int, int]] = []
    source_ranges: list[str] = []
    in_internship_entry = False

    for line in exp_lines:
        is_bullet = line.lstrip().startswith(("-", "*", "•", "●"))
        if INTERNSHIP_INDICATOR_RE.search(line):
            saw_internship = True
            in_internship_entry = True
            continue
        if not is_bullet and any(role_kw in line.lower() for role_kw in ROLE_TITLE_WORDS):
            # New non-internship role header resets internship block flag.
            in_internship_entry = False

        if in_internship_entry:
            continue

        for match in range_re.finditer(line):
            start_m = _parse_month_year(match.group(1), ref_today)
            end_m = _parse_month_year(match.group(2), ref_today)
            if start_m is not None and end_m is not None and end_m >= start_m:
                intervals.append((start_m, end_m))
                source_ranges.append(match.group(0).strip())

    if intervals:
        total_months = _merge_month_intervals(intervals)
        years = round(total_months / 12.0, 1)
        return FieldExtraction(
            value=int(years) if years.is_integer() else years,
            confidence=0.82,
            source_text="; ".join(source_ranges[:3]),
            review_required=True,
        )

    # Check non-internship duration phrases inside experience section (e.g., "6 months").
    in_internship_entry = False
    for line in exp_lines:
        is_bullet = line.lstrip().startswith(("-", "*", "•", "●"))
        if INTERNSHIP_INDICATOR_RE.search(line):
            saw_internship = True
            in_internship_entry = True
            continue
        if not is_bullet and any(role_kw in line.lower() for role_kw in ROLE_TITLE_WORDS):
            in_internship_entry = False
        if in_internship_entry:
            continue
        dur = re.search(r"\b(\d+)\s*(?:months?|mos?)\b", line, re.IGNORECASE)
        if dur:
            years = round(int(dur.group(1)) / 12.0, 1)
            return FieldExtraction(
                value=int(years) if years.is_integer() else years,
                confidence=0.80,
                source_text=line[:100],
                review_required=True,
            )

    # 3. Fresher or internship-only experience -> 0 years of full-time experience.
    fresher_match = re.search(
        r"\b(fresher|entry[\s\-]?level|0\s+years?\s+(?:of\s+)?experience|no\s+prior\s+experience|no\s+work\s+experience)\b"
        r"|(?:total\s+|work\s+)?experience\s*[:\-–]\s*(?:none|nil|0|n/?a)\b",
        text,
        re.I,
    )
    if fresher_match:
        return FieldExtraction(
            value=0,
            confidence=0.90,
            source_text=fresher_match.group(0).strip(),
            review_required=False,
        )

    if saw_internship:
        return FieldExtraction(
            value=0,
            confidence=0.88,
            source_text="Internship only (no full-time employment)",
            review_required=False,
        )

    # If any experience is not specified tag it as 0
    return FieldExtraction(
        value=0,
        confidence=0.85,
        source_text="Not specified (default 0)",
        review_required=False,
    )


def _matches_degree(text: str) -> bool:
    """Check whether a text line contains a recognized degree/qualification."""
    return bool(DEGREE_RE.search(text) or SHORT_DOTTED_DEGREE_RE.search(text))


UNIVERSITY_PREFIX_RE = re.compile(
    r"^(?:(?:MG|KTU|VTU|DU|IGNOU|APJ\s+Abdul\s+Kalam(?:\s+Technological)?)\s+university"
    r"|(?:[A-Za-z.\s]+?(?:university|college|institute|academy|polytechnic|campus))\s+(?:of\s+)?"
    r"|(?:affiliated\s+(?:to|with)\s+[A-Za-z.\s]+))[\s:\-–]+",
    re.IGNORECASE,
)

NON_DEGREE_SUMMARY_RE = re.compile(
    r"\b(?:student\s+with|graduate\s+with|final[\s\-]?year|foundation\s+in|hands[\s\-]?on|"
    r"interested\s+in|seeking|experience\s+in|passionate\s+about|developer\s+with|intern\s+at|"
    r"internship|projects\s+involving|developed|coursework|currently\s+developing)\b",
    re.IGNORECASE,
)

ROLE_ONLY_INDICATORS = re.compile(
    r"^(?:bca|mca|b\.?tech|m\.?tech|b\.?sc|m\.?sc|bba|mba|graduate|undergraduate|postgraduate)\s+"
    r"(?:student|graduate|fresher|intern|trainee|aspirant)\b",
    re.IGNORECASE,
)


def _qualification_rank(text: str) -> int:
    """Return academic level rank to prioritize highest educational qualification."""
    lower = text.lower()
    if re.search(r"\b(?:ph\.?d|doctorate)\b", lower):
        return 5
    if re.search(
        r"\b(?:m\.?tech|m\.?e|m\.?sc|mca|mba|m\.?com|ms|ma|master(?:'s)?|post[\s\-]?graduat|pg\s*diploma)\b",
        lower,
    ):
        return 4
    if re.search(
        r"\b(?:b\.?tech|b\.?e|b\.?sc|bca|bba|b\.?com|bs|ba|bachelor(?:'s)?|graduation)\b",
        lower,
    ):
        return 3
    if re.search(r"\b(?:diploma)\b", lower):
        return 2
    return 1


def _clean_education_entry(raw_line: str, next_lines: tuple[str, ...] | list[str] = ()) -> str:
    """Extract course name and attach CGPA or percentage cleanly."""
    line = re.sub(r"\s+", " ", raw_line).strip(" •●▪◦-–|")

    # Detect parenthesized CGPA/percentage or bare CGPA/percentage
    cgpa_str = None
    m = re.search(r"\(\s*(?:CGPA|GPA|Percentage|Marks)\s*[:\-–]?\s*[\d./\s%]+\)", line, re.I)
    if m:
        cgpa_str = m.group(0).strip(" ()")
        line = line[:m.start()] + " " + line[m.end():]
    else:
        m2 = re.search(r"\b(?:CGPA|GPA|Percentage|Marks)\s*[:\-–]?\s*[\d./\s%]+|\b\d{1,2}(?:\.\d+)?%", line, re.I)
        if m2:
            cgpa_str = m2.group(0).strip()
            line = line[:m2.start()] + " " + line[m2.end():]
        else:
            for nl in next_lines[:3]:
                if any(nl.strip().upper().startswith(h) for h in ("SKILLS", "EXPERIENCE", "PROJECTS", "CERTIFICATIONS")):
                    break
                m3 = re.search(r"\b(?:CGPA|GPA|Percentage|Marks)\s*[:\-–]?\s*[\d./\s%]+|\b\d{1,2}(?:\.\d+)?%", nl, re.I)
                if m3:
                    cgpa_str = m3.group(0).strip()
                    break

    cleaned = re.sub(r"\s*\(\s*\)", "", line).strip()
    cleaned = UNIVERSITY_PREFIX_RE.sub("", cleaned).strip()
    cleaned = re.sub(
        r"^(?:post[\s\-]?graduation|postgraduate|undergraduate|graduation|degree)\s*[:\-–]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove trailing year spans after | or - or (
    cleaned = re.sub(r"(?:\s*[-–|]?\s*|\s*)\b(?:19|20)\d{2}\b.*$", "", cleaned).strip()
    cleaned = re.split(r"\s+[-–]\s+(?=[A-Z])", cleaned)[0].strip()

    # Split on commas and keep course parts while removing trailing college/university
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    course_parts: list[str] = []
    for p in parts:
        words = set(re.findall(r"[a-z]+", p.lower()))
        if words & INSTITUTION_KEYWORDS:
            break
        if re.search(r"^(?:19|20)\d{2}\b", p.strip()):
            break
        course_parts.append(p)
    course = ", ".join(course_parts) if course_parts else cleaned
    course = re.sub(r"(?:\s*[-–|]?\s*|\s*)\b(?:19|20)\d{2}\b.*$", "", course).strip(" ,-–|")

    # Append CGPA or percentage if available and not already inside course
    if cgpa_str and cgpa_str.lower() not in course.lower():
        course = f"{course} ({cgpa_str})"

    return course


def _extract_education(text: str, sections: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Extract education entries prioritizing the highest educational qualification."""
    edu_lines = sections.get("education", [])
    merged_edu_lines: list[tuple[str, list[str]]] = []
    idx = 0
    while idx < len(edu_lines):
        line = edu_lines[idx].strip()
        if NON_DEGREE_SUMMARY_RE.search(line) or ROLE_ONLY_INDICATORS.match(line):
            idx += 1
            continue

        if _matches_degree(line):
            cleaned_peek = re.sub(
                r"^(?:post[\s\-]?graduation|postgraduate|undergraduate|graduation|degree)\s*[:\-–]?\s*",
                "",
                line,
                flags=re.I,
            ).strip()
            if not cleaned_peek and idx + 1 < len(edu_lines) and _matches_degree(edu_lines[idx + 1]):
                idx += 1
                continue

            next_lines = [edu_lines[j].strip() for j in range(idx + 1, min(len(edu_lines), idx + 4))]
            # Combine short standalone degree line (e.g. "B.Tech" / "M.Sc.") with next specialization line.
            if (
                len(line.split()) <= 3
                and idx + 1 < len(edu_lines)
                and not _matches_degree(edu_lines[idx + 1])
                and not SCHOOL_LEVEL_RE.search(edu_lines[idx + 1])
            ):
                next_spec = edu_lines[idx + 1].strip()
                if (
                    next_spec
                    and 1 <= len(next_spec.split()) <= 8
                    and not re.search(r"^(?:19|20)\d{2}\b|cgpa|gpa|%|university|college|institute|school", next_spec, re.I)
                ):
                    merged_edu_lines.append((f"{line} in {next_spec}", next_lines[1:]))
                    idx += 2
                    continue
            merged_edu_lines.append((line, next_lines))
        idx += 1

    # Only fall back to full document scan if NO degrees were found in the education section
    if merged_edu_lines:
        all_pairs = merged_edu_lines
    else:
        fallback_lines: list[tuple[str, list[str]]] = []
        lines_all = text.splitlines()
        for i, line in enumerate(lines_all):
            if NON_DEGREE_SUMMARY_RE.search(line) or ROLE_ONLY_INDICATORS.match(line):
                continue
            if _matches_degree(line):
                nxt = [lines_all[j].strip() for j in range(i + 1, min(len(lines_all), i + 4))]
                fallback_lines.append((line.strip(), nxt))
        all_pairs = fallback_lines

    edu_section_set = {pair[0] for pair in merged_edu_lines}

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_line, next_lines in all_pairs:
        clean_entry = _clean_education_entry(raw_line, next_lines)
        if not clean_entry or len(clean_entry) < 2:
            continue
        if clean_entry.lower() in {"graduation", "post graduation", "post-graduation", "undergraduate", "postgraduate"}:
            continue
        if not _matches_degree(clean_entry):
            continue
        if SCHOOL_LEVEL_RE.search(clean_entry):
            continue

        norm_key = re.sub(r"[^a-z0-9]+", " ", clean_entry.lower()).strip()
        base_norm_key = re.sub(r"\bcgpa.*|\bgpa.*|\b\d+%.*", "", norm_key).strip()
        if base_norm_key in seen:
            continue
        seen.add(base_norm_key)

        is_edu_section = raw_line in edu_section_set
        conf = 0.92 if is_edu_section else 0.82
        entries.append(
            {
                "value": clean_entry[:150],
                "confidence": round(conf, 2),
                "review_required": conf < 0.85,
                "_rank": _qualification_rank(clean_entry),
            }
        )

    # Sort so the highest educational qualification comes first
    entries.sort(key=lambda x: x["_rank"], reverse=True)
    for e in entries:
        e.pop("_rank", None)

    return entries


def extract_resume_fields(
    *,
    document_id: str,
    resume_text: str,
    skill_matcher: Optional[SkillMatcher] = None,
    skill_manager: Optional[SkillMatcher] = None,
    candidate_id: Optional[str] = None,
    extraction_config: Optional[dict[str, bool]] = None,
    persist_skill_updates: bool = False,
    llm_enhancer: Optional[Callable[[str, dict[str, Any]], dict[str, Any]]] = None,
) -> ResumeExtractionResult:
    """Extract structured candidate fields from resume text per AI Automation contract."""
    cfg = {
        "extract_name": True,
        "extract_contact": True,
        "extract_experience": True,
        "extract_skills": True,
        "extract_education": True,
    }
    if extraction_config:
        cfg.update(extraction_config)

    sections = _split_sections(resume_text)

    name = (
        _extract_name(resume_text, sections)
        if cfg["extract_name"]
        else FieldExtraction(value=None, confidence=None, source_text=None, review_required=False)
    )
    email = (
        _extract_email(resume_text)
        if cfg["extract_contact"]
        else FieldExtraction(value=None, confidence=None, source_text=None, review_required=False)
    )
    phone = (
        _extract_phone(resume_text)
        if cfg["extract_contact"]
        else FieldExtraction(value=None, confidence=None, source_text=None, review_required=False)
    )
    experience_years = (
        _extract_experience_years(resume_text, sections)
        if cfg["extract_experience"]
        else FieldExtraction(value=None, confidence=None, source_text=None, review_required=False)
    )

    if cfg["extract_skills"]:
        matcher = skill_matcher or skill_manager or SkillMatcher()
        skills_section_text = "\n".join(sections.get("skills", []))
        skills = matcher.match_skills(resume_text, skills_section_text=skills_section_text)
        new_dict_entries = []
    else:
        skills, new_dict_entries = [], []

    education = _extract_education(resume_text, sections) if cfg["extract_education"] else []
    location = _extract_location(resume_text, sections)

    missing_fields: list[str] = []
    if cfg["extract_name"] and not name.value:
        missing_fields.append("name")
    if cfg["extract_contact"]:
        if not email.value:
            missing_fields.append("email")
        if not phone.value:
            missing_fields.append("phone")
    if cfg["extract_experience"] and experience_years.value is None:
        missing_fields.append("experience_years")
    if cfg["extract_skills"] and not skills:
        missing_fields.append("skills")
    if cfg["extract_education"] and not education:
        missing_fields.append("education")

    status = "partial_success" if missing_fields else "success"

    result = ResumeExtractionResult(
        document_id=document_id,
        candidate_id=candidate_id,
        name=name,
        email=email,
        phone=phone,
        experience_years=experience_years,
        skills=skills,
        education=education,
        location=location,
        missing_fields=missing_fields,
        processing_status=status,
        newly_added_dictionary_entries=new_dict_entries,
    )

    if llm_enhancer is not None:
        # Optional hook for future LLM-assisted refinement while preserving contract.
        _ = llm_enhancer(resume_text, result.to_contract_dict())

    return result
