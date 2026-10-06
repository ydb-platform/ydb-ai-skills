UPSERT INTO documents (id, title, body, embedding)
SELECT id, title, body, embedding
FROM AS_TABLE($items);
