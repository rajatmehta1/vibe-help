import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import PolicyTemplate
from app.models.enums import PolicyCategory, SeverityLevel

BUILTIN_TEMPLATES = [
    {
        "slug": "security-owasp-basics",
        "name": "OWASP Security Basics",
        "description": "Checks for common OWASP Top 10 vulnerabilities in AI-generated code.",
        "category": PolicyCategory.SECURITY,
        "default_severity": SeverityLevel.ERROR,
        "default_configuration": {
            "rules": [
                {"id": "SEC-001", "name": "sql_injection_detection", "enabled": True, "type": "static"},
                {"id": "SEC-002", "name": "xss_prevention", "enabled": True, "type": "static"},
                {"id": "SEC-003", "name": "hardcoded_secrets", "enabled": True, "type": "static"},
                {"id": "SEC-004", "name": "insecure_deserialization", "enabled": True, "type": "learned"},
                {"id": "SEC-005", "name": "broken_auth_patterns", "enabled": True, "type": "learned"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "naming-conventions",
        "name": "Naming Conventions",
        "description": "Enforces consistent naming patterns across AI-generated code.",
        "category": PolicyCategory.NAMING,
        "default_severity": SeverityLevel.WARNING,
        "default_configuration": {
            "rules": [
                {"id": "NAM-001", "name": "snake_case_functions", "enabled": True, "type": "static"},
                {"id": "NAM-002", "name": "pascal_case_classes", "enabled": True, "type": "static"},
                {"id": "NAM-003", "name": "descriptive_variable_names", "enabled": True, "type": "learned"},
                {"id": "NAM-004", "name": "no_single_letter_vars", "enabled": True, "type": "static"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "architecture-layered",
        "name": "Layered Architecture",
        "description": "Validates that AI-generated code respects architectural layer boundaries.",
        "category": PolicyCategory.ARCHITECTURE,
        "default_severity": SeverityLevel.WARNING,
        "default_configuration": {
            "rules": [
                {"id": "ARC-001", "name": "no_circular_imports", "enabled": True, "type": "static"},
                {"id": "ARC-002", "name": "layer_boundary_respect", "enabled": True, "type": "learned"},
                {"id": "ARC-003", "name": "dependency_direction", "enabled": True, "type": "static"},
                {"id": "ARC-004", "name": "separation_of_concerns", "enabled": True, "type": "learned"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "error-handling-consistency",
        "name": "Error Handling Consistency",
        "description": "Ensures AI-generated code uses consistent error handling patterns.",
        "category": PolicyCategory.ERROR_HANDLING,
        "default_severity": SeverityLevel.WARNING,
        "default_configuration": {
            "rules": [
                {"id": "ERR-001", "name": "no_bare_except", "enabled": True, "type": "static"},
                {"id": "ERR-002", "name": "consistent_error_types", "enabled": True, "type": "learned"},
                {"id": "ERR-003", "name": "error_logging_required", "enabled": True, "type": "static"},
                {"id": "ERR-004", "name": "no_swallowed_exceptions", "enabled": True, "type": "static"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "dependency-safety",
        "name": "Dependency Safety",
        "description": "Validates that AI-generated code does not introduce unsafe dependencies.",
        "category": PolicyCategory.DEPENDENCIES,
        "default_severity": SeverityLevel.ERROR,
        "default_configuration": {
            "rules": [
                {"id": "DEP-001", "name": "no_deprecated_packages", "enabled": True, "type": "static"},
                {"id": "DEP-002", "name": "version_pinning_required", "enabled": True, "type": "static"},
                {"id": "DEP-003", "name": "license_compatibility", "enabled": True, "type": "learned"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "performance-basics",
        "name": "Performance Basics",
        "description": "Detects common performance anti-patterns in AI-generated code.",
        "category": PolicyCategory.PERFORMANCE,
        "default_severity": SeverityLevel.INFO,
        "default_configuration": {
            "rules": [
                {"id": "PRF-001", "name": "n_plus_one_query", "enabled": True, "type": "learned"},
                {"id": "PRF-002", "name": "unnecessary_recomputation", "enabled": True, "type": "learned"},
                {"id": "PRF-003", "name": "large_payload_warning", "enabled": True, "type": "static"},
            ]
        },
        "version": "1.0.0",
    },
    {
        "slug": "documentation-required",
        "name": "Documentation Required",
        "description": "Ensures AI-generated code includes proper documentation.",
        "category": PolicyCategory.DOCUMENTATION,
        "default_severity": SeverityLevel.INFO,
        "default_configuration": {
            "rules": [
                {"id": "DOC-001", "name": "public_function_docstring", "enabled": True, "type": "static"},
                {"id": "DOC-002", "name": "module_docstring", "enabled": True, "type": "static"},
                {"id": "DOC-003", "name": "complex_logic_comments", "enabled": True, "type": "learned"},
            ]
        },
        "version": "1.0.0",
    },
]


async def seed_builtin_templates(db: AsyncSession) -> None:
    for tmpl_data in BUILTIN_TEMPLATES:
        result = await db.execute(
            select(PolicyTemplate).where(PolicyTemplate.slug == tmpl_data["slug"])
        )
        if result.scalar_one_or_none() is None:
            template = PolicyTemplate(id=uuid.uuid4(), is_builtin=True, **tmpl_data)
            db.add(template)
    await db.commit()
