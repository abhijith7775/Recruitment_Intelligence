import json
from pathlib import Path
from django.core.management.base import BaseCommand
from recruitment_app.models import Candidate, JobPosting, Application, Activity

class Command(BaseCommand):
    help = 'Ingests cleaned recruitment JSON output into the Django database'

    def handle(self, *args, **options):
        # 1. Define the path to the Data Preparation JSON output file
        json_path = Path("outputs/data_preparation/data_preparation.json")
        
        if not json_path.exists():
            self.stdout.write(self.style.ERROR(f"Output file not found at {json_path}"))
            return

        # 2. Open and parse the JSON file
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        # Ensure the module run was successful
        if payload.get("status") != "success":
            self.stdout.write(self.style.WARNING("Module run status was not success. Aborting ingestion."))
            return

        data = payload.get("data", {})
        candidates_data = data.get("candidates", [])
        jobs_data = data.get("jobs", [])
        applications_data = data.get("applications", [])
        activity_data = data.get("activity", [])

        # 3. Ingest Candidates
        candidate_count = 0
        for c in candidates_data:
            # Join list of canonical skills back into a semicolon-separated string for storage
            skills_str = "; ".join(c.get("skills", [])) if isinstance(c.get("skills"), list) else c.get("skills", "")
            
            Candidate.objects.update_or_create(
                candidate_id=c["candidate_id"],
                defaults={
                    "name": c.get("name"),
                    "email": c.get("email"),
                    "phone": c.get("phone"),
                    "location": c.get("location"),
                    "experience_years": c.get("experience_years"),
                    "skills": skills_str,
                    "education": c.get("education"),
                    "source": c.get("source"),
                    "application_date": c.get("application_date") if c.get("application_date") else None,
                }
            )
            candidate_count += 1

        # 4. Ingest Job Postings
        job_count = 0
        for j in jobs_data:
            req_skills_str = "; ".join(j.get("required_skills", [])) if isinstance(j.get("required_skills"), list) else j.get("required_skills", "")
            
            JobPosting.objects.update_or_create(
                job_id=j["job_id"],
                defaults={
                    "role": j.get("role"),
                    "required_skills": req_skills_str,
                    "min_experience": j.get("min_experience"),
                    "max_experience": j.get("max_experience"),
                }
            )
            job_count += 1

        # 5. Ingest Applications
        app_count = 0
        for a in applications_data:
            try:
                candidate_obj = Candidate.objects.get(candidate_id=a["candidate_id"])
                job_obj = JobPosting.objects.get(job_id=a["job_id"])
                
                Application.objects.update_or_create(
                    candidate=candidate_obj,
                    job=job_obj,
                    stage=a.get("stage"),
                    defaults={
                        "stage_date": a.get("stage_date"),
                        "recruiter_id": a.get("recruiter_id"),
                    }
                )
                app_count += 1
            except (Candidate.DoesNotExist, JobPosting.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"Skipping application reference error: {e}"))

        # 6. Ingest Activities
        activity_count = 0
        for act in activity_data:
            try:
                candidate_obj = Candidate.objects.get(candidate_id=act["candidate_id"])
                Activity.objects.create(
                    candidate=candidate_obj,
                    event_type=act.get("event_type"),
                    event_date=act.get("event_date")
                )
                activity_count += 1
            except Candidate.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Skipping activity for missing candidate: {act.get('candidate_id')}"))

        self.stdout.write(self.style.SUCCESS(
            f"Successfully ingested: {candidate_count} candidates, {job_count} jobs, {app_count} applications, and {activity_count} activities!"
        ))