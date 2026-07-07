# careers/imports/import_result.py


from dataclasses import dataclass, field

@dataclass(slots=True)
class ImportResult:
    importer: str
    source: str

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)