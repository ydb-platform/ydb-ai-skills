ALTER TABLE documents
    ADD INDEX ft_idx GLOBAL USING fulltext_relevance
    ON (body) COVER (title)
    WITH (tokenizer=standard, use_filter_lowercase=true);
