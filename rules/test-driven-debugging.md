# Test-Driven Debugging

When investigating a bug, write tests that trace the execution path rather than reading code and guessing. Tests both diagnose the problem and remain as regression coverage.

## Approach

### 1. Trace the Full Chain

Map the complete execution path from trigger to symptom. Identify every component boundary where data passes between layers.

**Example:** "UI shows blank screen" might traverse:
```
App launch → config resolution → process spawn → connection setup → data pipeline → rendering
```

### 2. Write Tests at Each Layer

For each component in the chain, write tests that verify:

- **Happy path**: Does the component work when given correct inputs?
- **Failure modes**: What happens when inputs are wrong, missing, or malformed?
- **Error propagation**: Do errors surface clearly or get swallowed silently?
- **State transitions**: Does the component report its state accurately (alive/dead, connected/disconnected)?

Start with unit tests (mocked dependencies), then add integration tests (real components wired together).

### 3. Let Tests Reveal the Bug

Tests that **pass** eliminate that layer as the cause. Tests that **fail** or **document broken behavior** point to the root cause. Tests that **hang** reveal blocking issues.

The diagnosis comes from the pattern of pass/fail across the chain, not from any single test.

### 4. Fix and Verify

Once the root cause is identified:

1. Update relevant tests to expect the **fixed** behavior (they should fail against current code)
2. Apply the fix
3. Verify the updated tests pass
4. Run the full suite to catch regressions

## What to Test

| Priority | What | Why |
|----------|------|-----|
| High | Error propagation paths | Silent error swallowing is the most common cause of "nothing happens" bugs |
| High | Component boundaries | Data format mismatches between layers cause subtle failures |
| High | State reporting | Components that lie about their state (alive when dead, connected when not) cause cascading failures |
| Medium | Timeout/fallback behavior | Timeouts that are too short or fallbacks that hide errors |
| Medium | Resource cleanup | Leaked resources that work on first run but fail on reconnect |

## Anti-Patterns

- **Don't guess first, test first.** Reading code and forming hypotheses without verification leads to confirmation bias.
- **Don't only test the suspected cause.** The bug might be two layers away from where you think it is. Test the full chain.
- **Don't write tests that only pass.** Tests documenting broken behavior are diagnostic. Update them to expect correct behavior, then fix the code.
- **Don't discard diagnostic tests.** Even after the bug is fixed, these tests prevent regression.
