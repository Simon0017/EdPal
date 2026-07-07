# course_importer.py

from __future__ import annotations

import logging
from django.utils.text import slugify
from django.db import transaction
from django.db.models import Q
from careers.models import Course, Career, Institution
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class CourseImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "code",
        "title",
        "qualification",
        "institution_ref",  # Can hold institution code OR name
        "career_ref",       # Can hold career code OR title
        "duration_years",
        "description",
    )

    VALID_QUALIFICATIONS = {"DEGREE", "DIPLOMA", "CERTIFICATE"}

    def validate(self) -> None:
        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["code", "title", "qualification", "institution_ref", "career_ref"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        if self.df["code"].duplicated().any():
            duplicate_codes = self.df[self.df["code"].duplicated()]["code"].unique()
            raise ValueError(f"Duplicate course codes found in file: {duplicate_codes}")

        if self.df["title"].duplicated().any():
            duplicate_titles = self.df[self.df["title"].duplicated()]["title"].unique()
            raise ValueError(f"Duplicate course titles found in file: {duplicate_titles}")

        # Normalize capitalization for choices lookup
        self.df["qualification"] = self.df["qualification"].astype(str).str.upper().str.strip()
        invalid_quals = self.df[~self.df["qualification"].isin(self.VALID_QUALIFICATIONS)]["qualification"].unique()
        if invalid_quals.size > 0:
            raise ValueError(f"Invalid qualifications found: {invalid_quals}. Must be one of {self.VALID_QUALIFICATIONS}")

        self.df["duration_years"] = self.df["duration_years"].fillna(4).astype(int)
        self.df["description"] = self.df["description"].fillna("").astype(str).str.strip()
        self.df["institution_ref"] = self.df["institution_ref"].astype(str).str.strip()
        self.df["career_ref"] = self.df["career_ref"].astype(str).str.strip()

        logger.info("Validation passed.")

    def transform(self) -> None:
        unique_inst_refs = set(self.df["institution_ref"].unique())
        unique_career_refs = set(self.df["career_ref"].unique())

        institution_map = {}
        if unique_inst_refs:
            inst_query = Q(code__in=unique_inst_refs) | Q(name__in=unique_inst_refs)
            for inst in Institution.objects.filter(inst_query):
                institution_map[inst.code.lower()] = inst
                institution_map[inst.name.lower()] = inst

        career_map = {}
        if unique_career_refs:
            career_query = Q(code__in=unique_career_refs) | Q(title__in=unique_career_refs)
            for career in Career.objects.filter(career_query):
                career_map[career.code.lower()] = career
                career_map[career.title.lower()] = career

        self.records = []
        # Store relational assignments out-of-band to map during database save execution
        self.record_relations = {}

        #Populate the object staging collections
        for row in self.df.itertuples(index=False):
            inst_obj = institution_map.get(str(row.institution_ref).lower())
            career_obj = career_map.get(str(row.career_ref).lower())

            if not inst_obj:
                raise ValueError(f"Failed to match Institution reference target: '{row.institution_ref}'")
            if not career_obj:
                raise ValueError(f"Failed to match Career reference target: '{row.career_ref}'")

            course = Course(
                code=row.code,
                title=row.title,
                slug=slugify(row.title),
                qualification=row.qualification,
                duration_years=row.duration_years,
                description=row.description,
            )
            
            self.records.append(course)
            self.record_relations[row.code] = {
                "institution_id": inst_obj.id,
                "career_id": career_obj.id,
            }

        logger.info(f"Transformed {len(self.records)} rows into Course model structures.")

    def import_data(self) -> None:
        codes = [record.code for record in self.records]

        existing_courses = Course.objects.filter(code__in=codes)
        existing = {course.code: course for course in existing_courses}

        to_create = []
        to_update = []

        for record in self.records:
            # Reattach the resolved foreign key pointers safely prior to compilation
            relations = self.record_relations[record.code]
            record.institution_id = relations["institution_id"]
            record.career_id = relations["career_id"]

            if record.code not in existing:
                to_create.append(record)
            else:
                if not self.update:
                    self.result.skipped += 1
                    continue

                existing_record = existing[record.code]
                existing_record.title = record.title
                existing_record.slug = record.slug
                existing_record.qualification = record.qualification
                existing_record.duration_years = record.duration_years
                existing_record.description = record.description
                existing_record.institution_id = record.institution_id
                existing_record.career_id = record.career_id
                to_update.append(existing_record)

        if not self.dry_run:
            with transaction.atomic():
                if to_create:
                    Course.objects.bulk_create(to_create, batch_size=self.batch_size)
                if to_update:
                    Course.objects.bulk_update(
                        to_update,
                        fields=[
                            "title",
                            "slug",
                            "qualification",
                            "duration_years",
                            "description",
                            "institution_id",
                            "career_id",
                        ],
                        batch_size=self.batch_size,
                    )

        self.result.created += len(to_create)
        self.result.updated += len(to_update)

        logger.info(
            f"Import complete summary - Created: {len(to_create)}, "
            f"Updated: {len(to_update)}, Skipped: {self.result.skipped}"
        )