from collections import Counter
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from .models import Candidate, JobPosting, Application, Activity


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