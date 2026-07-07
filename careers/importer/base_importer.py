"""
base_importer.py

Abstract base class for all data importers.

Import Lifecycle

    run()
        │
        ├── read()
        ├── validate()
        ├── transform()
        ├── import_data()
        └── report()

Each concrete importer should only implement the model-specific logic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from django.db import transaction

from .general_utils import (
    dataframe_summary,
    ensure_not_empty,
    normalize_columns,
    read_source,
    remove_duplicate_rows,
    replace_nan,
    strip_whitespace,
)

from .import_result import ImportResult

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """
    Base class for all importers.

    Concrete subclasses must implement:

        validate()
        transform()
        import_data()

    Example

        class InstitutionImporter(BaseImporter):
            ...
    """

    REQUIRED_COLUMNS: tuple[str, ...] = ()

    def __init__(
        self,
        source: Path,
        *,
        dry_run: bool = False,
        update: bool = False,
        batch_size: int = 1000,
    ) -> None:

        self.source = Path(source)

        self.dry_run = dry_run
        self.update = update
        self.batch_size = batch_size

        self.df: pd.DataFrame | None = None

        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0

        self.errors: list[str] = []
        self.warnings: list[str] = []

        self.records = []

    # ===================================================================
    # Public API
    # ===================================================================

    def run(self) -> ImportResult:
        """
        Executes the complete import lifecycle.
        """

        logger.info("=" * 70)
        logger.info("%s started.", self.__class__.__name__)
        logger.info("=" * 70)

        self.read()

        self.validate()

        self.transform()

        if not self.dry_run:

            with transaction.atomic():
                self.import_data()

        else:

            logger.info("Dry-run enabled. Database changes skipped.")

        logger.info("%s completed.", self.__class__.__name__)

        return self.report()

    # ===================================================================
    # Reading
    # ===================================================================

    def read(self) -> None:
        """
        Reads and prepares the dataframe.
        """

        df = read_source(self.source)

        if df is None:
            raise RuntimeError("Unable to read import source.")

        df = normalize_columns(df)

        df = strip_whitespace(df)

        df = remove_duplicate_rows(df)

        df = replace_nan(df)

        if not ensure_not_empty(df):
            raise RuntimeError("Import file contains no records.")

        dataframe_summary(df)

        self.df = df

    # ===================================================================
    # Validation
    # ===================================================================

    @abstractmethod
    def validate(self) -> None:
        """
        Validate dataframe.

        Raise ValueError if validation fails.
        """
        ...

    # ===================================================================
    # Transformation
    # ===================================================================

    @abstractmethod
    def transform(self) -> None:
        """
        Convert dataframe rows into model instances.
        """
        ...

    # ===================================================================
    # Import
    # ===================================================================

    @abstractmethod
    def import_data(self) -> None:
        """
        Persist transformed records.
        """
        ...

    # ===================================================================
    # Reporting
    # ===================================================================

    def report(self) -> ImportResult:
        """
        Returns import statistics.
        """

        return ImportResult(
            importer=self.__class__.__name__,
            source=str(self.source),
            created=self.created,
            updated=self.updated,
            skipped=self.skipped,
            failed=self.failed,
            warnings=self.warnings,
            errors=self.errors,
        )

    # ===================================================================
    # Helpers
    # ===================================================================

    def warning(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)

    def error(self, message: str) -> None:
        logger.error(message)
        self.errors.append(message)

    def fail(self, message: str) -> None:
        """
        Register a failed record.
        """
        self.failed += 1
        self.error(message)

    def success_create(self) -> None:
        self.created += 1

    def success_update(self) -> None:
        self.updated += 1

    def success_skip(self) -> None:
        self.skipped += 1