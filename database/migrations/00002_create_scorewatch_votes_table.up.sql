CREATE TABLE scorewatch_votes (
    vote_id BIGSERIAL NOT NULL PRIMARY KEY,
    request_id BIGSERIAL NOT NULL,
    vote_user_id BIGINT NOT NULL,
    vote_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
