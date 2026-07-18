from __future__ import annotations

import logging
from django.utils.text import slugify
from careers.models import Institution
from .base_importer import BaseImporter
from .general_utils import validate_required_columns

logger = logging.getLogger(__name__)


class InstitutionImporter(BaseImporter):
    REQUIRED_COLUMNS = (
        "code",
        "name",
        "type",
        "website",
        "country",
    )

    # Dictionary mapping standard required columns to their potential user-provided variations
    COLUMN_ALIASES = {
        "code": ["code", "institution_code", "institution code", "inst_code", "id"],
        "name": ["name", "institution_name", "institution name", "inst_name", "title"],
        "type": ["type", "institution_type", "institution type", "inst_type", "category"],
        "website": ["website", "url", "web_link", "web link", "site"],
        "country": ["country", "nation", "location"],
    }

    VALID_TYPES = {
        "PUBLIC_UNIVERSITY",
        "PRIVATE_UNIVERSITY",
        "TECHNICAL",
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

    def validate(self) -> None:
        # Normalize and map column variations to standard internal keys first
        self._apply_fuzzy_column_mapping()

        validate_required_columns(self.df, self.REQUIRED_COLUMNS)

        for col in ["code", "name", "type"]:
            if self.df[col].isna().any() or (self.df[col].astype(str).str.strip() == "").any():
                raise ValueError(f"Column '{col}' contains empty or missing values.")

        if self.df["code"].duplicated().any():
            duplicate_codes = self.df[self.df["code"].duplicated()]["code"].unique()
            raise ValueError(f"Duplicate institution codes found in file: {duplicate_codes}")
        
        if self.df["name"].duplicated().any():
            duplicate_names = self.df[self.df["name"].duplicated()]["name"].unique()
            raise ValueError(f"Duplicate institution names found in file: {duplicate_names}")

        invalid_types = self.df[~self.df["type"].isin(self.VALID_TYPES)]["type"].unique()
        if invalid_types.size > 0:
            raise ValueError(f"Invalid institution types found: {invalid_types}. Must be one of {self.VALID_TYPES}")

        self.df["country"] = self.df["country"].fillna("Kenya").replace("", "Kenya")
        self.df["website"] = self.df["website"].replace("", None).where(self.df["website"].notna(), None)

        logger.info("Validation passed.")

    def transform(self) -> None:
        self.records = []
        for row in self.df.itertuples(index=False):
            institution = Institution(
                code=row.code,
                name=row.name,
                slug=slugify(row.name),
                type=row.type,
                website=row.website,
                country=row.country,
            )
            self.records.append(institution)
        logger.info(f"Transformed {len(self.records)} rows into model instances.")

    def import_data(self) -> None:
        codes = [record.code for record in self.records]
        
        existing_institutions = Institution.objects.filter(code__in=codes)
        existing = {inst.code: inst for inst in existing_institutions}

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
                existing_record.name = record.name
                existing_record.slug = record.slug
                existing_record.type = record.type
                existing_record.website = record.website
                existing_record.country = record.country
                to_update.append(existing_record)

        if not self.dry_run:
            if to_create:
                Institution.objects.bulk_create(to_create, batch_size=self.batch_size)
            if to_update:
                Institution.objects.bulk_update(
                    to_update,
                    fields=["name", "slug", "type", "website", "country"],
                    batch_size=self.batch_size,
                )

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