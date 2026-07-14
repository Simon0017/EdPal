import logging
from django.db.models import Count, Q, QuerySet
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import UserProfile
from careers.models import (
    Career,
    Course,
    Institution,
    SubjectRequirement,
    CutoffCluster,
    CareerRecommendation,
    ProcessingStatus
)

logger = logging.getLogger(__name__)

class CourseDetailSelector:

    @staticmethod
    def get_course_detail_context(user: UserProfile, slug: str | None) -> dict:
        try:
            if not slug:
                raise ValueError("A valid course slug must be provided.")

            # 1. Fetch main course and select_related career link defensively
            course = (
                Course.objects.select_related("career")
                .only(
                    "id", "code", "title", "slug", "description", "qualification", "duration_years",
                    "career__id", "career__code", "career__title", "career__slug", "career__description", "career__sector"
                )
                .get(slug=slug)
            )

            career = course.career

            # 2. Extract institution(s) as an annotated QuerySet as expected by the context
            institutions = (
                Institution.objects.filter(courses=course)
                .annotate(course_count=Count("courses"))
                .only("code", "name", "slug", "type", "website", "country")
            )

            # 3. Get specific subject requirements
            subject_requirements = (
                SubjectRequirement.objects.filter(course=course)
                .select_related("subject")
                .only("subject__name", "requirement_type", "minimum_grade")
            )

            # 4. Get cutoff clusters
            cutoff_clusters = (
                CutoffCluster.objects.filter(course=course)
                .only("cluster_number", "cutoff_points", "year")
                .order_by("-year", "cluster_number")
            )

            # 5. Determine the lowest cutoff for the most recent year available
            latest_cutoff = CourseDetailSelector._get_latest_cutoff(course)

            # 6. Retrieve related courses within the same career path (max 6)
            related_courses = Course.objects.none()
            match_pct = None
            if career:
                related_courses = (
                    Course.objects.filter(career=career)
                    .exclude(id=course.id)
                    .only("code", "title", "slug", "description", "qualification", "duration_years")[:6]
                )
                match_pct = CourseDetailSelector._get_user_match_percentage(user, career.slug)

            return {
                "course": course,
                "career": career,
                "institutions": institutions,
                "subject_requirements": subject_requirements,
                "cutoff_clusters": cutoff_clusters,
                "related_courses": related_courses,
                "latest_cutoff": latest_cutoff,
                "match_pct": match_pct,
            }

        except ObjectDoesNotExist as e:
            logger.warning(f"Course detail lookup failed. Slug '{slug}' not found: {e}")
            return CourseDetailSelector._get_empty_fallback_context()
        except Exception as e:
            logger.error(f"Error compiling course detail context for slug '{slug}': {e}", exc_info=True)
            return CourseDetailSelector._get_empty_fallback_context()

    @staticmethod
    def _get_latest_cutoff(course: Course) -> float | None:
        try:
            # Sort by year descending and cutoff points ascending to grab the lowest point entry for the latest year
            latest_cluster = (
                CutoffCluster.objects.filter(course=course)
                .order_by("-year", "cutoff_points")
                .only("cutoff_points")
                .first()
            )
            return float(latest_cluster.cutoff_points) if latest_cluster else None
        except Exception as e:
            logger.error(f"Failed to resolve latest cutoff points: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_user_match_percentage(user: UserProfile, career_slug: str) -> int | None:
        try:
            recommendation = (
                CareerRecommendation.objects.filter(
                    user=user, 
                    processing_status=ProcessingStatus.COMPLETED
                )
                .order_by("-generated_at")
                .only("recommendation_details")
                .first()
            )
            if not recommendation:
                return None

            careers_data = recommendation.recommendation_details.get("careers", [])
            for c_data in careers_data:
                if c_data.get("slug") == career_slug:
                    return int(c_data.get("match_pct", 0))
            return None
        except Exception as e:
            logger.error(f"Failed to fetch user match percentage for career '{career_slug}': {e}", exc_info=True)
            return None

    @staticmethod
    def _get_empty_fallback_context() -> dict:
        return {
            "course": None,
            "career": None,
            "institutions": Institution.objects.none(),
            "subject_requirements": SubjectRequirement.objects.none(),
            "cutoff_clusters": CutoffCluster.objects.none(),
            "related_courses": Course.objects.none(),
            "latest_cutoff": None,
            "match_pct": None,
        }