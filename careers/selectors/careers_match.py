import logging
from django.db.models import Count, Q
from django.utils.safestring import SafeString
from accounts.models import UserProfile
from careers.models import (
    Career,
    Course,
    Institution,
    SubjectRequirement,
    CutoffCluster,
    CareerRecommendation,
    CareerPsychometricTest,
    ProcessingStatus
)

logger = logging.getLogger(__name__)

class CareerMatchSelector:

    @staticmethod
    def get_career_match_context(user: UserProfile, career_slug: str | None = None) -> dict:
        try:
            # 1. Base Structure & Fallback defaults
            context = {
                "career": {},
                "match_pct": 0,
                "insights": [],
                "recommended_courses": [],
                "subject_requirements": [],
                "cutoff_clusters": [],
                "institutions": [],
                "similar_careers": [],
                "user_grades": {},
                "user_points": 0.0,
                "careers": [],
                "courses": [],
                "subject_reqs": [],
                "cutoffs": [],
                "ca_tests_json": [],
            }

            # 2. Fetch User Profile Specific Data (Grades, Points) Defensively
            context["user_grades"] = CareerMatchSelector._get_user_grades(user)
            context["user_points"] = CareerMatchSelector._get_user_points(user)

            # 3. Retrieve User's Match Mapping via Recommendation Details
            recommendation = CareerMatchSelector._get_latest_recommendation(user)
            match_map = CareerMatchSelector._extract_match_map(recommendation)

            # 4. Resolve Target Career Context
            target_career = CareerMatchSelector._resolve_target_career(career_slug, match_map)
            if not target_career:
                # If no target career matches or exists, return context with active choices and tests only
                context["ca_tests_json"] = CareerMatchSelector._get_psychometric_tests()
                return context

            # 5. Populate Target Career Details
            match_detail = match_map.get(target_career.slug, {})
            context["career"] = {
                "title": target_career.title,
                "slug": target_career.slug,
                "sector": target_career.sector,
                "description": target_career.description,
            }
            context["match_pct"] = match_detail.get("match_pct", 0)
            context["insights"] = recommendation.recommendation_details.get("insights", []) if recommendation else []

            # 6. Pull Target Specific Courses & Linked Objects
            courses_list = CareerMatchSelector._get_courses_for_career(target_career.slug)
            context["recommended_courses"] = courses_list
            context["courses"] = courses_list

            # 7. Pull Course Requirements (Subject and Cutoffs)
            course_ids = [c["id"] for c in courses_list if "id" in c]
            reqs = CareerMatchSelector._get_subject_requirements(course_ids)
            context["subject_requirements"] = reqs
            context["subject_reqs"] = reqs

            cutoffs = CareerMatchSelector._get_cutoff_clusters(course_ids)
            context["cutoff_clusters"] = cutoffs
            context["cutoffs"] = cutoffs

            # 8. Pull Distinct Dynamic Entities (Institutions, Similar Careers, Lists)
            context["institutions"] = CareerMatchSelector._extract_distinct_institutions(courses_list)
            context["similar_careers"] = CareerMatchSelector._get_similar_careers(target_career)
            
            context["careers"] = [context["career"]]
            context["ca_tests_json"] = CareerMatchSelector._get_psychometric_tests()

            return context
        except Exception as e:
            logger.error(f"Error compiling career match context: {e}", exc_info=True)
            return {}

    @staticmethod
    def _get_user_grades(user: UserProfile) -> dict[str, str]:
        try:
            # Safely navigate to grades depending on how your UserProfile stores academic results
            return getattr(user, "academic_grades", {}) or {}
        except Exception as e:
            logger.error(f"Failed to fetch user grades: {e}", exc_info=True)
            return {}

    @staticmethod
    def _get_user_points(user: UserProfile) -> float:
        try:
            return float(getattr(user, "aggregate_points", 0.0) or 0.0)
        except Exception as e:
            logger.error(f"Failed to fetch aggregate points: {e}", exc_info=True)
            return 0.0

    @staticmethod
    def _get_latest_recommendation(user: UserProfile) -> CareerRecommendation | None:
        try:
            return (
                CareerRecommendation.objects.filter(
                    user=user, 
                    processing_status=ProcessingStatus.COMPLETED
                )
                .order_by("-generated_at")
                .only("recommendation_details")
                .first()
            )
        except Exception as e:
            logger.error(f"Failed to retrieve latest recommendation: {e}", exc_info=True)
            return None

    @staticmethod
    def _extract_match_map(recommendation: CareerRecommendation | None) -> dict[str, dict]:
        try:
            if not recommendation:
                return {}
            careers_data = recommendation.recommendation_details.get("careers", [])
            return {item["slug"]: item for item in careers_data if "slug" in item}
        except Exception as e:
            logger.error(f"Failed to extract recommendation mapping: {e}", exc_info=True)
            return {}

    @staticmethod
    def _resolve_target_career(slug: str | None, match_map: dict[str, dict]) -> Career | None:
        try:
            if slug:
                return Career.objects.filter(slug=slug).first()
            if match_map:
                top_slug = list(match_map.keys())[0]
                return Career.objects.filter(slug=top_slug).first()
            return Career.objects.first()
        except Exception as e:
            logger.error(f"Failed to resolve target career: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_courses_for_career(career_slug: str) -> list[dict]:
        try:
            queryset = (
                Course.objects.filter(career__slug=career_slug)
                .select_related("institution", "career")
                .only(
                    "id", "title", "slug", "code", "qualification", "duration_years", "description",
                    "institution__name", "institution__slug", "institution__code", "institution__type",
                    "institution__country", "institution__website", "career__title", "career__slug",
                    "career__sector"
                )[:10]
            )

            # Avoid direct database grouping on institutions by mapping it in memory
            inst_course_counts = dict(
                Institution.objects.annotate(c_count=Count("courses")).values_list("id", "c_count")
            )

            return [
                {
                    "id": course.id,
                    "title": course.title,
                    "slug": course.slug,
                    "code": course.code,
                    "qualification": course.get_qualification_display(),
                    "duration_years": course.duration_years,
                    "description": course.description,
                    "institution": {
                        "name": course.institution.name,
                        "slug": course.institution.slug,
                        "code": course.institution.code,
                        "type": course.institution.get_type_display() if hasattr(course.institution, "get_type_display") else course.institution.type,
                        "country": course.institution.country,
                        "website": course.institution.website or "",
                        "course_count": inst_course_counts.get(course.institution.id, 0),
                    },
                    "career": {
                        "title": course.career.title if course.career else "",
                        "slug": course.career.slug if course.career else "",
                        "sector": course.career.sector if course.career else "",
                    }
                }
                for course in queryset
            ]
        except Exception as e:
            logger.error(f"Failed to fetch courses: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_subject_requirements(course_ids: list[int]) -> list[dict]:
        try:
            if not course_ids:
                return []
            queryset = (
                SubjectRequirement.objects.filter(course_id__in=course_ids)
                .select_related("subject")
                .only("subject__name", "requirement_type", "minimum_grade")
            )
            return [
                {
                    "subject": req.subject.name if hasattr(req.subject, "name") else str(req.subject),
                    "requirement_type": req.requirement_type,
                    "minimum_grade": req.minimum_grade,
                }
                for req in queryset
            ]
        except Exception as e:
            logger.error(f"Failed to fetch subject requirements: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_cutoff_clusters(course_ids: list[int]) -> list[dict]:
        try:
            if not course_ids:
                return []
            queryset = (
                CutoffCluster.objects.filter(course_id__in=course_ids)
                .only("year", "cluster_number", "cutoff_points")
                .order_by("-year", "cluster_number")[:10]
            )
            return [
                {
                    "year": record.year,
                    "cluster_number": record.cluster_number,
                    "cutoff_points": float(record.cutoff_points),
                }
                for record in queryset
            ]
        except Exception as e:
            logger.error(f"Failed to fetch cutoff clusters: {e}", exc_info=True)
            return []

    @staticmethod
    def _extract_distinct_institutions(courses_list: list[dict]) -> list[dict]:
        try:
            seen_slugs = set()
            distinct_institutions = []
            for item in courses_list:
                inst = item.get("institution")
                if inst and inst.get("slug") not in seen_slugs:
                    seen_slugs.add(inst["slug"])
                    distinct_institutions.append(inst)
            return distinct_institutions
        except Exception as e:
            logger.error(f"Failed parsing distinct institutions: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_similar_careers(target_career: Career) -> list[dict]:
        try:
            queryset = (
                Career.objects.filter(sector=target_career.sector)
                .exclude(id=target_career.id)
                .annotate(course_count=Count("courses"))
                .only("title", "slug", "sector", "description")[:5]
            )
            return [
                {
                    "title": c.title,
                    "slug": c.slug,
                    "sector": c.sector,
                    "description": c.description,
                    "course_count": getattr(c, "course_count", 0),
                }
                for c in queryset
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve similar careers: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_psychometric_tests() -> list[dict]:
        try:
            tests_qs = CareerPsychometricTest.objects.filter(is_active=True).only(
                "name", "slug", "description", "category", "estimated_duration", "total_questions", "is_premium"
            )
            return [
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
        except Exception as e:
            logger.error(f"Failed to compile psychometric test list: {e}", exc_info=True)
            return []