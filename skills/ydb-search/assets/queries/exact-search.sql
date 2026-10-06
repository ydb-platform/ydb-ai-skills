SELECT id, title, Knn::CosineDistance(embedding, $query_vector) AS score
FROM documents
ORDER BY score ASC
LIMIT $limit;
