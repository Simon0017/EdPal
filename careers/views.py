from django.shortcuts import render
from django.http import HttpRequest,JsonResponse
import logging
from .models import *
from django.db.models import Q
from rest_framework import status
from django.views.decorators.http import require_GET
from core.decorators import outer_exception_handler
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

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
    

'''
CBV(S)
'''

@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareersDashboardView(View):
    template_name = "careers/dashboard.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)
    


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareersExploreView(View):
    template_name = "careers/explore.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareerMatchView(View):
    template_name = "careers/career_match.html"
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)


@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CareerDetailView(View):
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return JsonResponse(
            {
                "success":True
            },status=status.HTTP_200_OK
        )
    
@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  CourseDetailView(View):
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return JsonResponse(
            {
                "success":True
            },status=status.HTTP_200_OK
        )
    
@method_decorator(login_required,name="dispatch")
@method_decorator(outer_exception_handler(logger),name="dispatch")
class  InstitutionDetailView(View):
    
    def get(self,request:HttpRequest,*args,**kwargs):
        return JsonResponse(
            {
                "success":True
            },status=status.HTTP_200_OK
        )