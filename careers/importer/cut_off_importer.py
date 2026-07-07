# cut_off_cluster_importer.py

from __future__ import annotations

import logging
from django.db import transaction
from django.db.models import Q
from careers.models import CutoffCluster, Course
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class CutoffClusterImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "course_ref",       # Can be course code OR course title
        "cluster_number",
        "cutoff_points",
        "year",
    )

    def validate(self) -> None:
        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["course_ref", "cluster_number", "cutoff_points", "year"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        # Check for unique combinations within the spreadsheet itself
        duplicated_rows = self.df.duplicated(subset=["course_ref", "cluster_number", "year"])
        if duplicated_rows.any():
            raise ValueError("Duplicate rows for the same course, cluster, and year found inside the import file.")

        try:
            self.df["cluster_number"] = self.df["cluster_number"].astype(int)
            self.df["year"] = self.df["year"].astype(int)
            self.df["cutoff_points"] = self.df["cutoff_points"].astype(float)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Data type conversion failed. Ensure numeric columns are well-formed: {e}")

        self.df["course_ref"] = self.df["course_ref"].astype(str).str.strip()

        logger.info("Validation passed.")

    def transform(self) -> None:
        unique_course_refs = set(self.df["course_ref"].unique())

        # Build flexible course resolution map
        course_map = {}
        if unique_course_refs:
            course_query = Q(code__in=unique_course_refs) | Q(title__in=unique_course_refs)
            for course in Course.objects.filter(course_query):
                course_map[course.code.lower()] = course
                course_map[course.title.lower()] = course

        self.records = []
        self.record_relations = []  # Mirror array to preserve direct loop indexing

        for row in self.df.itertuples(index=False):
            course_obj = course_map.get(str(row.course_ref).lower())
            if not course_obj:
                raise ValueError(f"Failed to match Course reference target: '{row.course_ref}'")

            cluster = CutoffCluster(
                cluster_number=row.cluster_number,
                cutoff_points=row.cutoff_points,
                year=row.year,
            )
            self.records.append(cluster)
            self.record_relations.append(course_obj.id)

        logger.info(f"Transformed {len(self.records)} rows into CutoffCluster model structures.")

    def import_data(self) -> None:
        # Pull distinct target parameters to slice down the existing DB lookup size
        course_ids = list(set(self.record_relations))
        years = list(set([r.year for r in self.records]))

        existing_clusters = CutoffCluster.objects.filter(
            course_id__in=course_ids,
            year__in=years
        )
        
        # Unique mapping tracking strategy using a composite lookup key tuple: (course_id, cluster_number, year)
        existing = {
            (c.course_id, c.cluster_number, c.year): c 
            for c in existing_clusters
        }

        to_create = []
        to_update = []

        for idx, record in enumerate(self.records):
            assigned_course_id = self.record_relations[idx]
            record.course_id = assigned_course_id
            
            lookup_key = (record.course_id, record.cluster_number, record.year)

            if lookup_key not in existing:
                to_create.append(record)
            else:
                if not self.update:
                    self.result.skipped += 1
                    continue

                existing_record = existing[lookup_key]
                existing_record.cutoff_points = record.cutoff_points
                to_update.append(existing_record)

        if not self.dry_run:
            with transaction.atomic():
                if to_create:
                    CutoffCluster.objects.bulk_create(to_create, batch_size=self.batch_size)
                if to_update:
                    CutoffCluster.objects.bulk_update(
                        to_update,
                        fields=["cutoff_points"],
                        batch_size=self.batch_size,
                    )

        self.result.created += len(to_create)
        self.result.updated += len(to_update)

        logger.info(
            f"Import complete summary - Created: {len(to_create)}, "
            f"Updated: {len(to_update)}, Skipped: {self.result.skipped}"
        )