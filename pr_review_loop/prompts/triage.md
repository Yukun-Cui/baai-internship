# Review Triage Prompt

Classify each review item before changing code.

Return one of:

- `must_fix`: a concrete code, test, registration, naming, conflict, or behavior change is required
- `should_reply`: no code change is clearly required, but the reviewer should receive an explanation
- `ignore`: duplicate, obsolete, already handled, bot noise, or unrelated
- `need_human`: ambiguous design decision, risky API change, unclear reviewer intent, or conflicting requirements

Always include evidence from the review text and relevant code/diff context.

