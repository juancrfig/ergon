# Monitor health-check contracts

Every feature must have a human-approved health-check contract next to its feature code before the feature is done. The feature's source declaration is a JSON file named `<feature>.monitor.json`; approval installs a byte-for-byte runtime copy at `$HERMES_HOME/monitor/contracts/<feature>.json`. `HERMES_HOME` defaults to `~/.hermes`.

## Contract format

The contract is a UTF-8 JSON object with these required fields:

- `feature`: lowercase hyphenated feature identifier.
- `checks`: a non-empty array. Each check has a unique `id`, a deterministic shell `command`, a `schedule`, and `severity`.
- `schedule`: exactly one of `{"interval": "<duration>"}` or `{"event": "hermes-update"}` / `{"event": "thesystem-update"}`. Intervals are a positive whole number followed by `m` (at least `5m`, the scheduler tick), `h` or `d` (for example `15m`, `6h`, `1d`).
- `severity`: exactly `normal`, `security`, or `data-loss`.
- `safe_state`: exactly one of `command` or `switch`, plus a human-readable `description`. This is the safe state Monitor may switch to alone.
- `approved_fixes`: an array of explicitly approved fix descriptions. It starts empty; Monitor must not infer approval from a command's presence.
- `sampling`: `what` describes the output to sample, `sample_size` is a positive integer, and `working_well` defines what good output means.

Example:

```json
{
  "feature": "artifact-library",
  "checks": [
    {
      "id": "http-responds",
      "command": "curl --fail --silent http://localhost:8765/",
      "schedule": {"interval": "15m"},
      "severity": "normal"
    },
    {
      "id": "installed-version",
      "command": "umbrella --version",
      "schedule": {"event": "thesystem-update"},
      "severity": "normal"
    }
  ],
  "safe_state": {
    "switch": "stop thesystem-artifacts.service",
    "description": "Stop serving artifacts if the service exposes unsafe content."
  },
  "approved_fixes": [],
  "sampling": {
    "what": "HTML artifact index responses",
    "sample_size": 5,
    "working_well": "Each sampled link resolves to an existing artifact and no private path is exposed."
  }
}
```

## Human approval and runtime behavior

The human reviews the source contract and invokes the workspace command:

```sh
umbrella monitor approve path/to/artifact-library.monitor.json
```

The configured company command replaces `umbrella`. This command validates the contract, copies its exact bytes to `$HERMES_HOME/monitor/contracts/<feature>.json`, and records its SHA-256 in `$HERMES_HOME/monitor/approvals.json`:

```json
{
  "contracts": {
    "artifact-library": {
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  }
}
```

The approve command is the only path that writes or updates this approval record. Neither the scheduler nor Monitor may approve contracts or edit the record. A contract edit changes its digest: the scheduler must skip it until the human approves the revised source contract again. Approved fixes remain empty unless a human explicitly approves fixes in a contract revision and runs the approval command.
