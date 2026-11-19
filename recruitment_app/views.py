from collections import Counter
from datetime import date
from pathlib import Path
import tempfile

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from modules.ai_automation.pipeline import run_ai_automation
from .models import Activity, Application, Candidate, JobPosting


def _parse_skills(skills_value):
    """Normalize stored semicolon/comma-separated skills into a clean list."""
    if not skills_value:
        return []
    if isinstance(skills_value, list):
        return [str(s).strip() for s in skills_value if str(s).strip()]
    raw = str(skills_value).replace(";", ",")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _serialize_candidate(candidate):
    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "experience_years": candidate.experience_years,
        "skills": _parse_skills(candidate.skills),
        "education": candidate.education,
        "source": candidate.source,
        "application_date": (
            candidate.application_date.isoformat()
            if candidate.application_date
            else None
        ),
    }


def _serialize_job(job):
    return {
        "job_id": job.job_id,
        "role": job.role,
        "required_skills": _parse_skills(job.required_skills),
        "min_experience": job.min_experience,
        "max_experience": job.max_experience,
    }


@require_GET
def health_check(request):
    return JsonResponse({"status": "ok", "service": "recruitment_app_api"})


@require_GET
def candidate_list(request):
    queryset = Candidate.objects.all().order_by("candidate_id")

    skill = request.GET.get("skill", "").strip().lower()
    search = request.GET.get("search", "").strip()
    source = request.GET.get("source", "").strip()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(email__icontains=search)
            | Q(candidate_id__icontains=search)
            | Q(skills__icontains=search)
            | Q(location__icontains=search)
        )

    if source:
        queryset = queryset.filter(source__iexact=source)

    candidates = [_serialize_candidate(c) for c in queryset]

    if skill:
        candidates = [
            c for c in candidates
            if any(s.lower() == skill or skill in s.lower() for s in c["skills"])
        ]

    return JsonResponse({"count": len(candidates), "results": candidates})


@require_GET
def candidate_detail(request, candidate_id):
    candidate = get_object_or_404(Candidate, candidate_id=candidate_id)

    applications = [
        {
            "id": app.id,
            "job_id": app.job.job_id,
            "role": app.job.role,
            "stage": app.stage,
            "stage_date": app.stage_date.isoformat() if app.stage_date else None,
            "recruiter_id": app.recruiter_id,
        }
        for app in Application.objects.filter(candidate=candidate).select_related("job")
    ]

    activities = [
        {
            "id": act.id,
            "event_type": act.event_type,
            "event_date": act.event_date.isoformat() if act.event_date else None,
        }
        for act in Activity.objects.filter(candidate=candidate).order_by("-id")
    ]

    data = _serialize_candidate(candidate)
    data["applications"] = applications
    data["activities"] = activities
    return JsonResponse(data)


@require_GET
def job_list(request):
    jobs = [_serialize_job(j) for j in JobPosting.objects.all().order_by("job_id")]
    return JsonResponse({"count": len(jobs), "results": jobs})


@require_GET
def application_list(request):
    queryset = Application.objects.select_related("candidate", "job").order_by("-id")

    stage = request.GET.get("stage", "").strip()
    job_id = request.GET.get("job_id", "").strip()

    if stage:
        queryset = queryset.filter(stage__iexact=stage)
    if job_id:
        queryset = queryset.filter(job__job_id=job_id)

    results = [
        {
            "id": app.id,
            "candidate_id": app.candidate.candidate_id,
            "candidate_name": app.candidate.name,
            "job_id": app.job.job_id,
            "role": app.job.role,
            "stage": app.stage,
            "stage_date": app.stage_date.isoformat() if app.stage_date else None,
            "recruiter_id": app.recruiter_id,
        }
        for app in queryset
    ]
    return JsonResponse({"count": len(results), "results": results})


@require_GET
def activity_list(request):
    queryset = Activity.objects.select_related("candidate").order_by("-id")

    candidate_id = request.GET.get("candidate_id", "").strip()
    event_type = request.GET.get("event_type", "").strip()

    if candidate_id:
        queryset = queryset.filter(candidate__candidate_id=candidate_id)
    if event_type:
        queryset = queryset.filter(event_type__icontains=event_type)

    results = [
        {
            "id": act.id,
            "candidate_id": act.candidate.candidate_id,
            "candidate_name": act.candidate.name,
            "event_type": act.event_type,
            "event_date": act.event_date.isoformat() if act.event_date else None,
        }
        for act in queryset
    ]
    return JsonResponse({"count": len(results), "results": results})


@require_GET
def analytics_summary(request):
    stage_counts = Counter(
        app.stage or "Unspecified" for app in Application.objects.all()
    )
    source_counts = Counter(
        c.source or "Unspecified" for c in Candidate.objects.all()
    )
    skill_counts = Counter()
    for c in Candidate.objects.all():
        for skill in _parse_skills(c.skills):
            skill_counts[skill.lower()] += 1

    return JsonResponse({
        "totals": {
            "candidates": Candidate.objects.count(),
            "jobs": JobPosting.objects.count(),
            "applications": Application.objects.count(),
            "activities": Activity.objects.count(),
        },
        "applications_by_stage": dict(stage_counts),
        "candidates_by_source": dict(source_counts),
        "top_skills": [
            {"skill": skill, "count": count}
            for skill, count in skill_counts.most_common(10)
        ],
    })


