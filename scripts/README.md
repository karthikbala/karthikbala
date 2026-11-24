# Profile activity maintenance

`python3 scripts/update_activity.py` refreshes the SVG and the marked activity
section in the profile README. It uses Python's standard library and does not
need a personal token or access to private repositories.

The source is GitHub's public contribution calendar. It includes only the
aggregate counts the account already shares publicly. The exact 90-day window
includes the current UTC date, so today's count can be partial. GitHub's own
contribution eligibility rules and processing delays still apply. Month labels
and colors follow the public calendar; repository content is never requested.

The workflow runs daily at 02:17 UTC (07:47 India time), when manually dispatched,
or when the generator/workflow changes on main. Only the built-in token for this
profile repository receives contents-write permission. Automated commits use the
GitHub Actions bot identity. No additional secrets are required.

GitHub's calendar HTML is not a versioned API. Missing dates, changed count labels
or inconsistent levels stop generation rather than publishing fabricated zeroes.
The last successful chart remains visible. Check the workflow's Actions log if
the update date stops advancing; scheduled jobs can also be delayed by GitHub.

Run the focused parser, year-boundary and rendering checks with:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```
