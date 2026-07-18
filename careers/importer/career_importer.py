# career_importer.py
#SELF NOTE MAKE SURE TO ADD A COMMAND THAT DYNAMIALLY LOOKS FOR THE FIELDS AND CREATES EMPTY FIELDS WHICH THE IMPRTER REQUIRES

from __future__ import annotations

import logging
from django.utils.text import slugify
from django.db import transaction
from careers.models import Career, CareerTag
from core.models import Tag
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class CareerImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "code",
        "title",
        "sector",
        "description",
        # "tags", -> Marked optional to handle dataset variations gracefully
    )

    # Dictionary mapping standard internal columns to their possible variations
    COLUMN_ALIASES = {
        "code": ["code", "career_code", "career code", "job_code", "id"],
        "title": ["title", "career_title", "career title", "job_title", "name"],
        "sector": ["sector", "career_sector", "industry", "department"],
        "description": ["description", "desc", "career_description", "summary"],
        "tags": ["tags", "keywords", "categories", "labels"],
    }

    def _apply_fuzzy_column_mapping(self) -> None:
        """
        Scans dataframe columns and renames them to match REQUIRED_COLUMNS 
        based on known variations, case-insensitivity, and string normalization.
        """
        def normalize_str(s: str) -> str:
            return str(s).lower().replace("_", "").replace(" ", "").strip()

        # Build a fast lookup map from our normalized aliases
        alias_lookup = {}
        for canonical_key, aliases in self.COLUMN_ALIASES.items():
            for alias in aliases:
                alias_lookup[normalize_str(alias)] = canonical_key

        rename_map = {}
        for col in self.df.columns:
            normalized_col = normalize_str(col)
            if normalized_col in alias_lookup:
                rename_map[col] = alias_lookup[normalized_col]

        if rename_map:
            self.df.rename(columns=rename_map, inplace=True)
            logger.info(f"Remapped columns using fuzzy matching: {rename_map}")

        # Ensure missing columns (like optional fields) are explicitly created as empty strings if not present
        all_possible_columns = set(self.REQUIRED_COLUMNS) | {"tags"}
        for column_field in all_possible_columns:
            if column_field not in self.df.columns:
                self.df[column_field] = ""
                logger.info(f"Dynamically generated empty column for missing field: '{column_field}'")

    def validate(self) -> None:
        # Normalize, map, and dynamically fill missing required fields before validation
        self._apply_fuzzy_column_mapping()

        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["code", "title", "sector"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        if self.df["code"].duplicated().any():
            duplicate_codes = self.df[self.df["code"].duplicated()]["code"].unique()
            raise ValueError(f"Duplicate career codes found in file: {duplicate_codes}")

        if self.df["title"].duplicated().any():
            duplicate_names = self.df[self.df["title"].duplicated()]["title"].unique()
            raise ValueError(f"Duplicate career titles found in file: {duplicate_names}")

        self.df["description"] = self.df["description"].fillna("").astype(str).str.strip()
        
        # Safely assign tags column if it exists, otherwise instantiate an empty string column
        if "tags" in self.df.columns:
            self.df["tags"] = self.df["tags"].fillna("").astype(str).str.strip()
        else:
            self.df["tags"] = ""

        logger.info("Validation passed.")

    def transform(self) -> None:
        self.records = []
        # Store a mapping of row code to raw tags string for the import_data phase
        self.row_tags_map = {}

        # Using _asdict() inside the loop to support safe fallback parsing
        for row in self.df.itertuples(index=False):
            row_dict = row._asdict() if hasattr(row, "_asdict") else row._current_via_dict
            
            career = Career(
                code=row_dict.get("code"),
                title=row_dict.get("title"),
                slug=slugify(row_dict.get("title", "")),
                sector=row_dict.get("sector"),
                description=row_dict.get("description"),
            )
            self.records.append(career)
            self.row_tags_map[row_dict.get("code")] = row_dict.get("tags", "")
            
        logger.info(f"Transformed {len(self.records)} rows into Career model instances.")

    def import_data(self) -> None:
        codes = [record.code for record in self.records]

        existing_careers = Career.objects.filter(code__in=codes)
        existing = {career.code: career for career in existing_careers}

        to_create = []
        to_update = []
        skipped_count = 0

        for record in self.records:
            if record.code not in existing:
                to_create.append(record)
            else:
                if not self.update:
                    skipped_count += 1
                    continue

                existing_record = existing[record.code]
                existing_record.title = record.title
                existing_record.slug = record.slug
                existing_record.sector = record.sector
                existing_record.description = record.description
                to_update.append(existing_record)

        if not self.dry_run:
            with transaction.atomic():
                # 1. Save Parent Careers
                if to_create:
                    Career.objects.bulk_create(to_create, batch_size=self.batch_size)
                if to_update:
                    Career.objects.bulk_update(
                        to_update,
                        fields=["title", "slug", "sector", "description"],
                        batch_size=self.batch_size,
                    )

                # Re-query all affected careers from DB to ensure we have valid IDs for relation mapping
                db_careers = {c.code: c for c in Career.objects.filter(code__in=codes)}

                # 2. Extract and resolve Tags via exact __in query
                all_tag_codes = set()
                for tags_str in self.row_tags_map.values():
                    if tags_str:
                        all_tag_codes.update([t.strip() for t in tags_str.split(",") if t.strip()])

                db_tags = {tag.code: tag for tag in Tag.objects.filter(title__in=all_tag_codes)}

                # 3. Build CareerTag through-model instances
                career_tags_to_create = []
                careers_to_clear_tags = []

                for code, record in db_careers.items():
                    tags_str = self.row_tags_map.get(code, "")
                    if not tags_str:
                        continue

                    careers_to_clear_tags.append(record.id)
                    
                    for tag_code in [t.strip() for t in tags_str.split(",") if t.strip()]:
                        tag_obj = db_tags.get(tag_code)
                        if tag_obj:
                            career_tags_to_create.append(
                                CareerTag(career=record, tag=tag_obj, recommendation_weight=1.0)
                            )
                        else:
                            logger.warning(f"Tag with code '{tag_code}' not found in database. Skipping association.")

                # 4. Update the relations table safely
                if careers_to_clear_tags:
                    CareerTag.objects.filter(career_id__in=careers_to_clear_tags).delete()
                
                if career_tags_to_create:
                    CareerTag.objects.bulk_create(career_tags_to_create, batch_size=self.batch_size)

        created_count = len(to_create)
        updated_count = len(to_update)

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