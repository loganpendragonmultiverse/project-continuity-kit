# Continuity example

From the repository root with the package installed:

```bash
continuity-kit examples/sample.json --format json --output build/continuity.json --bundle build/continuity.zip
continuity-kit --verify-bundle build/continuity.zip --root . --format json
```

Use fresh output names for another run. `build` is excluded, so these outputs do not become source drift. The sample checklist is an author assertion and does not prove a recovery was executed. No repository file contents are exported; inspect file names and human notes before sharing. Lower scan limits by supplying a complete `scan_limits` version-1 object; omitted limits use the documented defaults.
