
'''
This module contains the view for creating a questionnaire via POST request. It is used by the questionnaire creation form in the frontend,
Thins the view is separated from the main views.py file to keep it clean and focused on rendering templates and handling GET requests.
'''

from django.http import HttpRequest
from ..forms import (
    QuestionForm,
    QuestionnaireForm,
    QuestionnaireTagForm,
    AnswerChoiceForm
)
import logging

logger = logging.getLogger(__name__)

class CreateQuestionniare:
    def __init__(self,request:HttpRequest):
        self.post = request.POST
        self.user = request.user
        self.has_errors = False
        self.errors = {"questionnaire": {}, "tags": [], "questions": [], "choices": []}
        self.question_texts   = self.post.getlist("question_text")
        self.question_types   = self.post.getlist("question_type")
        self.weights          = self.post.getlist("weight")
        self.max_points_list  = self.post.getlist("max_points")
        self.orders           = self.post.getlist("order")
        self.rand_groups      = self.post.getlist("randomisation_group")
        self.is_required_list = self.post.getlist("is_required")
        self.explanations     = self.post.getlist("explanation")
        self.numeric_configs  = self.post.getlist("numeric_config_raw")

    def create__questionnare_form(self) ->QuestionnaireForm | None:
        try:
            questionnare_form  = QuestionnaireForm(self.post)
            if not questionnare_form.is_valid():
                self.errors["questionnaire"] = questionnare_form.errors
                self.has_errors = True
            return questionnare_form
        except Exception as e:
            logger.error(str(e))

    def create_tags(self) -> list | None:
        try:
            tags_data = zip(
                self.post.getlist("tag"),
                self.post.getlist("coupling_strength"),
                self.post.getlist("is_primary"),
            )

            tag_objects = []
            for i, (tag_id, coupling, primary) in enumerate(tags_data):
                form = QuestionnaireTagForm({
                    "tag":               tag_id,
                    "coupling_strength": coupling,
                    "is_primary":        primary,
                })
                if not form.is_valid():
                    self.errors["tags"].append({"index": i, "errors": form.errors})
                    self.has_errors = True
                else:
                    tag_objects.append(form)
            
            return tag_objects
        except Exception as e:
            logger.error(str(e))
    
    def create_question_forms(self) -> list | None:
        try:
            question_forms = []
            for i, text in enumerate(self.question_texts):
                form = QuestionForm({
                    "question_text":       text,
                    "question_type":       self.question_types[i] if i < len(self.question_types) else "MCQ",
                    "weight":              self.weights[i]         if i < len(self.weights)         else "",
                    "max_points":          self.max_points_list[i] if i < len(self.max_points_list) else "",
                    "order":               self.orders[i]           if i < len(self.orders)          else i + 1,
                    "randomisation_group": self.rand_groups[i]      if i < len(self.rand_groups)     else "",
                    "is_required":         self.is_required_list[i] if i < len(self.is_required_list) else "",
                    "explanation":         self.explanations[i]     if i < len(self.explanations)    else "",
                    "numeric_config_raw":  self.numeric_configs[i]  if i < len(self.numeric_configs) else "",
                    # questionnaire FK assigned after save — skip here
                    "questionnaire":       None,
                })
                if not form.is_valid():
                    self.errors["questions"].append({"row": i + 1, "errors": form.errors})
                    self.has_errors = True
                else:
                    question_forms.append(form)

            return question_forms
        except Exception as e:
            logger.error(str(e))
    
    def create_choices_forms(self) -> list | None:
        try:
            choice_keys     = self.post.getlist("choice_key")
            choice_texts    = self.post.getlist("choice_text")
            is_correct_list = self.post.getlist("is_correct")
            partial_scores  = self.post.getlist("partial_score")
            choice_orders   = self.post.getlist("choice_order")
            choice_exps     = self.post.getlist("choice_explanation")
            choice_q_idxs   = self.post.getlist("choice_question_index")


            choice_forms = []
            for i, key in enumerate(choice_keys):
                q_idx_str = choice_q_idxs[i] if i < len(choice_q_idxs) else None
                try:
                    q_idx = int(q_idx_str)
                    assert 0 <= q_idx < len(self.question_texts)
                except (TypeError, ValueError, AssertionError):
                    self.errors["choices"].append(
                        f"Choice row {i + 1}: invalid question index '{q_idx_str}'."
                    )
                    self.has_errors = True
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
                        self.errors["choices"].append({"row": i + 1, "errors": field_errors})
                        self.has_errors = True
                else:
                    choice_forms.append((q_idx, form))

            return choice_forms
        except Exception as e:
            logger.error(str(e))
    
    def has_validation_errors(self):
        return self.has_errors
    
    def save_post(self,questionnaire_form, tag_objects:list, question_forms:list, choice_forms:list) -> bool:
        try:
            # Save questionnaire
            questionnaire = questionnaire_form.save(commit=False)
            questionnaire.created_by = self.user
            questionnaire.save()

            # Save tags
            for form in tag_objects:
                tag_obj = form.save(commit=False)
                tag_obj.questionnaire = questionnaire
                tag_obj.save()

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

            return True
        except Exception as e:
            logger.error(str(e))
            return False