from app.db.models import ApiKey, AuditLog, Base, Job, User


def test_table_names():
    assert User.__tablename__ == "users"
    assert ApiKey.__tablename__ == "api_keys"
    assert Job.__tablename__ == "jobs"
    assert AuditLog.__tablename__ == "audit_log"


def test_user_columns_present():
    cols = {c.name for c in User.__table__.columns}
    assert {"id", "username", "email", "password_hash", "role", "status", "deleted_at",
            "created_at", "updated_at"} <= cols


def test_job_columns_present():
    cols = {c.name for c in Job.__table__.columns}
    assert {"id", "user_id", "api_key_id", "original_filename", "file_size_bytes", "mime_type",
            "s3_input_uri", "s3_output_prefix", "bda_invocation_arn", "matched_blueprint",
            "pages_processed", "blueprint_field_count", "cost_usd", "status", "error_code",
            "error_message", "extracted_fields", "raw_bda_output", "created_at",
            "started_at", "completed_at", "duration_ms"} <= cols


def test_metadata_has_all_tables():
    assert {"users", "api_keys", "jobs", "audit_log"} <= set(Base.metadata.tables.keys())
