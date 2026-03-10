"""initial schema

Revision ID: 20260308_0001
Revises:
Create Date: 2026-03-08 18:50:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260308_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_system", sa.String(), nullable=True),
        sa.Column("order_number", sa.String(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=False)

    op.create_table(
        "trackings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tracking_number", sa.String(), nullable=False),
        sa.Column("current_status", sa.String(), nullable=False),
        sa.Column("current_status_detail", sa.String(), nullable=True),
        sa.Column("current_status_code", sa.String(), nullable=True),
        sa.Column("last_event_time", sa.DateTime(), nullable=True),
        sa.Column("last_event_desc", sa.String(), nullable=True),
        sa.Column("last_event_location", sa.String(), nullable=True),
        sa.Column("last_opcode", sa.String(), nullable=True),
        sa.Column("last_queried_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_message", sa.String(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_number"),
    )
    op.create_index("ix_trackings_tracking_number", "trackings", ["tracking_number"], unique=False)

    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_data", sa.JSON(), nullable=True),
        sa.Column("column_mapping", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "column_mapping_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_hint", sa.String(), nullable=True),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("key_fields", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("test_result", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "status_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("carrier_code", sa.String(), nullable=False),
        sa.Column("opcode", sa.String(), nullable=True),
        sa.Column("first_status_code", sa.String(), nullable=True),
        sa.Column("secondary_status_code", sa.String(), nullable=True),
        sa.Column("mapped_status", sa.String(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_status_mappings_carrier_code", "status_mappings", ["carrier_code"], unique=False)
    op.create_index("ix_status_mappings_opcode", "status_mappings", ["opcode"], unique=False)
    op.create_index("ix_status_mappings_first_status_code", "status_mappings", ["first_status_code"], unique=False)
    op.create_index("ix_status_mappings_secondary_status_code", "status_mappings", ["secondary_status_code"], unique=False)
    op.create_index("ix_status_mappings_mapped_status", "status_mappings", ["mapped_status"], unique=False)

    op.create_table(
        "polling_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("total_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "order_trackings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("tracking_id", sa.Integer(), nullable=False),
        sa.Column("linked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["tracking_id"], ["trackings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "tracking_id"),
    )
    op.create_index("ix_order_trackings_order_id", "order_trackings", ["order_id"], unique=False)
    op.create_index("ix_order_trackings_tracking_id", "order_trackings", ["tracking_id"], unique=False)

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tracking_id", sa.Integer(), nullable=False),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("event_location", sa.String(), nullable=True),
        sa.Column("opcode", sa.String(), nullable=True),
        sa.Column("first_status_code", sa.String(), nullable=True),
        sa.Column("secondary_status_code", sa.String(), nullable=True),
        sa.Column("first_status_name", sa.String(), nullable=True),
        sa.Column("secondary_status_name", sa.String(), nullable=True),
        sa.Column("event_desc", sa.String(), nullable=True),
        sa.Column("mapped_status", sa.String(), nullable=True),
        sa.Column("raw_event_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tracking_id"], ["trackings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_id", "event_time", "opcode", "event_desc"),
    )
    op.create_index("ix_tracking_events_tracking_id", "tracking_events", ["tracking_id"], unique=False)
    op.create_index("ix_tracking_events_event_time", "tracking_events", ["event_time"], unique=False)
    op.create_index("ix_tracking_events_mapped_status", "tracking_events", ["mapped_status"], unique=False)

    op.create_table(
        "upload_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("upload_batch_id", sa.String(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_errors_upload_batch_id", "upload_errors", ["upload_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_upload_errors_upload_batch_id", table_name="upload_errors")
    op.drop_table("upload_errors")
    op.drop_index("ix_tracking_events_mapped_status", table_name="tracking_events")
    op.drop_index("ix_tracking_events_event_time", table_name="tracking_events")
    op.drop_index("ix_tracking_events_tracking_id", table_name="tracking_events")
    op.drop_table("tracking_events")
    op.drop_index("ix_order_trackings_tracking_id", table_name="order_trackings")
    op.drop_index("ix_order_trackings_order_id", table_name="order_trackings")
    op.drop_table("order_trackings")
    op.drop_table("polling_runs")
    op.drop_index("ix_status_mappings_mapped_status", table_name="status_mappings")
    op.drop_index("ix_status_mappings_secondary_status_code", table_name="status_mappings")
    op.drop_index("ix_status_mappings_first_status_code", table_name="status_mappings")
    op.drop_index("ix_status_mappings_opcode", table_name="status_mappings")
    op.drop_index("ix_status_mappings_carrier_code", table_name="status_mappings")
    op.drop_table("status_mappings")
    op.drop_table("api_keys")
    op.drop_table("column_mapping_presets")
    op.drop_table("upload_batches")
    op.drop_index("ix_trackings_tracking_number", table_name="trackings")
    op.drop_table("trackings")
    op.drop_index("ix_orders_order_number", table_name="orders")
    op.drop_table("orders")
