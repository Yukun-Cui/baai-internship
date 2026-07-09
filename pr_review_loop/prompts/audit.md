# Codex Audit Prompt

Review the fixer output as a strict code reviewer.

Inputs:

- original review text
- triage decision
- fixer notes
- git diff
- test output
- reply draft

Return JSON:

```json
{
  "decision": "approved | needs_revision | needs_human",
  "summary": "...",
  "findings": [
    {
      "severity": "blocking | warning | note",
      "file": "...",
      "line": 123,
      "message": "..."
    }
  ],
  "required_changes": [
    "..."
  ],
  "reply_to_reviewer": "..."
}
```

Check:

- whether the review was actually addressed
- whether unrelated files changed
- whether behavior regressed
- whether validation is adequate
- whether the fixer hallucinated APIs or code paths
- whether any forbidden attribution trailer was added
- whether `reply_draft.md` is accurate and belongs under the original review line

