from django.core.management.base import BaseCommand
from django.db import transaction
from careers.models import Career, CareerTag


class Command(BaseCommand):
    help = "Seeds/updates CareerTag relationships with domain-appropriate taxonomy tags and weights."

    def add_arguments(self, parser):
        # Add dry-run flag
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the command execution without modifying the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.NOTICE("--- RUNNING IN DRY-RUN MODE ---"))
        # Mapping format:
        # "Career Title": [(tag_id, recommendation_weight), ...]
        #
        # Tag Reference (from taxonomy_tag table):
        # 1: Intro to Computer | 2: Math101 | 3: Literature101 | 4: IQ tests | 5: Science
        # 6: Biology | 7: Engineering | 9: Physics | 10: English | 12: Chemistry
        # 13: Geography | 14: History & Govt | 18: Agriculture | 19: Business Studies
        # 21: Art & Design | 22: Music | 23: French | 24: German
        mappings = {
            "Software Engineering": [(1, "0.90"), (2, "0.90"), (4, "0.80"), (7, "0.90"), (9, "0.80")],
            "DENTISTRY": [(5, "0.85"), (6, "0.90")],
            "Linguist & Cultural Specialist": [(3, "0.90"), (10, "0.85"), (23, "0.75"), (24, "0.75")],
            "IT Systems Administrator": [(1, "0.90"), (4, "0.80")],
            "Architect": [(2, "0.80"), (7, "0.85"), (21, "0.75")],
            "Quantity Surveyor": [(2, "0.80"), (7, "0.85"), (21, "0.75")],
            "Actuary": [(2, "0.90"), (19, "0.90")],
            "Industrial Chemist": [(5, "0.85"), (12, "0.95")],
            "Statistician / Quantitative Analyst": [(2, "0.90")],
            "Biotechnologist / Research Scientist": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Biological Sciences)": [(5, "0.85"), (6, "0.90")],
            "Computer Scientist": [(1, "0.90"), (2, "0.90"), (4, "0.80")],
            "Civil Engineer": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Electrical & Electronics Engineer": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Mechanical Engineer": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in": [(2, "0.80"), (5, "0.85")],
            "Specialist in (Bsc.)": [(2, "0.80"), (5, "0.85")],
            "Specialist in Bsc (Science)": [(2, "0.80"), (5, "0.85")],
            "Agricultural Officer / Agronomist": [(6, "0.80"), (18, "0.90")],
            "Specialist in (Biosystems Engineering)": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Food Science & Technology)": [(20, "0.90")],
            "Specialist in (Food Science And Technology)": [(20, "0.90")],
            "Specialist in Technology (Food Science And Technology)": [(20, "0.90")],
            "Pharmacist": [(5, "0.85"), (6, "0.90")],
            "Specialist in Biomedical Sciences & Technology": [(5, "0.85"), (6, "0.90")],
            "Medical Practitioner / Physician": [(2, "0.85"), (5, "0.90"), (6, "0.90"), (9, "0.95")],
            "Registered Nurse": [(5, "0.85"), (6, "0.90")],
            "Business Development Executive": [(19, "0.90")],
            "Legal Counsel / Advocate": [(10, "0.85"), (14, "0.90")],
            "High School / College Educator": [(3, "0.80"), (10, "0.85")],
            "Security & Criminology Expert": [(10, "0.85"), (14, "0.90")],
            "Social Worker / Psychologist": [(3, "0.80"), (10, "0.85")],
            "Economist": [(2, "0.90"), (19, "0.90")],
            "Specialist in (Information Science)": [(3, "0.80"), (10, "0.85")],
            "Specialist in Information Sciences": [(3, "0.80"), (10, "0.85")],
            "Hospitality & Tourism Manager": [(20, "0.90")],
            "Specialist in Information Communication Technology": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in (Information And Communication Techno...": [(3, "0.80"), (10, "0.90")],
            "Specialist in Technology In Information & Communica...": [(2, "0.80"), (5, "0.85")],
            "Creative Arts & Film Director": [(21, "0.95")],
            "Media & Public Relations Officer": [(3, "0.80"), (10, "0.90")],
            "Environmental Conservation Specialist": [(5, "0.80"), (13, "0.90")],
            "Specialist in (Horticulture)": [(6, "0.80"), (18, "0.90")],
            "Public Health Officer": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Biomedical Science And Technology)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Biomedical Science & Technology)": [(5, "0.85"), (6, "0.90")],
            "Specialist in Technology (Science Laboratory Techno...": [(5, "0.85"), (6, "0.90")],
            "Medical Laboratory Scientist": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Occupational Health & Safety)": [(5, "0.85"), (6, "0.90")],
            "Specialist in Occupational Therapy": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Manufacturing Engineering & Technology)": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Clothing Textile & Interior Design)": [(20, "0.90"), (21, "0.95")],
            "Specialist in (Fashion Design And Textile Technology)": [(20, "0.90"), (21, "0.95")],
            "Specialist in Textile Technology & Applied Fashion ...": [(20, "0.90"), (21, "0.95")],
            "Specialist in (Apparel & Fashion Technology)": [(20, "0.90"), (21, "0.95")],
            "Specialist in Library And Information Science": [(3, "0.80"), (10, "0.85")],
            "Specialist in In Information Science": [(3, "0.80"), (10, "0.85")],
            "Specialist in Library & Information Science": [(3, "0.80"), (10, "0.85")],
            "Specialist in Library And Information Studies": [(3, "0.80"), (10, "0.85")],
            "Supply Chain & Procurement Officer": [(19, "0.90")],
            "Animal Scientist / Marine Biologist": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Geography)": [(5, "0.80"), (13, "0.90")],
            "Specialist in Development Studies": [(3, "0.80"), (10, "0.85")],
            "Specialist in (Applied Aquatic Science)": [(5, "0.85"), (6, "0.90"), (18, "0.90")],
            "Mining & Petroleum Engineer": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Financial Engineering)": [(2, "0.90"), (7, "0.90"), (9, "0.80"), (19, "0.90")],
            "Physicist / Meteorologist": [(2, "0.85"), (5, "0.90"), (9, "0.95")],
            "Specialist in (Sugar And Agro Processing Technology)": [(6, "0.80"), (18, "0.90")],
            "Specialist in Applied Computing": [(1, "0.90"), (4, "0.80")],
            "Data Scientist / Analyst": [(2, "0.90")],
            "Specialist in (Informatics)": [(1, "0.90"), (4, "0.80")],
            "Specialist in Theology": [(10, "0.80"), (15, "0.90")],
            "Specialist in Theology In Pastoral Studies": [(5, "0.85"), (6, "0.90"), (10, "0.80"), (15, "0.90")],
            "Specialist in (Communication And Public Relations)": [(3, "0.80"), (10, "0.90")],
            "Specialist in (Paramedic Science)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Physiotherapy)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Soil Science)": [(6, "0.80"), (18, "0.90")],
            "Specialist in (Spatial Planning": [(2, "0.80"), (5, "0.80"), (7, "0.85"), (13, "0.90"), (21, "0.75")],
            "Specialist in (Graphic, Communication And Advertising)": [(3, "0.80"), (10, "0.90"), (21, "0.95")],
            "Specialist in (Renewable Energy)": [(5, "0.85"), (7, "0.80"), (18, "0.75")],
            "Specialist in Technology In Medical Engineering": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in Technology In Marine Engineering": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Financial Analyst": [(2, "0.90"), (19, "0.90")],
            "Software Engineer": [(1, "0.90"), (2, "0.90"), (4, "0.80"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Health Records And Informatics)": [(1, "0.90"), (4, "0.80"), (5, "0.85"), (6, "0.90")],
            "Specialist in (Health Records & Information Mgt.)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Forensic Science)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Optometry And Vision Sciences)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Medical Engineering)": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Biomedical Engineering)": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in Telecommunication": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in (Geospatial Information Science)": [(3, "0.80"), (5, "0.80"), (10, "0.85"), (13, "0.90")],
            "Specialist in Geospatial Information Science And Re...": [(3, "0.80"), (5, "0.80"), (10, "0.85"), (13, "0.90")],
            "Specialist in (Climate Change Adaptation And Sustai...": [(5, "0.80"), (13, "0.90")],
            "Specialist in ( Sustainable Energy & Climate Change...": [(5, "0.85"), (7, "0.80"), (13, "0.90"), (18, "0.75")],
            "Specialist in Geoinformatics": [(1, "0.90"), (4, "0.80"), (5, "0.80"), (13, "0.90")],
            "Specialist in (Geomatic Engineering)": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in Applied Communication": [(3, "0.80"), (10, "0.90")],
            "Specialist in Computer Systems Engineering": [(1, "0.90"), (2, "0.90"), (4, "0.80"), (7, "0.90"), (9, "0.80")],
            "Specialist in Technology In Building Construction": [(2, "0.85"), (7, "0.90"), (9, "0.80"), (21, "0.75")],
            "Specialist in Technology (Building Construction)": [(2, "0.85"), (7, "0.90"), (9, "0.80"), (21, "0.75")],
            "Specialist in Laboratory Sciences": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Laboratory Science And Technology)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Health Promotion And Sports Science)": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Health Promotion)": [(5, "0.85"), (6, "0.90")],
            "Specialist in Technology (Telecommunication And Inf...": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in (Renewable Energy Technology)": [(5, "0.85"), (7, "0.80"), (18, "0.75")],
            "Specialist in Renewable Energy And Technology": [(5, "0.85"), (7, "0.80"), (18, "0.75")],
            "Specialist in Networks And Communication Systems": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in Public Policy And Administration": [(10, "0.85"), (14, "0.90")],
            "Specialist in Engineering (Geospatial Engineering)": [(2, "0.85"), (5, "0.80"), (7, "0.90"), (9, "0.80"), (13, "0.90")],
            "Specialist in (Geospatial Engineering)": [(2, "0.85"), (5, "0.80"), (7, "0.90"), (9, "0.80"), (13, "0.90")],
            "Specialist in (Marine Engineering)": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Crop Protection)": [(6, "0.80"), (18, "0.90")],
            "Specialist in (Microprocessor Technology And Instru...": [(2, "0.85"), (5, "0.90"), (6, "0.80"), (9, "0.95"), (18, "0.90")],
            "Specialist in (Telecommunication And Information En...": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in (Telecommunication & Inform. Tech)": [(1, "0.90"), (3, "0.80"), (4, "0.80"), (10, "0.90")],
            "Specialist in Justice And Peace": [(10, "0.85"), (14, "0.90")],
            "Specialist in Applied Optics And Lasers": [(2, "0.85"), (5, "0.90"), (9, "0.95")],
            "Specialist in Ba In Biblical Studies": [(10, "0.80"), (15, "0.90")],
            "Specialist in Engineering (Aeronautical Engineering)": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in Real Estate": [(19, "0.90")],
            "Specialist in (Land Administration)": [(5, "0.80"), (13, "0.90")],
            "Specialist in Automotive Technology": [(2, "0.80"), (5, "0.85")],
            "Mechatronics Automation Engineer": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Seed Science & Technology": [(6, "0.80"), (18, "0.90")],
            "Specialist in Dental Technology": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Geology)": [(5, "0.80"), (13, "0.90")],
            "Specialist in Technology (Chemical Engineering)": [(2, "0.85"), (5, "0.85"), (7, "0.90"), (9, "0.80"), (12, "0.95")],
            "Specialist in (Exercise & Sport Science)": [(2, "0.80"), (5, "0.85")],
            "Specialist in Technology (Communication And Compute...": [(3, "0.80"), (10, "0.90")],
            "Specialist in Urban And Regional Planning": [(2, "0.80"), (7, "0.85"), (21, "0.75")],
            "Specialist in Applied Science (Geo-Informatics)": [(1, "0.90"), (4, "0.80"), (5, "0.80"), (13, "0.90")],
            "Specialist in Computer Technology": [(1, "0.90"), (2, "0.90"), (4, "0.80")],
            "Specialist in (Urban Design And Development)": [(2, "0.80"), (7, "0.85"), (21, "0.95")],
            "Specialist in (Physical Therapy)": [(2, "0.85"), (5, "0.90"), (6, "0.90"), (9, "0.95")],
            "Specialist in Ba In Inter-Cultural Studies": [(10, "0.80"), (15, "0.90")],
            "Specialist in Leather Technology": [(6, "0.80"), (18, "0.90")],
            "Public Administration Specialist": [(10, "0.85"), (14, "0.90")],
            "Specialist in (Renewable Energy And Biofuels Techno...": [(5, "0.85"), (7, "0.80"), (18, "0.75")],
            "Specialist in Radiography": [(5, "0.85"), (6, "0.90")],
            "Specialist in Biomedical Science": [(5, "0.85"), (6, "0.90")],
            "Specialist in Technology (Office Administration And...": [(19, "0.90")],
            "Specialist in Laboratory Technology": [(5, "0.85"), (6, "0.90")],
            "Specialist in Technology (Design)": [(21, "0.95")],
            "Specialist in Engineering (Chemical And Process Eng...": [(2, "0.85"), (5, "0.85"), (7, "0.90"), (9, "0.80"), (12, "0.95")],
            "Specialist in Engineering (Chemical Engineering)": [(2, "0.85"), (5, "0.85"), (7, "0.90"), (9, "0.80"), (12, "0.95")],
            "Specialist in Genomic Science": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Control And Instrumentation)": [(2, "0.80"), (5, "0.85")],
            "Specialist in Oral Health": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Crop Improvement & Protection)": [(6, "0.80"), (18, "0.90")],
            "Specialist in (Applied Bioengineering)": [(2, "0.85"), (5, "0.85"), (6, "0.90"), (7, "0.90"), (9, "0.80")],
            "Specialist in Midwifery": [(5, "0.85"), (6, "0.90")],
            "Specialist in (Operations Research)": [(2, "0.90")],
            "Specialist in Engineering (Manufacturing, Industria...": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Nutraceutical Science And Technology)": [(20, "0.90")],
            "Specialist in (Aerospace Engineering)": [(2, "0.85"), (7, "0.90"), (9, "0.80")],
            "Specialist in (Wood Science And Industrial Processes)": [(6, "0.80"), (18, "0.90")],
            "Specialist in (Instrumentation & Control)": [(2, "0.80"), (5, "0.85")],
            "Specialist in Communication & Public Relations": [(3, "0.80"), (10, "0.90")],
            "Accountant / Auditor": [(2, "0.90"), (19, "0.90")],
        }
        created_count = 0
        updated_count = 0
        missing_careers = []

        with transaction.atomic():
            for title, tag_weights in mappings.items():
                try:
                    career = Career.objects.get(title=title)
                except Career.DoesNotExist:
                    missing_careers.append(title)
                    continue

                for tag_id, weight in tag_weights:
                    if not dry_run:
                        obj, created = CareerTag.objects.update_or_create(
                            career=career,
                            tag_id=tag_id,
                            defaults={"recommendation_weight": weight},
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        # Simulate lookup in dry-run mode
                        if CareerTag.objects.filter(career=career, tag_id=tag_id).exists():
                            updated_count += 1
                        else:
                            created_count += 1

            if dry_run:
                # Force rollback in dry-run mode to prevent any accidental persistence
                transaction.set_rollback(True)

        # Output Summary
        action_verb = "Would process" if dry_run else "Successfully processed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action_verb} career tags: {created_count} created, {updated_count} updated."
            )
        )

        if missing_careers:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped missing careers ({len(missing_careers)}): {', '.join(missing_careers)}"
                )
            )