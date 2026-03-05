"""initial_schema

Revision ID: fb894aaee630
Revises:
Create Date: 2026-02-28 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fb894aaee630"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum types once, with create_type=False so they are never auto-created by create_table
org_role = postgresql.ENUM("owner", "admin", "member", name="org_role", create_type=False)
policy_category = postgresql.ENUM("security", "naming", "architecture", "error_handling", "dependencies", "performance", "documentation", "custom", name="policy_category", create_type=False)
severity_level = postgresql.ENUM("error", "warning", "info", name="severity_level", create_type=False)
scan_type = postgresql.ENUM("realtime", "file", "workspace", name="scan_type", create_type=False)
scan_status = postgresql.ENUM("pending", "running", "completed", "failed", name="scan_status", create_type=False)
audit_action = postgresql.ENUM("code_detected", "scan_started", "scan_completed", "policy_created", "policy_updated", "index_started", "index_completed", name="audit_action", create_type=False)
indexing_job_type = postgresql.ENUM("full", "incremental", name="indexing_job_type", create_type=False)
code_unit_type = postgresql.ENUM("function", "class", "module", "file", name="code_unit_type", create_type=False)


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Enum types (created via raw SQL to avoid SQLAlchemy double-creation)
    op.execute("CREATE TYPE org_role AS ENUM ('owner', 'admin', 'member')")
    op.execute("CREATE TYPE policy_category AS ENUM ('security', 'naming', 'architecture', 'error_handling', 'dependencies', 'performance', 'documentation', 'custom')")
    op.execute("CREATE TYPE severity_level AS ENUM ('error', 'warning', 'info')")
    op.execute("CREATE TYPE scan_type AS ENUM ('realtime', 'file', 'workspace')")
    op.execute("CREATE TYPE scan_status AS ENUM ('pending', 'running', 'completed', 'failed')")
    op.execute("CREATE TYPE audit_action AS ENUM ('code_detected', 'scan_started', 'scan_completed', 'policy_created', 'policy_updated', 'index_started', 'index_completed')")
    op.execute("CREATE TYPE indexing_job_type AS ENUM ('full', 'incremental')")
    op.execute("CREATE TYPE code_unit_type AS ENUM ('function', 'class', 'module', 'file')")

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(1024), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_email", "users", ["email"], unique=True)

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_index("ix_slug", "organizations", ["slug"], unique=True)

    # user_organizations
    op.create_table(
        "user_organizations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("role", org_role, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "org_id", name="pk_user_organizations"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_organizations_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_user_organizations_org_id_organizations", ondelete="CASCADE"),
    )

    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("root_path", sa.String(1024), nullable=True),
        sa.Column("primary_language", sa.String(50), nullable=True),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_projects_org_id_organizations", ondelete="CASCADE"),
    )

    # policy_templates
    op.create_table(
        "policy_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", policy_category, nullable=False),
        sa.Column("default_severity", severity_level, nullable=False),
        sa.Column("default_configuration", postgresql.JSONB(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policy_templates"),
    )
    op.create_index("ix_policy_templates_slug", "policy_templates", ["slug"], unique=True)

    # policies
    op.create_table(
        "policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("policy_template_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", policy_category, nullable=False),
        sa.Column("severity_default", severity_level, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("configuration", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policies"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_policies_project_id_projects", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_template_id"], ["policy_templates.id"], name="fk_policies_policy_template_id_policy_templates", ondelete="SET NULL"),
    )

    # scans
    op.create_table(
        "scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("scan_type", scan_type, nullable=False),
        sa.Column("status", scan_status, nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("trigger_source", sa.String(50), nullable=False),
        sa.Column("total_violations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_scans"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_scans_project_id_projects", ondelete="CASCADE"),
    )

    # violations
    op.create_table(
        "violations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scan_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("severity", severity_level, nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("column_start", sa.Integer(), nullable=False),
        sa.Column("column_end", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("context_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("auto_fix", postgresql.JSONB(), nullable=True),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_violations"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_violations_scan_id_scans", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], name="fk_violations_policy_id_policies", ondelete="CASCADE"),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_audit_logs_project_id_projects", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id_users", ondelete="SET NULL"),
    )

    # indexing_jobs
    op.create_table(
        "indexing_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("status", scan_status, nullable=False),
        sa.Column("job_type", indexing_job_type, nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_files", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_indexing_jobs"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_indexing_jobs_project_id_projects", ondelete="CASCADE"),
    )

    # code_embeddings
    op.create_table(
        "code_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("code_unit_type", code_unit_type, nullable=False),
        sa.Column("code_unit_name", sa.String(512), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_code_embeddings"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_code_embeddings_project_id_projects", ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("code_embeddings")
    op.drop_table("indexing_jobs")
    op.drop_table("audit_logs")
    op.drop_table("violations")
    op.drop_table("scans")
    op.drop_table("policies")
    op.drop_table("policy_templates")
    op.drop_table("projects")
    op.drop_table("user_organizations")
    op.drop_table("organizations")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS code_unit_type")
    op.execute("DROP TYPE IF EXISTS indexing_job_type")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS scan_status")
    op.execute("DROP TYPE IF EXISTS scan_type")
    op.execute("DROP TYPE IF EXISTS severity_level")
    op.execute("DROP TYPE IF EXISTS policy_category")
    op.execute("DROP TYPE IF EXISTS org_role")

    op.execute("DROP EXTENSION IF EXISTS vector")
