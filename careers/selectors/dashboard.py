from django.db.models import QuerySet,Count
from accounts.models import UserProfile
from ..models import (
    Career, 
    Course, 
    Institution, 
    CareerPsychometricTest, 
    CareerPsychometricResponse, 
    CareerRecommendation,
    ProcessingStatus,
    RecommendationExplanation,
    ExplanationType
)
import logging

logger = logging.getLogger(__name__)

class DashboardSelector:
    """Queries and formats data required for the Career Dashboard view."""

    @staticmethod
    def get_dashboard_context(user: UserProfile) -> dict:
        try:
            latest_recommendation = (
                CareerRecommendation.objects.filter(
                    user=user, 
                    processing_status=ProcessingStatus.COMPLETED
                )
                .order_by("-generated_at")
                .first()
            )
            
            recommended_careers = []
            explored_careers = 0
            top_match_pct = 0
            top_match_title = ""
            
            if latest_recommendation:
                careers_data = latest_recommendation.get_top_careers()
                explored_careers = len(careers_data)
                if careers_data:
                    top_career_ref = careers_data[0]
                    top_match_pct = round((top_career_ref.get("fit_score", 0) * 100),2)
                    
                    career_ids = [c["career_id"] for c in careers_data[:3]]
                    careers_db = {
                        c.id: c for c in Career.objects.filter(id__in=career_ids)
                    }
                    
                    for idx, c_data in enumerate(careers_data[:3], start=1):
                        career_obj = careers_db.get(c_data["career_id"])
                        if career_obj:
                            if idx == 1:
                                top_match_title = career_obj.title
                            
                            recommended_careers.append({
                                "career": {
                                    "title": career_obj.title,
                                    "slug": career_obj.slug,
                                    "sector": career_obj.sector,
                                },
                                "rank": idx,
                                "match_pct": round((top_career_ref.get("fit_score", 0) * 100),2),
                                "reason": DashboardSelector._get_recommendation_insight(latest_recommendation),
                            })

            recommended_courses = []
            if recommended_careers:
                top_career_slug = recommended_careers[0]["career"]["slug"]
                courses = (
                    Course.objects.filter(career__slug=top_career_slug)
                    .select_related("institution", "career")[:3]
                )
                for course in courses:
                    recommended_courses.append({
                        "title": course.title,
                        "slug": course.slug,
                        "code": course.code,
                        "qualification": course.get_qualification_display(),
                        "duration_years": course.duration_years,
                        "description": course.description,
                        "institution": {
                            "name": course.institution.name,
                        },
                        "career": {
                            "title": course.career.title if course.career else "",
                        }
                    })

            tests_qs = CareerPsychometricTest.objects.filter(is_active=True).only(
                "name", "slug", "description", "category", "estimated_duration", "total_questions", "is_premium"
            )
            tests_list = [
                {
                    "name": test.name,
                    "slug": test.slug,
                    "description": test.description,
                    "category": test.category,
                    "estimated_duration": test.estimated_duration,
                    "total_questions": test.total_questions,
                    "is_premium": test.is_premium,
                }
                for test in tests_qs
            ]

            recent_responses = (
                CareerPsychometricResponse.objects.filter(user=user)
                .select_related("questionnaire")
                .order_by("-started_at")[:5]
            )
            recent_activity = []
            for resp in recent_responses:
                status_desc = "Completed" if resp.completed_at else "Started"
                recent_activity.append({
                    "description": f"{status_desc} {resp.questionnaire.name}",
                    "timestamp": resp.completed_at or resp.started_at,
                })

            trending = (
                Career.objects.annotate(course_count=Count("courses"))
                .order_by("-course_count")[:3]
                .only("title", "slug", "sector")
            )
            trending_careers = [
                {
                    "title": c.title,
                    "slug": c.slug,
                    "sector": c.sector,
                }
                for c in trending
            ]

            course_count = Course.objects.count()
            institution_count = Institution.objects.count()

            return {
                "metrics": {
                    "explored": explored_careers,
                    "top_match_pct": top_match_pct,
                    "top_match_title": top_match_title,
                    "course_count": course_count,
                    "institution_count": institution_count,
                },
                "recommended_careers": recommended_careers,
                "recommended_courses": recommended_courses,
                "trending_careers": trending_careers,
                "recent_activity": recent_activity,
                "psychometric_tests": tests_list[:2],
                "ca_tests_json": tests_list,
            }
        
        except Exception as e:
            logger.error(str(e))
            return {}

    @staticmethod
    def _get_recommendation_insight(recommendation:CareerRecommendation) ->list:
        insights = (
                RecommendationExplanation.objects
                .filter(recommendation=recommendation,explanation_type=ExplanationType.NARRATIVE)
                .distinct()
                .only("explanation_data")
            )
        
        insights_list = list(set(
            [
                insight.explanation_data.get("text","")
                for insight in insights
            ]
        ))

        return " ".join(insights_list)