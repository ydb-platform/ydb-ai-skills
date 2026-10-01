# FloatVector parameters in Python (`ydb`)

For an application-provided `list[float]`, follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (Python tab) to serialize it on the client. Bind the result as YQL `String`, including for a stored embedding column or an `AS_TABLE` batch member. Avoid passing `List<Float>` and calling `Knn::ToBinaryStringFloat` in YQL when the vector already exists in Python. The YQL conversion remains useful for vectors constructed inside YQL.

Sources: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main> (Python recommended approach); <https://ydb.tech/docs/en/yql/reference/udf/list/knn#functions-convert>.
