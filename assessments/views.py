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
        post = request.POST
        errors = {"questionnaire": {}, "tags": [], "questions": [], "choices": []}
        has_errors = False

        questionnaire_form = QuestionnaireForm(post)

        if not questionnaire_form.is_valid():
            errors["questionnaire"] = questionnaire_form.errors
            has_errors = True

        tags_data = zip(
            post.getlist("tag"),
            post.getlist("coupling_strength"),
            post.getlist("is_primary"),
        )

        tag_objects = []
        for i, (tag_id, coupling, primary) in enumerate(tags_data):
            form = QuestionnaireTagForm({
                "tag":               tag_id,
                "coupling_strength": coupling,
                "is_primary":        primary,
            })

            if not form.is_valid():
                errors["tags"].append({"row": i + 1, "errors": form.errors})
                has_errors = True
            else:
                tag_objects.append(form)

        question_texts   = post.getlist("question_text")
        question_types   = post.getlist("question_type")
        weights          = post.getlist("weight")
        max_points_list  = post.getlist("max_points")
        orders           = post.getlist("order")
        rand_groups      = post.getlist("randomisation_group")
        is_required_list = post.getlist("is_required")
        explanations     = post.getlist("explanation")
        numeric_configs  = post.getlist("numeric_config_raw")

        question_forms = []
        for i, text in enumerate(question_texts):
            form = QuestionForm({
                "question_text":       text,
                "question_type":       question_types[i] if i < len(question_types) else "MCQ",
                "weight":              weights[i]         if i < len(weights)         else "",
                "max_points":          max_points_list[i] if i < len(max_points_list) else "",
                "order":               orders[i]           if i < len(orders)          else i + 1,
                "randomisation_group": rand_groups[i]      if i < len(rand_groups)     else "",
                "is_required":         is_required_list[i] if i < len(is_required_list) else "",
                "explanation":         explanations[i]     if i < len(explanations)    else "",
                "numeric_config_raw":  numeric_configs[i]  if i < len(numeric_configs) else "",
                # questionnaire FK assigned after save — skip here
                "questionnaire":       None,
            })
            if not form.is_valid():
                errors["questions"].append({"row": i + 1, "errors": form.errors})
                has_errors = True
            else:
                question_forms.append(form)

        choice_keys     = post.getlist("choice_key")
        choice_texts    = post.getlist("choice_text")
        is_correct_list = post.getlist("is_correct")
        partial_scores  = post.getlist("partial_score")
        choice_orders   = post.getlist("choice_order")
        choice_exps     = post.getlist("choice_explanation")
        choice_q_idxs   = post.getlist("choice_question_index")


        choice_forms = []
        for i, key in enumerate(choice_keys):
            q_idx_str = choice_q_idxs[i] if i < len(choice_q_idxs) else None
            try:
                q_idx = int(q_idx_str)
                assert 0 <= q_idx < len(question_texts)
            except (TypeError, ValueError, AssertionError):
                errors["choices"].append(
                    f"Choice row {i + 1}: invalid question index '{q_idx_str}'."
                )
                has_errors = True
                continue

            form = AnswerChoiceForm({
                "choice_key":    key,
                "choice_text":   choice_texts[i]    if i < len(choice_texts)    else "",
                "is_correct":    is_correct_list[i] if i < len(is_correct_list) else "",
                "partial_score": partial_scores[i]  if i < len(partial_scores)  else "",
                "order":         choice_orders[i]   if i < len(choice_orders)   else i + 1,
                "explanation":   choice_exps[i]     if i < len(choice_exps)     else "",
                # question FK assigned after question save — skip FK validation here
                "question":      None,
            })
            if not form.is_valid():
                # Filter out the question FK error since we pass None intentionally
                field_errors = {
                    k: v for k, v in form.errors.items() if k != "question"
                }
                if field_errors:
                    errors["choices"].append({"row": i + 1, "errors": field_errors})
                    has_errors = True
            else:
                choice_forms.append((q_idx, form))

        if has_errors:
            logger.error(errors)
            return JsonResponse(
                {"success": False, "errors": errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        questionnaire = questionnaire_form.save()

        # Save tags
        for form in tag_objects:
            tag = form.save(commit=False)
            tag.questionnaire = questionnaire
            tag.save()

        # Save questions — keep a positional map for choice FK assignment
        saved_questions = {}                      # { original_index: Question instance }
        for original_idx, form in enumerate(question_forms):
            question = form.save(commit=False)
            question.questionnaire = questionnaire
            question.save()
            saved_questions[original_idx] = question

        # Save choices — resolve FK from saved_questions map
        for q_idx, form in choice_forms:
            choice = form.save(commit=False)
            choice.question = saved_questions[q_idx]
            choice.save()

        return JsonResponse(
            {"success": True, "message": "Questionnaire created"},
            status=status.HTTP_201_CREATED
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
        pass


    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        pass

