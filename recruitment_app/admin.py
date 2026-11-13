from django.contrib import admin
from .models import Candidate, JobPosting, Application, Activity

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('candidate_id', 'name', 'email', 'source', 'application_date')
    search_fields = ('candidate_id', 'name', 'email')
    list_filter = ('source',)

@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('job_id', 'role', 'min_experience', 'max_experience')
    search_fields = ('job_id', 'role')

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'job', 'stage', 'stage_date', 'recruiter_id')
    list_filter = ('stage',)
    search_fields = ('candidate__name', 'job__role', 'recruiter_id')

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'event_type', 'event_date')
    list_filter = ('event_type',)
    search_fields = ('candidate__name', 'event_type')