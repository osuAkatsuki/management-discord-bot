CREATE TABLE scorewatch_requests (
    request_id BIGSERIAL NOT NULL PRIMARY KEY,
    requested_by BIGINT NOT NULL,
    score_id BIGINT UNIQUE NOT NULL,
    score_relax INTEGER NOT NULL,
    request_status TEXT NOT NULL,
    thread_message_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
