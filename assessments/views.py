from django.shortcuts import render
from django.views import View
from rest_framework import status
import logging
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.http import HttpRequest,JsonResponse
from django.db.models import Prefetch,Count,Avg,Max,Min

from core.decorators import outer_exception_handler
from .forms import (
    QuestionForm,
    QuestionnaireForm,
    QuestionnaireTagForm,
    AnswerChoiceForm
)
from .models import *

from .services.questionnare_post import CreateQuestionniare

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
        questionnare_obj =  CreateQuestionniare(request)

        questionnaire_form = questionnare_obj.create__questionnare_form()
        
        tags_forms = questionnare_obj.create_tags()

        questions_forms = questionnare_obj.create_question_forms()

        choices_forms = questionnare_obj.create_choices_forms()

        has_errors = questionnare_obj.has_validation_errors()

        if has_errors:
            logger.error(questionnare_obj.errors)
            return JsonResponse(
                {"success": False, "errors": questionnare_obj.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_saved = questionnare_obj.save_post(
            questionnaire_form,
            tags_forms,
            questions_forms,
            choices_forms
        )


        if is_saved:
            return JsonResponse(
                {"success": True, "message": "Questionnaire created"},
                status=status.HTTP_201_CREATED
            )
        else:
            return JsonResponse(
                {"success": False, "message": "Failed to save questionnaire"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class ListQuestionnares(View):
    '''Provides crud operations for staff to adminiter the questionare and questions'''
    template_name = "assessments/questionnare_manage.html"
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)


    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        pass


class ManageQuestionnares(View):
    '''Provides crud operations for staff to adminiter the questionare and questions'''
    template_name = "assessments/questionnare.html"
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        pk = kwargs.get("pk")
        
        questionnaire = (
            Questionnaire.objects
            .filter(id=pk)
            .prefetch_related(
                Prefetch(
                    "questions",
                    queryset=Question.objects.prefetch_related("answer_choices")
                )
            )
            .annotate(
                attempts_count=Count("attempts", distinct=True),
                participants_count=Count("attempts__profile", distinct=True),
                average_score=Avg("attempts__score"),
                highest_score=Max("attempts__score"),
                lowest_score=Min("attempts__score"),
            )
            .first()
        )

        data = {
            "id": questionnaire.id,
            "title": questionnaire.title,
            "status": questionnaire.status,
            "created_at": questionnaire.created_at,
            "modified_at": questionnaire.modified_at,
            "attempts_count": questionnaire.attempts_count,
            "participants_count": questionnaire.participants_count,
            "average_score": questionnaire.average_score,
            "highest_score": questionnaire.highest_score,
            "lowest_score": questionnaire.lowest_score,
            "description": questionnaire.description,
            "max_score": questionnaire.max_score,
            "time_limit_minutes": questionnaire.time_limit_minutes,
            "is_randomised": questionnaire.is_randomised,
        }
        
        data["questions"] = [
            {
                "id": q.id,
                "text": q.question_text,
                "explanation": q.explanation,
                "is_required": q.is_required,
                "max_points": q.max_points,
                "order": q.order,
                "question_type": q.question_type,
                "weight": q.weight,
                "choices": list(q.answer_choices.values(
                    "id", "choice_key", "choice_text", "is_correct", "partial_score"
                ))
            }
            for q in questionnaire.questions.all()
        ]

        return JsonResponse(
            {"success": True, "message": "Questionnaire details fetched","data": data},
            status=status.HTTP_200_OK
        )


    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        pass

@require_GET
@outer_exception_handler(logger)
def get_questionnnaire_list(request:HttpRequest):
    '''API endpoint to fetch list of questionnares'''

    questionnares = (
        Questionnaire.objects
        .annotate(
            attempts_count=Count("attempts", distinct=True),
            participants_count=Count("attempts__profile", distinct=True),
        )
        .values(
            "id", "title", "status", "created_at", "modified_at",
            "attempts_count", "participants_count", "description","max_score"
        )
    )

    return JsonResponse(
        {"success": True, "results": list(questionnares)},
        status=status.HTTP_200_OK
    )