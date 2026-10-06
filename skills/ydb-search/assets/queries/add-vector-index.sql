ALTER TABLE documents
    ADD INDEX vec_idx GLOBAL USING vector_kmeans_tree
    ON (embedding) COVER (embedding, title)
    WITH (distance=cosine, vector_type="float", vector_dimension=3,
          clusters=2, levels=1);
