from django.shortcuts import render
from django.views import View
from rest_framework import status
import logging
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.http import HttpRequest,JsonResponse
from core.decorators import outer_exception_handler
from .models import *
from .forms import (
    TagForm
)

logger = logging.getLogger(__name__)


class TagsView(View):
    '''This view manages crud operations of tags'''
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        query = request.GET.get("query")

        tag_qs = Tag.objects.filter(title__iregex=query.strip()).values("id","title")
        if not tag_qs:
            return JsonResponse({
                "success":False,
                "message":"The query search is empty."
            },status=status.HTTP_404_NOT_FOUND)
        
        return JsonResponse({
            "success":True,
            "message":[{"id":res["id"],"name":res["title"]} for res in tag_qs]
        },status=status.HTTP_200_OK)
        


    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        tag_form = TagForm(request.POST)
        if tag_form.is_valid():
            tag_form.save()

        
        tag_qs = Tag.objects.filter(
            title__iexact=request.POST.get("title")
        ).values("id", "title").first()
        

        return JsonResponse({
            "success":True,
            "id":tag_qs["id"],
            "name":tag_qs["title"]
        },status=status.HTTP_201_CREATED)

