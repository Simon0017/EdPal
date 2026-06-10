# Dashboard populator

from assessments.models import QuestionnaireAttempt, Questionnaire,QuestionResponse
from core.models import Tag
from django.db.models import Avg,Count,Q,F
from django.http import HttpResponse
import logging
from typing import Any
from collections import Counter

logger = logging.getLogger(__name__)


class DashboardService():
    def __init__(self,request:HttpResponse):
        self.request = request
        self.Attempts = None


    @property
    def stats(self) -> dict[str,Any]:
        """builds the stats metrics

        Returns:
            dict[str,Any] : metrics
        """
        try:
            attempts = (
                QuestionnaireAttempt.objects.filter(
                profile=self.request.user.profile)
                .prefetch_related("question_responses", "score")
            )
            
            self.Attempts = attempts

            metrics = attempts.aggregate(
                completed=Count("id", filter=Q(status="COMPLETED")),
                avg_pct=Avg("score__percentage"),
                in_progress = Count("id", filter=Q(status="IN_PROGRESS")),
            )

            latest_attempt = attempts.order_by("-completed_at").first()

            metrics["avg_pct"] = round(metrics["avg_pct"] or 0, 1)
            metrics["latest_score"] = round(latest_attempt.score.percentage,1) if latest_attempt and latest_attempt.score else None

            return metrics
        except Exception as e:
            logger.error(str(e))
            return {}
        
        
    @property
    def score_trend(self) -> list[dict]:
        """Builds data for the score trend chart

        Returns:
            list[dict]: 
        """
        try:
            data = [
                {
                    "score": round(a.score.percentage,1) if a.score else None,
                    "label": a.score.computed_at.strftime("%d-%m-%Y") if a.score else None,
                }
                for a in self.Attempts
            ]

            return data
        except Exception as e:
            logger.error(str(e))
            return []

    @property
    def latest_questionnaires(self) ->list[dict]:
        try:
            latest_qns = (
                Questionnaire.objects
                .filter(status="PUBLISHED")
                .order_by("-created_at")
                .values(
                    "id",
                    "created_at",
                    "status",
                    "title",
                )[:5]      
            )

            return list(latest_qns)
        
        except Exception as e:
            logger.error(str(e))
            return []
    
    @property
    def trending_tags(self) ->list[dict]:  # implement a cache and cardinality counter here in scaling
        try:
            tags = Tag.objects.all().values_list("title",flat=True)
            counter_dict = dict(Counter(list(tags)).most_common(5))
            tags_count = [
                {
                    "title":k,
                    "count":v
                } for k,v in counter_dict.items() 
            ]

            return tags_count

        except Exception as e:
            logger.error(str(e))
            return {}
        
    @property
    def category(self) -> list[dict]:
        try:
            questions_responses = (
                QuestionResponse.objects
                .filter(attempt__profile=self.request.user.profile)
                .values("question__question_type")
                .annotate(total=Count("id"))
                .order_by("question__question_type")
            )

            data = [
                {
                    "label": res["question__question_type"],
                    "value": res["total"]
                } for res in questions_responses
            ]

            return data
        except Exception as e:
            logger.error(str(e))
            return []