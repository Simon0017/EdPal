# careers/imports/cutoff_cluster_importer.py

from __future__ import annotations

import logging
from django.db import transaction
from django.db.models import Q
from careers.models import CutoffCluster, Course, Institution
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class CutoffClusterImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "course",        # Can be course code OR course title
        "institution",   # Can be institution code OR name
        "cluster_number",
        "cutoff_points",
        "year",
    )

    def validate(self) -> None:
        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["course", "institution", "cluster_number", "cutoff_points", "year"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        
        try:
            self.df["cluster_number"] = self.df["cluster_number"].astype(int)
            self.df["year"] = self.df["year"].astype(int)
            self.df["cutoff_points"] = self.df["cutoff_points"].astype(float)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Data type conversion failed. Ensure numeric columns are well-formed: {e}")

        self.df["course"] = self.df["course"].astype(str).str.strip()
        self.df["institution"] = self.df["institution"].astype(str).str.strip()

        logger.info("Validation passed.")

    def transform(self) -> None:
        unique_courses = [str(x).strip().lower() for x in self.df["course"].unique()]
        unique_inst_refs = [str(x).strip().lower() for x in self.df["institution"].unique()]

        course_map = {}
        if unique_courses:
            course_query = Q(code__in=unique_courses) | Q(title__in=unique_courses)
            course_query |= Q(code__in=[c.upper() for c in unique_courses]) | Q(title__in=[c.upper() for c in unique_courses])
            
            for course in Course.objects.filter(course_query):
                course_map[course.code.strip().lower()] = course
                course_map[course.title.strip().lower()] = course

        
        institution_map = {}
        if unique_inst_refs:
            # Build an efficient OR query checking code OR name case-insensitively (__iexact)
            inst_query = Q()
            for ref in unique_inst_refs:
                inst_query |= Q(code__iexact=ref) | Q(name__iexact=ref)
            
            for inst in Institution.objects.filter(inst_query):
                institution_map[inst.code.strip().lower()] = inst
                institution_map[inst.name.strip().lower()] = inst

        self.records = []
        self.record_relations = []

        for row in self.df.itertuples(index=False):
            course_obj = course_map.get(str(row.course).strip().lower())
            inst_obj = institution_map.get(str(row.institution).strip().lower())

            if not course_obj:
                raise ValueError(f"Failed to match Course reference target: '{row.course}'")
            if not inst_obj:
                raise ValueError(f"Failed to match Institution reference target: '{row.institution}'")

            cluster = CutoffCluster(
                cluster_number=row.cluster_number,
                cutoff_points=row.cutoff_points,
                year=row.year,
            )
            self.records.append(cluster)
            self.record_relations.append({
                "course_id": course_obj.id,
                "institution_id": inst_obj.id
            })

        logger.info(f"Transformed {len(self.records)} rows into CutoffCluster model structures.")

    def import_data(self) -> None:
        course_ids = list(set([rel["course_id"] for rel in self.record_relations]))
        years = list(set([r.year for r in self.records]))

        existing_clusters = CutoffCluster.objects.filter(
            course_id__in=course_ids,
            year__in=years
        )
        
        # Composite unique target row map pairing key coordinates tracking parameters
        existing = {
            (c.course_id, c.cluster_number, c.year): c 
            for c in existing_clusters
        }

        to_create = []
        to_update = []
        skipped_count = 0

        for idx, record in enumerate(self.records):
            relations = self.record_relations[idx]
            record.course_id = relations["course_id"]
            record.institution_id = relations["institution_id"]
            
            lookup_key = (record.course_id, record.cluster_number, record.year)

            if lookup_key not in existing:
                to_create.append(record)
            else:
                if not self.update:
                    skipped_count += 1
                    continue

                existing_record = existing[lookup_key]
                existing_record.cutoff_points = record.cutoff_points
                existing_record.institution_id = record.institution_id
                to_update.append(existing_record)

        if not self.dry_run:
            with transaction.atomic():
                if to_create:
                    CutoffCluster.objects.bulk_create(to_create, batch_size=self.batch_size)
                if to_update:
                    CutoffCluster.objects.bulk_update(
                        to_update,
                        fields=["cutoff_points", "institution_id"],
                        batch_size=self.batch_size,
                    )

        created_count = len(to_create)
        updated_count = len(to_update)

        # Dynamic attribute container tracking safety interface block
        for attr_name in ["result", "import_result", "_result"]:
            if hasattr(self, attr_name):
                res_obj = getattr(self, attr_name)
                if res_obj is not None:
                    res_obj.created += created_count
                    res_obj.updated += updated_count
                    res_obj.skipped += skipped_count
                    break

        logger.info(
            f"Import complete summary - Created: {created_count}, "
            f"Updated: {updated_count}, Skipped: {skipped_count}"
        )