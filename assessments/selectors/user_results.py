import logging
from ..models import QuestionnaireAttempt
from accounts.models import UserProfile
from django.db.models import Count,Avg,Max,Q

logger = logging.getLogger(__name__)


class UserResultsSelector():

    @staticmethod
    def get_user_results(profile:UserProfile):
        attempts = QuestionnaireAttempt.objects.filter(
            profile=profile
        ).prefetch_related("question_responses", "score")

        metrics = attempts.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="COMPLETED")),
            avg_pct=Avg("score__percentage"),
            best_score=Max("score__percentage"),
            passed=Count("id", filter=Q(score__percentage__gt=50))
        )

        metrics["avg_pct"] = round(metrics["avg_pct"] or 0, 1)
        metrics["best_score"] = round(metrics["best_score"] or 0, 1)

        data = {
                **metrics,
                "results":[
                    {
                        "title":attempt.questionnaire.title,
                        "completed_at":attempt.completed_at,
                        "attempt_number":attempt.attempt_number,
                        "passed":attempt.score.percentage > 50,
                        "percentage":round(attempt.score.percentage,1),
                        "raw_score":attempt.score.raw_score,
                        "max_score":attempt.score.raw_score,
                        "percentile_rank":(attempt.score.percentile_rank or 0),
                        "started_at":attempt.started_at,
                        "completed_at":attempt.completed_at,
                        "attempt_id":attempt.id

                    } for attempt in attempts 
                ]
        }

        return data