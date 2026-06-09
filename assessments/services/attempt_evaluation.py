
from django.http import HttpRequest
import json
from django.db.models import Prefetch,Max
import logging
from typing import Any
import math
from .feedback_classifier import Feedback

logger = logging.getLogger(__name__)


from ..models import *
from ..forms import QuestionResponseForm

class AttemptEvaluationService:
    def __init__(self,request:HttpRequest):
        self.request = request
        self.body_data:dict[str,Any] = json.loads(request.body.decode())
        self.questinnare_id:int = self.body_data.get('questionnaire_id')
        self.answers:list[dict] = self.body_data.get('answers')
        self.send_email:bool = self.body_data.get('send_email')
        self.questionnaire = None
        self.attempt_id = None

    def setup(self):
        prefetch_questions = Prefetch(
            "questions",
            queryset=Question.objects.prefetch_related("answer_choices")
        )

        self.questionnaire = (
            Questionnaire.objects
            .filter(id=int(self.questinnare_id))
            .prefetch_related(prefetch_questions)
            .first()
        )
    
    def save_response(self):
        pass

    def handle_answers(self) -> float:
        try:
            # create an attempt
            # select the latest attempt and increase it
            latest_attempt_number = QuestionnaireAttempt.objects.filter(
                                        profile=self.request.user.profile,
                                        questionnaire_id=self.questinnare_id
                                    ).aggregate(max_attempt=Max("attempt_number"))["max_attempt"]
            
            latest_attempt_number = latest_attempt_number or 0
            new_attempt_number = latest_attempt_number + 1
            self.attempt_id = new_attempt_number
            
            attempt_instance = QuestionnaireAttempt(
                profile=self.request.user.profile, # include a fail safe for unauthenticated
                questionnaire_id=int(self.questinnare_id),
                status="COMPLETED",
                attempt_number=new_attempt_number
            )

            attempt_instance.save()

            points_awarded:float = 0.0

            for answer in self.answers:  #OPTIMIZE THIS SO THAT TIME COMPLEXITY IS NOT AN ISSUE
                question_id:int = answer.get("question_id")
                answer_value:Any = answer.get("answer_value")

                question = self.questionnaire.questions.filter(id=question_id)
                if not question.exists:
                    logger.warning(f"Question corresponding to id {question_id} does not exixt, Skipping...")
                    continue
                question = question.first()
                
                data = {
                    "question": question,
                    "answer_value": json.dumps(answer_value),
                    "attempt":attempt_instance
                }

                question_response_form = QuestionResponseForm(data=data)

                if not question_response_form.is_valid():
                    logger.warning(f"Invalid answer value {answer_value} for question id {question_id}, Errors: {question_response_form.errors}, Skipping...")
                    continue
                
                response:QuestionResponse = question_response_form.save(commit=False)
                
                answer_points:float = self.evaluate_question_answer(question,answer_value,response)
                points_awarded += float(answer_points)

            return points_awarded
            
        except Exception as e:
            logger.error(str(e))
            return 0.0


    def evaluate_question_answer(self,question:Question,answer_value:Any,response:QuestionResponse) -> float:
        match question.question_type:
            case "MCQ":
                return self.handle_mcq(question,answer_value,response)
            case "MULTI":
                return self.handle_multi(question,answer_value,response)
            case "TEXT":
                return self.handle_text(question,answer_value,response)
            case "NUMERIC":
                return self.handle_numeric(question,answer_value,response)
            case "LIKERT":
                return self.handle_likert(question,answer_value,response)
            case "RANKING":
                return self.handle_ranking(question,answer_value,response)
            case _:
                return 0.0
    
    def handle_mcq(self,question:Question,answer_value:Any,response:QuestionResponse) -> float:
        '''Multiple Choice (single answer)'''
        try:
            choices = question.answer_choices.all()
            correct_choice = choices.filter(is_correct=True)
            correct = correct_choice.first()

            if not correct:
                logger.error("No correct choice found for question %s", question.id)
                return
            
            max_points = question.max_points
            points_awarded = 0.0

            if str(answer_value).lower() == str(correct.choice_key).lower():
                response.is_correct = True
                points_awarded = max_points
                response.points_awarded = points_awarded
            else:
                response.is_correct = False

            response.save()

            return points_awarded

        except Exception as e:
            logger.error(str(e))
            return 0.0

    def handle_multi(self,question:Question,answer_value:list,response:QuestionResponse) -> float:
        try:
            if not isinstance(answer_value,list):
                return
            
            correct_choices = question.answer_choices.filter(is_correct=True).values_list("choice_key", flat=True)
            max_points = question.max_points

            correct_choices_lower = set(map(str.lower,correct_choices))
            answer_value_lower = set(map(str.lower,answer_value))

            intersection_answers = set(answer_value_lower & correct_choices_lower)

            # precision_penalty = len(answer_value_lower) / len(correct_choices_lower | answer_value_lower)
            ratio = (len(intersection_answers)/len(correct_choices_lower)) if len(correct_choices_lower) > 0 else 0
            # ratio = ratio * precision_penalty
            
            point_awarded = float(max_points) * ratio

            response.points_awarded = point_awarded
            response.is_correct = ratio == 1
            response.save()

            return point_awarded
        except Exception as e:
            logger.error(str(e))
            return 0.0

    def handle_numeric(self,question:Question,answer_value:Any,response:QuestionResponse)-> float:
        return 0.0

    def handle_text(self,question:Question,answer_value:Any,response:QuestionResponse)-> float:
        return 0.0

    def handle_likert(self,question:Question,answer_value:Any,response:QuestionResponse)-> float:
        return 0.0

    def handle_ranking(self,question:Question,answer_value:Any,response:QuestionResponse)-> float:
        return 0.0
    
    @property
    def build_response(self) ->dict[str,Any]:
        """Builds a report dictionary

        Returns:
            dict[str,Any]: report dictionary
        """

        try:
            self.setup()
            total_points:float = self.handle_answers()
            percentage = (total_points /
                          float(self.questionnaire.max_score) if float(self.questionnaire.max_score) > 0 else 0.0) * 100
            passed = percentage >= 50
            score = total_points
            feedback = Feedback.from_percentage(percentage)
            message = feedback.message.split(".")

            response = {
                "percentage":round(percentage,2),
                "passed":passed,
                "score":round(score,2),
                "max_score":float(self.questionnaire.max_score),
                "feedback":message,
                "details":str(self.questionnaire.description),
                "email_sent":False,
                "attempt_id":self.attempt_id,

            }

            return response
        except Exception as e:
            logger.error(str(e))
            return {}
