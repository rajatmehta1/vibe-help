"""initial_schema

Revision ID: fb894aaee630
Revises:
Create Date: 2026-02-28 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "fb894aaee630"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Enum types
    org_role = sa.Enum("owner", "admin", "member", name="org_role")
    policy_category = sa.Enum(
        "security", "naming", "architecture", "error_handling",
        "dependencies", "performance", "documentation", "custom",
        name="policy_category",
    )
    severity_level = sa.Enum("error", "warning", "info", name="severity_level")
    scan_type = sa.Enum("realtime", "file", "workspace", name="scan_type")
    scan_status = sa.Enum("pending", "running", "completed", "failed", name="scan_status")
    audit_action = sa.Enum(
        "code_detected", "scan_started", "scan_completed",
        "policy_created", "policy_updated", "index_started", "index_completed",
        name="audit_action",
    )
    indexing_job_type = sa.Enum("full", "incremental", name="indexing_job_type")
    code_unit_type = sa.Enum("function", "class", "module", "file", name="code_unit_type")

    org_role.create(op.get_bind(), checkfirst=True)
    policy_category.create(op.get_bind(), checkfirst=True)
    severity_level.create(op.get_bind(), checkfirst=True)
    scan_type.create(op.get_bind(), checkfirst=True)
    scan_status.create(op.get_bind(), checkfirst=True)
    audit_action.create(op.get_bind(), checkfirst=True)
    indexing_job_type.create(op.get_bind(), checkfirst=True)
    code_unit_type.create(op.get_bind(), checkfirst=True)

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
        sa.Column("role", sa.Enum("owner", "admin", "member", name="org_role", create_type=False), nullable=False),
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
        sa.Column("settings", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.Column("category", sa.Enum("security", "naming", "architecture", "error_handling", "dependencies", "performance", "documentation", "custom", name="policy_category", create_type=False), nullable=False),
        sa.Column("default_severity", sa.Enum("error", "warning", "info", name="severity_level", create_type=False), nullable=False),
        sa.Column("default_configuration", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.Column("category", sa.Enum("security", "naming", "architecture", "error_handling", "dependencies", "performance", "documentation", "custom", name="policy_category", create_type=False), nullable=False),
        sa.Column("severity_default", sa.Enum("error", "warning", "info", name="severity_level", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("configuration", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.Column("scan_type", sa.Enum("realtime", "file", "workspace", name="scan_type", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", name="scan_status", create_type=False), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("trigger_source", sa.String(50), nullable=False),
        sa.Column("total_violations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_scans"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_scans_project_id_projects", ondelete="CASCADE"),
    )

    # violations
    op.create_table(
        "violations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scan_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("severity", sa.Enum("error", "warning", "info", name="severity_level", create_type=False), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("column_start", sa.Integer(), nullable=False),
        sa.Column("column_end", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("context_evidence", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("auto_fix", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.Column("action", sa.Enum("code_detected", "scan_started", "scan_completed", "policy_created", "policy_updated", "index_started", "index_completed", name="audit_action", create_type=False), nullable=False),
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", name="scan_status", create_type=False), nullable=False),
        sa.Column("job_type", sa.Enum("full", "incremental", name="indexing_job_type", create_type=False), nullable=False),
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
        sa.Column("code_unit_type", sa.Enum("function", "class", "module", "file", name="code_unit_type", create_type=False), nullable=False),
        sa.Column("code_unit_name", sa.String(512), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
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

    sa.Enum(name="code_unit_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="indexing_job_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scan_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scan_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="severity_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="policy_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="org_role").drop(op.get_bind(), checkfirst=True)

    op.execute("DROP EXTENSION IF EXISTS vector")
