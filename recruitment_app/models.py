from django.db import models

class Candidate(models.Model):
    candidate_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    experience_years = models.FloatField(blank=True, null=True)
    skills = models.TextField(blank=True, null=True)  # Stored as semicolon-separated string
    education = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=100, blank=True, null=True)
    application_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.candidate_id})"


class JobPosting(models.Model):
    job_id = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=255)
    required_skills = models.TextField(blank=True, null=True)
    min_experience = models.IntegerField(blank=True, null=True)
    max_experience = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.role} ({self.job_id})"


class Application(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="applications")
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="applications")
    stage = models.CharField(max_length=100, blank=True, null=True)
    stage_date = models.DateField(blank=True, null=True)
    recruiter_id = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.candidate.name} -> {self.job.role} [{self.stage}]"


class Activity(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="activities")
    event_type = models.CharField(max_length=100)
    event_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.event_type} for {self.candidate.name}"