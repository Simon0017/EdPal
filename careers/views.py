from django.shortcuts import render
from django.http import HttpRequest,JsonResponse
import logging
from .models import *
from django.db.models import Q
from rest_framework import status
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

'''
FBV(s)
'''

@require_GET
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