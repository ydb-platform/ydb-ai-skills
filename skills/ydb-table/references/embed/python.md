# FloatVector parameters in Python (`ydb`)

For an application-provided `list[float]`, follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (Python tab) to serialize it on the client. Bind the result as YQL `String`, including for a stored embedding column or an `AS_TABLE` batch member. Avoid passing `List<Float>` and calling `Knn::ToBinaryStringFloat` in YQL when the vector already exists in Python. The YQL conversion remains useful for vectors constructed inside YQL.

For Python SDK **3.33.1 or later**, the recipe provides the serializer directly:

```python
embedding_bytes = ydb.convert_floats_to_embedding_bytes(embedding)
params = {"$embedding": (embedding_bytes, ydb.PrimitiveType.String)}
```

Pass `params` to the query with `DECLARE $embedding AS String` and use `$embedding` directly in the distance function. Check the installed SDK version before recommending this helper. For an older SDK, use its documented serialization approach or upgrade; do not substitute an unverified `struct.pack` recipe for the complete YDB embedding encoding.

Sources: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main> (Python recommended approach); <https://ydb.tech/docs/en/yql/reference/udf/list/knn#functions-convert>.
