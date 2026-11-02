# Client-side balancing

The SDK selects endpoints according to its configured balancing policy. For session-based operations, the node is chosen when a session is created; queries within that session remain attached to that node. Borrowing sessions through the SDK pool lets the SDK manage their lifecycle instead of pinning all application work to one stored session.

Docs: <https://ydb.tech/docs/en/recipes/ydb-sdk/balancing>.

## Defaults

The default policy and its eligible endpoints depend on the SDK and version. Ask for the target SDK and verify its current documentation before recommending a policy or naming an API; do not translate symbols from another SDK by analogy. Random endpoint selection does not rebalance individual queries within an existing session.

## Locality policies

A locality policy can restrict eligible endpoints to a selected location. Whether this is useful depends on application placement, workload, available capacity, discovery metadata, and maintenance or failure requirements.

Risks to check:

- Many application replicas preferring one location can concentrate load there while capacity elsewhere is unused by those clients.
- Maintenance can leave too little eligible capacity.
- Client-to-session-node proximity does not establish locality of the data accessed by the query.
- A locality restriction does not necessarily include cross-location fallback; check the actual policy.

Locality is neither universally required nor universally unsuitable for production. Measure latency and capacity with representative traffic; network RTT alone does not establish the result.

## Operational

Ensure enough healthy eligible capacity remains during planned maintenance and the failures the application must tolerate. Configure an explicit fallback policy when cross-location fallback is required. Keep the policy configurable so it can be changed without rewriting application logic.
