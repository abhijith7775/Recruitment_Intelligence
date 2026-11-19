from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health_check, name="api-health"),
    path("candidates/", views.candidate_list, name="api-candidate-list"),
    path("candidates/<str:candidate_id>/", views.candidate_detail, name="api-candidate-detail"),
    path("jobs/", views.job_list, name="api-job-list"),
    path("applications/", views.application_list, name="api-application-list"),
    path("activities/", views.activity_list, name="api-activity-list"),
    path("analytics/summary/", views.analytics_summary, name="api-analytics-summary"),
    path("matching/<str:job_id>/", views.job_matching, name="api-job-matching"),
    path("resumes/upload/", views.resume_upload, name="api-resume-upload"),
]