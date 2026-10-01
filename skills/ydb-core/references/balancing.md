# Client-side balancing

SDK picks which cluster node receives each gRPC request. Docs: <https://ydb.tech/docs/en/recipes/ydb-sdk/balancing>.

Topology details and balancer, pool, and session API names differ by SDK. Ask for the target language and verify its current SDK documentation before naming an API; do not translate Go names into another SDK by analogy.

## Default: random spread

Pick an endpoint at random per request. Spreads load across every discovered node. Go SDK names: `embed/go.md`.

## Prefer-DC family

Concentrates traffic on one DC's nodes (current DC, nearest DC, or a named DC). Go SDK API names: `embed/go.md`.

Failure modes:

- DC-skewed load when application replicas cluster in one DC.
- Drill / rolling-restart stickiness: traffic sticks to the few remaining nodes in the chosen DC.
- Cross-DC datashard hops: client→node locality doesn't imply node→tablet locality; under load the tablet moves out anyway.

Pays off only with followers (read replicas) + `StaleRO` reads. Without that, no latency upside.

## Operational

- ≥ 2 YDB nodes per AZ. Single-node-per-zone + prefer-DC = outage on rolling restart.
- If prefer-DC is used, drive it from config (env/dynamic), not a hardcoded driver option — production must be able to roll back without redeploy.
