# Runtime State Model

The runtime state database is `runtime_state.sqlite`.

## Jobs

Jobs track one complete workflow:

- `queued`
- `searching`
- `building_kb`
- `browser_learning`
- `completed`
- `failed`

## Events

Events are append-only status messages. They are used by the API to show progress.

## Feedback

Feedback is stored by project and DOI/article key. It is also optionally mirrored into the project KB when that KB exists.
