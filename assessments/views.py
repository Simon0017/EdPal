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
from .forms import (
    QuestionForm,
    QuestionnaireForm,
    QuestionnaireTagForm,
    AnswerChoiceForm
)
from .models import *

logger = logging.getLogger(__name__)


'''
CBV(s)
'''
class AdminQuestinnare(View):
    '''Provides crud operations for staff to adminiter the questionare and questions'''
    template_name = "assessments/questionnare.html"
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        context =  {
            "steps": ["Meta", "Tags", "Questions", "Choices", "Review"]
        }
        return render(request,self.template_name,context)

    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        questionnare_form = Questionnaire(request.POST)
        tag_form = QuestionnaireTag(request.POST)
        choice_form = AnswerChoiceForm(request.POST)
        questions_form = QuestionForm(request.POST)


        
        return JsonResponse(
            {
                "success":True,
                "message":"Questionnare created"
            },status = status.HTTP_201_CREATED
        )

