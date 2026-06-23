# Privacy

Gap Assist processes pixels locally. First-party code contains no HTTP client,
analytics, crash telemetry, account identifier, or remote inference call. Settings
contain only mode/threshold/output preferences. Image content and bulk pixel values
are not logged.

The CLI writes only paths explicitly requested or deterministic sibling outputs.
It does not create hidden temporary image copies. The host adapter must preserve
these rules: no network transmission, no telemetry, no image-bearing logs, and no
undeleted temporary files. Debug logging remains off by default and must be enabled
explicitly if expanded in a future build.
