import logging
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from careers.models import (
    Institution,
    Course,
    Career,
    CutoffCluster,
    SubjectRequirement
)

logger = logging.getLogger(__name__)

class InstitutionDetailSelector:

    @staticmethod
    def get_institution_detail_context(slug: str | None) -> dict:
        try:
            if not slug:
                raise ValueError("A valid institution slug must be provided.")

            # 1. Fetch main institution safely
            institution = Institution.objects.only(
                "id", "code", "name", "slug", "type", "website", "country"
            ).get(slug=slug)

            # 2. Get all courses offered at this institution as JSON-serializable dicts
            courses_qs = (
                Course.objects.filter(institution=institution)
                .select_related("career")
                .only(
                    "code", "title", "slug", "description", "qualification", "duration_years",
                    "career__id", "career__code", "career__title", "career__slug", "career__sector"
                )
            )
            
            courses_list = [
                {
                    "code": course.code,
                    "title": course.title,
                    "slug": course.slug,
                    "description": course.description,
                    "qualification": course.get_qualification_display(),
                    "duration_years": course.duration_years,
                    "career": {
                        "code": course.career.code if course.career else "",
                        "title": course.career.title if course.career else "",
                        "slug": course.career.slug if course.career else "",
                        "sector": course.career.sector if course.career else "",
                    } if course.career else None
                }
                for course in courses_qs
            ]

            # 3. Get distinct careers and count only courses offered by this institution
            careers_qs = (
                Career.objects.filter(courses__institution=institution)
                .annotate(course_count=Count("courses", filter=Q(courses__institution=institution)))
                .distinct()
                .only("code", "title", "slug", "description", "sector")
            )
            
            careers_list = [
                {
                    "code": career.code,
                    "title": career.title,
                    "slug": career.slug,
                    "description": career.description,
                    "sector": career.sector,
                    "course_count": getattr(career, "course_count", 0),
                }
                for career in careers_qs
            ]

            # 4. Extract unique qualification display names and sectors for UI chips
            qualifications = list(
                courses_qs.exclude(qualification="")
                .values_list("qualification", flat=True)
                .distinct()
            )
            qual_map = dict(Course._meta.get_field("qualification").choices)
            readable_quals = [qual_map.get(q, q) for q in qualifications]

            sectors = list(
                careers_qs.exclude(sector="")
                .values_list("sector", flat=True)
                .distinct()
            )

            # 5. Retrieve cutoff clusters mapped to this institution's course offerings
            cutoff_qs = (
                CutoffCluster.objects.filter(institution=institution)
                .select_related("course")
                .only(
                    "cluster_number", "cutoff_points", "year",
                    "course__code", "course__title", "course__slug"
                )
                .order_by("-year")
            )
            
            cutoff_list = [
                {
                    "cluster_number": cutoff.cluster_number,
                    "cutoff_points": float(cutoff.cutoff_points),
                    "year": cutoff.year,
                    "course": {
                        "code": cutoff.course.code,
                        "title": cutoff.course.title,
                        "slug": cutoff.course.slug,
                    }
                }
                for cutoff in cutoff_qs
            ]

            # 6. Retrieve subject requirements across this institution's courses
            course_ids = courses_qs.values_list("id", flat=True)
            subject_qs = (
                SubjectRequirement.objects.filter(course_id__in=course_ids)
                .select_related("subject", "course")
                .only(
                    "requirement_type", "minimum_grade",
                    "subject__name", "course__title", "course__slug"
                )
                .order_by("subject__name")
                .distinct()
            )
            
            subject_list = [
                {
                    "requirement_type": req.requirement_type,
                    "minimum_grade": req.minimum_grade,
                    "subject": req.subject.name,
                    "course": {
                        "title": req.course.title,
                        "slug": req.course.slug,
                    }
                }
                for req in subject_qs
            ]

            return {
                "institution": institution,
                "courses": courses_list,
                "careers": careers_list,
                "qualifications": readable_quals,
                "sectors": sectors,
                "cutoff_clusters": cutoff_list,
                "subject_requirements": subject_list,
                "course_count": len(courses_list),
                "career_count": len(careers_list),
            }

        except ObjectDoesNotExist as e:
            logger.warning(f"Institution lookup failed. Slug '{slug}' not found: {e}")
            return InstitutionDetailSelector._get_empty_fallback_context()
        except Exception as e:
            logger.error(f"Error compiling institution detail context for slug '{slug}': {e}", exc_info=True)
            return InstitutionDetailSelector._get_empty_fallback_context()

    @staticmethod
    def _get_empty_fallback_context() -> dict:
        return {
            "institution": None,
            "courses": [],
            "careers": [],
            "qualifications": [],
            "sectors": [],
            "cutoff_clusters": [],
            "subject_requirements": [],
            "course_count": 0,
            "career_count": 0,
        }