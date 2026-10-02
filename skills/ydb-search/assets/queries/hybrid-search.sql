PRAGMA ydb.KMeansTreeSearchTopSize = "10";

SELECT id, title
FROM documents
ORDER BY HybridRank(
    FulltextScore(body, $query_text, "Or" AS DefaultOperator),
    Knn::CosineDistance(embedding, $query_vector),
    ("ft_idx", "vec_idx") AS Indexes,
    (100, 200) AS Limits)
LIMIT $limit;
