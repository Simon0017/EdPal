# subject_req_importer.py

from __future__ import annotations

import logging
from django.db import transaction
from django.db.models import Q
from careers.models import SubjectRequirement, Course
from accounts.models import Subject
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class SubjectRequirementImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "course_ref",        # Can be course code OR title
        "subject_ref",       # Can be subject code OR name
        "requirement_type",  # COMPULSORY, ALTERNATIVE, OPTIONAL
        "minimum_grade",     # C+, B, etc.
    )

    VALID_REQUIREMENT_TYPES = {"COMPULSORY", "ALTERNATIVE", "OPTIONAL"}

    def validate(self) -> None:
        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["course_ref", "subject_ref", "requirement_type"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        # Check for unique combinations within the spreadsheet itself
        duplicated_rows = self.df.duplicated(subset=["course_ref", "subject_ref"])
        if duplicated_rows.any():
            raise ValueError("Duplicate requirements for the same course and subject found inside the import file.")

        # Normalize string parameters
        self.df["requirement_type"] = self.df["requirement_type"].astype(str).str.upper().str.strip()
        invalid_types = self.df[~self.df["requirement_type"].isin(self.VALID_REQUIREMENT_TYPES)]["requirement_type"].unique()
        if invalid_types.size > 0:
            raise ValueError(f"Invalid requirement types found: {invalid_types}. Must be one of {self.VALID_REQUIREMENT_TYPES}")

        self.df["course_ref"] = self.df["course_ref"].astype(str).str.strip()
        self.df["subject_ref"] = self.df["subject_ref"].astype(str).str.strip()
        self.df["minimum_grade"] = self.df["minimum_grade"].fillna("").astype(str).str.strip()

        logger.info("Validation passed.")

    def transform(self) -> None:
        unique_course_refs = set(self.df["course_ref"].unique())
        unique_subject_refs = set(self.df["subject_ref"].unique())

        # Resolve Course mappings
        course_map = {}
        if unique_course_refs:
            course_query = Q(code__in=unique_course_refs) | Q(title__in=unique_course_refs)
            for course in Course.objects.filter(course_query):
                course_map[course.code.lower()] = course
                course_map[course.title.lower()] = course

        # Resolve Subject mappings (accounts.Subject)
        subject_map = {}
        if unique_subject_refs:
            subject_query = Q(code__in=unique_subject_refs) | Q(name__in=unique_subject_refs)
            for subj in Subject.objects.filter(subject_query):
                subject_map[subj.code.lower()] = subj
                subject_map[subj.name.lower()] = subj

        self.records = []
        self.record_relations = []  # Explicit parallel tracking tuple per row index

        for row in self.df.itertuples(index=False):
            course_obj = course_map.get(str(row.course_ref).lower())
            subject_obj = subject_map.get(str(row.subject_ref).lower())

            if not course_obj:
                raise ValueError(f"Failed to match Course reference target: '{row.course_ref}'")
            if not subject_obj:
                raise ValueError(f"Failed to match Subject reference target: '{row.subject_ref}'")

            requirement = SubjectRequirement(
                requirement_type=row.requirement_type,
                minimum_grade=row.minimum_grade,
            )
            self.records.append(requirement)
            self.record_relations.append((course_obj.id, subject_obj.id))

        logger.info(f"Transformed {len(self.records)} rows into SubjectRequirement structures.")

    def import_data(self) -> None:
        course_ids = list(set([rel[0] for rel in self.record_relations]))
        subject_ids = list(set([rel[1] for rel in self.record_relations]))

        existing_requirements = SubjectRequirement.objects.filter(
            course_id__in=course_ids,
            subject_id__in=subject_ids
        )

        # Map existing db elements using a composite structural key: (course_id, subject_id)
        existing = {
            (req.course_id, req.subject_id): req 
            for req in existing_requirements
        }

        to_create = []
        to_update = []

        for idx, record in enumerate(self.records):
            course_id, subject_id = self.record_relations[idx]
            record.course_id = course_id
            record.subject_id = subject_id

            lookup_key = (record.course_id, record.subject_id)

            if lookup_key not in existing:
                to_create.append(record)
            else:
                if not self.update:
                    self.result.skipped += 1
                    continue

                existing_record = existing[lookup_key]
                existing_record.requirement_type = record.requirement_type
                existing_record.minimum_grade = record.minimum_grade
                to_update.append(existing_record)

        if not self.dry_run:
            with transaction.atomic():
                if to_create:
                    SubjectRequirement.objects.bulk_create(to_create, batch_size=self.batch_size)
                if to_update:
                    SubjectRequirement.objects.bulk_update(
                        to_update,
                        fields=["requirement_type", "minimum_grade"],
                        batch_size=self.batch_size,
                    )

        self.result.created += len(to_create)
        self.result.updated += len(to_update)

        logger.info(
            f"Import complete summary - Created: {len(to_create)}, "
            f"Updated: {len(to_update)}, Skipped: {self.result.skipped}"
        )