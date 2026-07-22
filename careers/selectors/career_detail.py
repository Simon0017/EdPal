import logging
from django.db.models import Count, OuterRef, Subquery, QuerySet,Q
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import UserProfile
from core.models import Tag
from careers.models import (
    Career,
    Course,
    Institution,
    SubjectRequirement,
    CutoffCluster,
    CareerTag,
    CareerRecommendation,
    ProcessingStatus
)

logger = logging.getLogger(__name__)

class CareerDetailSelector:

    @staticmethod
    def get_career_detail_context(user: UserProfile, slug: str | None) -> dict:
        try:
            if not slug:
                raise ValueError("A valid career slug must be provided.")

            career = Career.objects.only("id", "code", "title", "slug", "description", "sector").get(slug=slug)

            courses = (
                Course.objects.filter(career=career)
                .annotate(institution_count=Count("institution", distinct=True))
                .only("code", "title", "slug", "description", "qualification", "duration_years")
            )

            institutions = (
                Institution.objects.filter(courses__career=career)
                .annotate(course_count=Count("courses", filter=Q(courses__career=career)))
                .distinct()
                .only("code", "name", "slug", "type", "website", "country")
            )

            course_ids = courses.values_list("id", flat=True)
            subject_requirements = (
                SubjectRequirement.objects.filter(course_id__in=course_ids)
                .order_by(
                    "subject_id",
                    "requirement_type",
                    "minimum_grade",
                )
                .distinct(
                    "subject_id",
                    "requirement_type",
                    "minimum_grade",
                )
            )

            cutoff_clusters = (
                CutoffCluster.objects.filter(course_id__in=course_ids)
                .order_by(
                    "-year",
                    "cluster_number",
                    "cutoff_points",
                    "course_id",
                )
                .distinct(
                    "year",
                    "cluster_number",
                    "cutoff_points",
                )
            )
            match_pct = CareerDetailSelector._get_user_match_percentage(user, career.slug)
            similar_careers = (
                Career.objects.filter(sector=career.sector)
                .exclude(id=career.id)
                .only("code", "title", "slug", "description", "sector")[:6]
            )

            career_tags = (
                Tag.objects.filter(careers=career)
                .annotate(
                    recommendation_weight=Subquery(
                        CareerTag.objects.filter(career=career, tag=OuterRef("pk")).values("recommendation_weight")[:1]
                    )
                )
                .only("title", "slug")
            )

            return {
                "career": career,
                "courses": courses,
                "institutions": institutions,
                "subject_requirements": subject_requirements,
                "cutoff_clusters": cutoff_clusters,
                "match_pct": match_pct,
                "similar_careers": similar_careers,
                "career_tags": career_tags,
                "page_title": career.title,
            }

        except ObjectDoesNotExist as e:
            logger.warning(f"Career detail lookup failed. Slug '{slug}' not found: {e}")
            return CareerDetailSelector._get_empty_fallback_context()
        except Exception as e:
            logger.error(f"Error compiling career detail context for slug '{slug}': {e}", exc_info=True)
            return CareerDetailSelector._get_empty_fallback_context()

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

            careers_data = recommendation.recommendation_details.get("ranked_careers", [])
            for c_data in careers_data:
                career_id = c_data.get("career_id")
                career_obj = Career.objects.get(id=career_id)
                if career_obj.slug == career_slug:
                    return int(c_data.get("fit_score", 0) * 100)
            return None
        except Exception as e:
            logger.error(f"Failed to fetch user match percentage: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_empty_fallback_context() -> dict:
        return {
            "career": None,
            "courses": Course.objects.none(),
            "institutions": Institution.objects.none(),
            "subject_requirements": SubjectRequirement.objects.none(),
            "cutoff_clusters": CutoffCluster.objects.none(),
            "match_pct": None,
            "similar_careers": Career.objects.none(),
            "career_tags": Tag.objects.none(),
            "page_title": "Career Not Found",
        }