PRAGMA ydb.KMeansTreeSearchTopSize = "10";

SELECT id, title, Knn::CosineDistance(embedding, $query_vector) AS score
FROM documents VIEW vec_idx
ORDER BY score ASC
LIMIT $limit;
