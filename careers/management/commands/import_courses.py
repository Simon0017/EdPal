# careers/management/commands/import_courses.py
# python manage.py import_courses data/courses.xlsx --update

import os
from django.core.management.base import BaseCommand, CommandError
from careers.importer.course_importer import CourseImporter


class Command(BaseCommand):
    help = "Production-grade ETL engine to import system Course master reference data files."

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            type=str,
            help="Path to the source data file (CSV or Excel formats supported).",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            dest="update",
            default=False,
            help="Modify and overwrite existing entries in the database when unique codes overlap.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            default=False,
            help="Simulate file reading, validations, and transformation sequences without writing mutations to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            dest="batch_size",
            default=500,
            help="The maximum capacity boundary allocated per individual multi-row transactional DB batch insert/update statement.",
        )

    def handle(self, *args, **options):
        source_path = options["source"]

        if not os.path.exists(source_path):
            raise CommandError(f"Target data source file locator path could not be found: '{source_path}'")

        self.stdout.write(self.style.WARNING(f"Initializing parsing sequence for target: {source_path}..."))

        try:
            importer = CourseImporter(
                file_path=source_path,
                update=options["update"],
                dry_run=options["dry_run"],
                batch_size=options["batch_size"],
            )
            
            result = importer.run()

            self.stdout.write(self.style.SUCCESS("\n--- Import Operation Complete Summary ---"))
            self.stdout.write(f"Created Reference Nodes: {result.created}")
            self.stdout.write(f"Updated Reference Nodes: {result.updated}")
            self.stdout.write(f"Skipped Reference Nodes: {result.skipped}")
            self.stdout.write(f"Failed Reference Nodes:  {result.failed}")
            
            if result.warnings:
                self.stdout.write(self.style.WARNING(f"Logged Operational Pipeline Warnings ({len(result.warnings)})"))
                
        except Exception as err:
            raise CommandError(f"Critical execution error encountered during ETL processing layout step: {err}")