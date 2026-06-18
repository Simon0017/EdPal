from django.http import HttpRequest
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Max, Count, Q
from typing import Any
from ..models import Questionnaire, QuestionnaireAttempt
from core.models import Tag
import logging

logger = logging.getLogger(__name__)

class FetchQuestionnairesService:
    def __init__(self, request: HttpRequest) -> None:
        self.user = request.user if request.user.is_authenticated else None
        self.format: str = request.GET.get("format", "json")
        self.query: str = request.GET.get('q', '').strip()
        self.status_filter: str = request.GET.get('status', 'all')
        
        # Safe integer parsing with default fallbacks
        try:
            self.page: int = int(request.GET.get('page', 1))
        except (ValueError, TypeError):
            self.page = 1

    @property
    def stats(self) -> dict[str, Any]:
        """Calculates dashboard summary metrics for the authenticated user."""
        try:
            if not self.user:
                return {"total_attempts": 0, "best_score": "—", "active_topics": 0}

            profile = getattr(self.user, 'profile', None)
            attempts_qs = (
                QuestionnaireAttempt.objects.filter(profile=profile)
                .prefetch_related("score")
            )

            # 1. Aggregate core attempt metrics
            metrics = attempts_qs.aggregate(
                best_score=Max('score__percentage'),
                total_attempts=Count('id')
            )

            metrics['total_attempts'] = attempts_qs.count()

            tags = []
            for att in attempts_qs:
                tag_titles = att.questionnaire.tags.values_list('title',flat=True)
                tags.extend(tag_titles)  

            metrics["active_topics"] = len(set(tags))

            return  metrics
        except Exception as e:
            logger.error(str(e))
            return {}

    def get_paginated_response(self) -> dict[str, Any]:
        """
        Builds the complete JSON-compatible payload for the JavaScript layout,
        including structural pagination, filtered results, and stats summaries.
        """
        try:
            if not self.user:
                return {"success": False, "results": [], "next": None, "count": 0}

            profile = getattr(self.user, 'profile', None)

            # Base questionnaire query
            queryset = Questionnaire.objects.all()

            # Apply search filtering
            if self.query:
                queryset = queryset.filter(
                    Q(title__icontains=self.query) | Q(description__icontains=self.query)
                )

            queryset = queryset.annotate(
                total_attempts_count=Count('attempts', filter=Q(attempts__profile=profile)),
                max_percentage=Max('attempts__score__percentage', filter=Q(attempts__profile=profile)),
                latest_attempt_id=Max('attempts__id', filter=Q(attempts__profile=profile)),
                latest_attempt_date=Max('attempts__started_at', filter=Q(attempts__profile=profile)) 
            )

            # Apply Status filter
            if self.status_filter != 'all':
                if self.status_filter == 'completed':
                    queryset = queryset.filter(attempts__profile=profile, attempts__status__iexact='completed')
                elif self.status_filter == 'in_progress':
                    queryset = queryset.filter(attempts__profile=profile, attempts__status__iexact='in_progress')
                else:
                    queryset = queryset.filter(status__iexact=self.status_filter)

            queryset = queryset.distinct().order_by('id')

            # Pagination Engine
            paginator = Paginator(queryset, per_page=10)
            try:
                page_obj = paginator.page(self.page)
            except EmptyPage:
                return {
                    "success": True,
                    "results": [],
                    "next": None,
                    "count": paginator.count,
                    **self.stats
                }

            # SERIALIZATION LOOP 
            serialized_results = []
            for q in page_obj.object_list:
                # Format the ISO timestamp string for the frontend JS Date constructor
                date_str = q.latest_attempt_date.isoformat() if q.latest_attempt_date else None

                serialized_results.append({
                    "id": q.id,
                    "title": q.title,
                    "description": q.description,
                    "status": q.status.lower(),  
                    "attempt_count": q.total_attempts_count,
                    "percentage": q.max_percentage,
                    "attempt_id": q.latest_attempt_id,
                    "attempt_date": date_str
                })

            return {
                "success": True,
                "results": serialized_results,
                "next": page_obj.next_page_number() if page_obj.has_next() else None,
                "count": paginator.count,
                **self.stats
            }
        except Exception as e:
            logger.error(str(e))
            return {}