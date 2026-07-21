from django.shortcuts import render
from django.http import HttpRequest,JsonResponse
import logging
from .models import *
from django.db.models import Q
from rest_framework import status
from django.views.decorators.http import require_GET,require_POST
from core.decorators import outer_exception_handler
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .selectors.dashboard import DashboardSelector
from .selectors.explore import ExploreSelector
from .selectors.careers_match import CareerMatchSelector
from .selectors.career_detail import CareerDetailSelector
from .selectors.course_detail import CourseDetailSelector
from core.models import Tag
from .selectors.institution_detail import InstitutionDetailSelector

logger = logging.getLogger(__name__)


'''
CBV(S)
'''

@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareersDashboardView(View):
    template_name = "careers/dashboard.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        context = DashboardSelector.get_dashboard_context(request.user.profile)
        return render(request,self.template_name,context)
    


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareersExploreView(View):
    template_name = "careers/explore.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            search_query = request.GET.get("q")
            context = ExploreSelector.get_explore_context(request.user.profile, search_query)
            return render(request, self.template_name, context)
        except Exception as e:
            logger.error(f"Unexpected execution exception in CareersExploreView: {e}", exc_info=True)
            return render(request, self.template_name, {
                "careers": [],
                "courses": [],
                "institutions": [],
                "sectors": [],
                "qualifications": [],
                "countries": [],
            })


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareerMatchView(View):
    template_name = "careers/career_match.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            slug = request.GET.get("slug")
            context = CareerMatchSelector.get_career_match_context(request.user.profile, slug)
            return render(request, self.template_name, context)
        except Exception as e:
            logger.error(f"Unexpected execution exception in CareerMatchView: {e}", exc_info=True)
            return render(request, self.template_name, {
                "career": {},
                "match_pct": 0,
                "insights": [],
                "recommended_courses": [],
                "subject_requirements": [],
                "cutoff_clusters": [],
                "institutions": [],
                "similar_careers": [],
                "user_grades": {},
                "user_points": 0.0,
                "careers": [],
                "courses": [],
                "subject_reqs": [],
                "cutoffs": [],
                "ca_tests_json": [],
            })
    
@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  PsychoMetricAssessmentView(View):
    template_name = "careers/psychometric_assessment.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareerDetailView(View):
    template_name = "careers/career_detail.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            slug = kwargs.get("slug")
            context = CareerDetailSelector.get_career_detail_context(request.user.profile, slug)
            return render(request, self.template_name, context)
        except Exception as e:
            logger.error(f"Unexpected execution exception in CareerDetailView: {e}", exc_info=True)
            return render(request, self.template_name, {
                "career": None,
                "courses": Course.objects.none(),
                "institutions": Institution.objects.none(),
                "subject_requirements": SubjectRequirement.objects.none(),
                "cutoff_clusters": CutoffCluster.objects.none(),
                "match_pct": None,
                "similar_careers": Career.objects.none(),
                "career_tags": Tag.objects.none(),
                "page_title": "Error Loading Career Detail",
            })
    
    

@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CourseDetailView(View):
    template_name = "careers/course_detail.html"
    
    def get(self, request: HttpRequest, *args, **kwargs):
        try:
            slug = kwargs.get("slug")
            context = CourseDetailSelector.get_course_detail_context(request.user.profile, slug)
            return render(request, self.template_name, context)
        except Exception as e:
            logger.error(f"Unexpected execution exception in CourseDetailView: {e}", exc_info=True)
            return render(request, self.template_name, {
                "course": None,
                "career": None,
                "institutions": Institution.objects.none(),
                "subject_requirements": SubjectRequirement.objects.none(),
                "cutoff_clusters": CutoffCluster.objects.none(),
                "related_courses": Course.objects.none(),
                "latest_cutoff": None,
                "match_pct": None,
            })
    
    
@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  InstitutionDetailView(View):
    template_name = "careers/institution_detail.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            slug = kwargs.get("slug")
            context = InstitutionDetailSelector.get_institution_detail_context(slug)
            return render(request, self.template_name, context)
        except Exception as e:
            logger.error(f"Unexpected execution exception in InstitutionDetailView: {e}", exc_info=True)
            return render(request, self.template_name, {
                "institution": None,
                "courses": Course.objects.none(),
                "careers": Career.objects.none(),
                "qualifications": [],
                "sectors": [],
                "cutoff_clusters": CutoffCluster.objects.none(),
                "subject_requirements": SubjectRequirement.objects.none(),
                "course_count": 0,
                "career_count": 0,
            })
    

'''
FBV(s)
'''

@require_GET
@outer_exception_handler(logger)
def search_careers_re(request:HttpRequest):
    '''Uses regex to search the db for careers'''
    try:
        query = request.GET.get("query")
        careers_q = Career.objects.filter(title__iregex=query).values("id","title")
        
        if not careers_q.exists():
            return JsonResponse({
            "success": False,
            "error": f"Career \'{query}\' does not exist."
        }, status=status.HTTP_404_NOT_FOUND)

        return JsonResponse({
            "success":True,
            "message":list(careers_q)
        })


    except Exception as e:
        logger.error(str(e))
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@require_POST
@outer_exception_handler(logger)
def save_career_assessment(request:HttpRequest,*args,**kwargs):
    pass


@require_POST
@outer_exception_handler(logger)
def autosave_career_assessment(request:HttpRequest,*args,**kwargs):
    pass