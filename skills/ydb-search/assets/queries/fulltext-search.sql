SELECT id, title,
       FulltextScore(body, $query_text, "Or" AS DefaultOperator) AS score
FROM documents VIEW ft_idx
WHERE FulltextScore(body, $query_text, "Or" AS DefaultOperator) > 0
ORDER BY score DESC
LIMIT $limit;
