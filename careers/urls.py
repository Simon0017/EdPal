from django.urls import path
from .views import *


CBVS = [
    path('',                  CareersDashboardView.as_view(), name='careers_dashboard'),
    path('explore/',          CareersExploreView.as_view(),   name='careers_explore'),
    path('match/',            CareerMatchView.as_view(),       name='careers_match'),
    path('<slug:slug>/',      CareerDetailView.as_view(),      name='career_detail'),
    path('courses/<slug:slug>/',       CourseDetailView.as_view(),      name='course_detail'),
    path('institutions/<slug:slug>/',  InstitutionDetailView.as_view(), name='institution_detail'),
]

FBVS = [
    path("search-careers",search_careers_re,name="search_careers")
]


urlpatterns = [
    *CBVS,*FBVS
]