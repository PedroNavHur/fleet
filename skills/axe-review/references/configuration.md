# Scanner configuration

Use a temporary JSON file when a scan needs authentication, multiple viewports,
scoped analysis, or interaction before axe runs. Relative paths resolve from
the configuration file.

```json
{
  "baseUrl": "https://example.test",
  "storageState": ".scratch/playwright-auth.json",
  "timeoutMs": 30000,
  "tags": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
  "viewports": [
    { "name": "desktop", "width": 1440, "height": 900 },
    { "name": "mobile", "width": 390, "height": 844 }
  ],
  "pages": [
    {
      "name": "open navigation",
      "url": "/",
      "waitFor": "main",
      "actions": [
        { "type": "wait", "milliseconds": 500 },
        { "type": "click", "selector": "role=button[name='Menu']" },
        { "type": "waitFor", "selector": "role=navigation" }
      ],
      "include": ["main", "nav"],
      "exclude": []
    }
  ]
}
```

Supported actions are:

- `wait`: `milliseconds`, capped by `timeoutMs`; use only when hydration has no
  observable ready selector
- `click`: `selector`
- `fill`: `selector`, `value`
- `press`: `selector`, `key`
- `check`: `selector`
- `selectOption`: `selector`, `value`
- `waitFor`: `selector`
- `waitForURL`: `url`

`include` and `exclude` accept CSS selectors supported by AxeBuilder. Interaction
actions and `waitFor` accept Playwright selectors.
Omit `tags` to run every enabled axe rule, including best-practice rules. The
WCAG tags above limit the run to automated WCAG A and AA checks.

Run the manifest with:

```bash
axe-review --config /absolute/path/to/axe-review.json
```

The scanner prints a compact text report by default. Add `--format json` when a
machine-readable result is useful. The scanner creates no report files.
