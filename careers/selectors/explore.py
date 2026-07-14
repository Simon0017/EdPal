import logging
from django.db.models import Count, Q, QuerySet
from accounts.models import UserProfile
from careers.models import Career, Course, Institution, CareerRecommendation

logger = logging.getLogger(__name__)

class ExploreSelector:

    @staticmethod
    def get_explore_context(user: UserProfile, search_query: str | None = None) -> dict:
        try:
            safe_query = (search_query or "").strip()
            
            careers = ExploreSelector._fetch_careers(user, safe_query)
            courses = ExploreSelector._fetch_courses(safe_query)
            institutions = ExploreSelector._fetch_institutions(safe_query)
            
            sectors = ExploreSelector._get_distinct_sectors()
            qualifications = ExploreSelector._get_distinct_qualifications()
            countries = ExploreSelector._get_distinct_countries()

            return {
                "careers": careers,
                "courses": courses,
                "institutions": institutions,
                "sectors": sectors,
                "qualifications": qualifications,
                "countries": countries,
            }
        except Exception as e:
            logger.error(f"Error compiling explore context: {e}", exc_info=True)
            return {
                "careers": [],
                "courses": [],
                "institutions": [],
                "sectors": [],
                "qualifications": [],
                "countries": [],
            }

    @staticmethod
    def _fetch_careers(user: UserProfile, query: str) -> list[dict]:
        try:
            match_pct_map = ExploreSelector._get_user_match_percentages(user)
            
            queryset = Career.objects.annotate(course_count=Count("courses"))
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | 
                    Q(sector__icontains=query) | 
                    Q(description__icontains=query)
                )
            
            careers_data = queryset.only("title", "slug", "sector", "description")[:15]
            
            return [
                {
                    "title": career.title,
                    "slug": career.slug,
                    "sector": career.sector,
                    "description": career.description,
                    "course_count": getattr(career, "course_count", 0),
                    "match_pct": match_pct_map.get(career.slug, 0),
                }
                for career in careers_data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch careers: {e}", exc_info=True)
            return []

    @staticmethod
    def _fetch_courses(query: str) -> list[dict]:
        try:
            queryset = Course.objects.select_related("institution", "career")
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | 
                    Q(code__icontains=query) | 
                    Q(description__icontains=query)
                )
                
            courses_data = queryset.only(
                "title", "slug", "qualification", "duration_years", "description",
                "institution__name", "institution__slug", "institution__code", 
                "institution__type", "institution__country", "institution__website",
                "career__title", "career__slug", "career__sector"
            )[:15]

            institution_course_counts = ExploreSelector._get_institution_course_counts()

            return [
                {
                    "title": course.title,
                    "slug": course.slug,
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
                        "course_count": institution_course_counts.get(course.institution.id, 0),
                    },
                    "career": {
                        "title": course.career.title if course.career else "",
                        "slug": course.career.slug if course.career else "",
                        "sector": course.career.sector if course.career else "",
                    }
                }
                for course in courses_data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch courses: {e}", exc_info=True)
            return []

    @staticmethod
    def _fetch_institutions(query: str) -> list[dict]:
        try:
            queryset = Institution.objects.annotate(course_count=Count("courses"))
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) | 
                    Q(code__icontains=query) | 
                    Q(country__icontains=query)
                )
                
            institutions_data = queryset.only("name", "slug", "code", "type", "country", "website")[:15]

            return [
                {
                    "name": inst.name,
                    "slug": inst.slug,
                    "code": inst.code,
                    "type": inst.get_type_display() if hasattr(inst, "get_type_display") else inst.type,
                    "country": inst.country,
                    "website": inst.website or "",
                    "course_count": getattr(inst, "course_count", 0),
                }
                for inst in institutions_data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch institutions: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_user_match_percentages(user: UserProfile) -> dict[str, int]:
        try:
            latest_recommendation = (
                CareerRecommendation.objects.filter(user=user, processing_status="COMPLETED")
                .order_by("-generated_at")
                .only("recommendation_details")
                .first()
            )
            if not latest_recommendation:
                return {}
            
            careers_list = latest_recommendation.recommendation_details.get("careers", [])
            return {item["slug"]: item.get("match_pct", 0) for item in careers_list if "slug" in item}
        except Exception as e:
            logger.error(f"Failed to load user recommendation details: {e}", exc_info=True)
            return {}

    @staticmethod
    def _get_institution_course_counts() -> dict[int, int]:
        try:
            counts = Institution.objects.annotate(c_count=Count("courses")).values_list("id", "c_count")
            return dict(counts)
        except Exception as e:
            logger.error(f"Failed to load institution course counts: {e}", exc_info=True)
            return {}

    @staticmethod
    def _get_distinct_sectors() -> list[str]:
        try:
            return list(Career.objects.values_list("sector", flat=True).distinct().order_by("sector"))
        except Exception as e:
            logger.error(f"Failed to fetch unique sectors: {e}", exc_info=True)
            return []

    @staticmethod
    def _get_distinct_qualifications() -> list[str]:
        try:
            choices = Course._meta.get_field("qualification").choices
            return [display for _, display in choices]
        except Exception as e:
            logger.error(f"Failed to parse qualification choices: {e}", exc_info=True)
            return ["Bachelor's Degree", "Diploma", "Certificate"]

    @staticmethod
    def _get_distinct_countries() -> list[str]:
        try:
            return list(Institution.objects.values_list("country", flat=True).distinct().order_by("country"))
        except Exception as e:
            logger.error(f"Failed to fetch unique countries: {e}", exc_info=True)
            return []