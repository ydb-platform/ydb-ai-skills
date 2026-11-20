CREATE TABLE documents (
    id Uint64 NOT NULL,
    title Utf8 NOT NULL,
    body Utf8 NOT NULL,
    embedding String NOT NULL,
    PRIMARY KEY (id)
);