def _compute_job_match(candidate_data, job_data):
    """Score a serialized candidate against a serialized job posting (0.0 to 100.0)."""
    req_skills = [s.lower() for s in job_data["required_skills"]]
    cand_skills_lower = {s.lower() for s in candidate_data["skills"]}

    matched_skills = [
        s for s in job_data["required_skills"] if s.lower() in cand_skills_lower
    ]
    missing_skills = [
        s for s in job_data["required_skills"] if s.lower() not in cand_skills_lower
    ]

    if req_skills:
        skill_ratio = len(matched_skills) / len(req_skills)
        skill_score = skill_ratio * 80.0
    else:
        skill_ratio = 1.0
        skill_score = 80.0

    exp = candidate_data["experience_years"]
    min_exp = job_data["min_experience"]
    max_exp = job_data["max_experience"]

    if exp is None:
        exp_score = 0.0
    else:
        above_min = (min_exp is None) or (exp >= min_exp)
        below_max = (max_exp is None) or (exp <= max_exp)
        if above_min and below_max:
            exp_score = 20.0
        elif above_min:
            exp_score = 12.0
        else:
            exp_score = 5.0

    total_score = round(skill_score + exp_score, 1)
    return {
        "candidate_id": candidate_data["candidate_id"],
        "name": candidate_data["name"],
        "email": candidate_data["email"],
        "experience_years": candidate_data["experience_years"],
        "match_score": total_score,
        "skill_match_percent": round(skill_ratio * 100.0, 1),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }


@require_GET
def job_matching(request, job_id):
    job = get_object_or_404(JobPosting, job_id=job_id)
    job_data = _serialize_job(job)

    min_score_raw = request.GET.get("min_score", "").strip()
    try:
        min_score = float(min_score_raw) if min_score_raw else 0.0
    except ValueError:
        return JsonResponse({"error": "Invalid min_score parameter"}, status=400)

    matches = []
    for candidate in Candidate.objects.all().order_by("candidate_id"):
        cand_data = _serialize_candidate(candidate)
        entry = _compute_job_match(cand_data, job_data)
        if entry["match_score"] >= min_score:
            matches.append(entry)

    matches.sort(key=lambda item: (-item["match_score"], item["candidate_id"]))

    return JsonResponse({
        "job": job_data,
        "count": len(matches),
        "results": matches,
    })


@csrf_exempt
@require_POST
def resume_upload(request):
    """Upload a resume file, extract structured fields via AI automation, and save Candidate."""
    uploaded_file = request.FILES.get("resume") or request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse(
            {"error": "No resume file provided. Send multipart form data with field 'resume'."},
            status=400,
        )

    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in allowed_extensions:
        return JsonResponse(
            {"error": f"Unsupported file type '{ext}'. Allowed: pdf, docx, doc, txt."},
            status=400,
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="django_resume_"))
    temp_file_path = temp_dir / uploaded_file.name

    try:
        with temp_file_path.open("wb") as handle:
            for chunk in uploaded_file.chunks():
                handle.write(chunk)

        report = run_ai_automation(
            [temp_file_path],
            append_to_csv=True,
            application_date=date.today().isoformat(),
        )
    except Exception as exc:
        return JsonResponse(
            {"error": f"Resume extraction failed: {exc}"},
            status=500,
        )
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink(missing_ok=True)
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    if not report.added_candidate_rows:
        return JsonResponse(
            {
                "error": "Pipeline completed without producing a candidate row.",
                "pipeline_status": report.output_payload.get("status"),
                "errors": report.output_payload.get("errors", []),
            },
            status=422,
        )

    row = report.added_candidate_rows[0]
    cid = (row.get("candidate_id") or "").strip()
    if not cid:
        return JsonResponse(
            {"error": "Extracted candidate is missing candidate_id."},
            status=422,
        )

    exp_raw = (row.get("experience_years") or "").strip()
    try:
        exp_years = float(exp_raw) if exp_raw else None
    except ValueError:
        exp_years = None

    app_date_raw = (row.get("application_date") or "").strip()
    try:
        parsed_date = date.fromisoformat(app_date_raw) if app_date_raw else date.today()
    except ValueError:
        parsed_date = date.today()

    candidate, created = Candidate.objects.update_or_create(
        candidate_id=cid,
        defaults={
            "name": (row.get("name") or "").strip() or None,
            "email": (row.get("email") or "").strip() or None,
            "phone": (row.get("phone") or "").strip() or None,
            "location": (row.get("location") or "").strip() or None,
            "experience_years": exp_years,
            "skills": (row.get("skills") or "").strip() or None,
            "education": (row.get("education") or "").strip() or None,
            "source": (row.get("source") or "").strip() or "AI Automation",
            "application_date": parsed_date,
        },
    )

    Activity.objects.create(
        candidate=candidate,
        event_type="resume_uploaded",
        event_date=date.today(),
    )

    return JsonResponse(
        {
            "created": created,
            "candidate": _serialize_candidate(candidate),
            "duplicate_alerts": report.duplicate_alerts,
            "pipeline_run_id": report.output_payload.get("run_id"),
        },
        status=201 if created else 200,
    )