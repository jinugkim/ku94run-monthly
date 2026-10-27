# Annual challenge registry

Keep one YAML file per calendar year (`YYYY.yaml`). Add each monthly Garmin challenge once. Use a stable ID in the form `<series>-<year>-<month>`.

Fields:

- `year`: calendar year for this file
- `id`: stable identifier for this occurrence
- `month`: month number (1–12)
- `title`: display title
- `start_date`, `end_date`: challenge period from Garmin
- `garmin_uuid_secret`: name of the GitHub Actions Secret containing this challenge's Garmin UUID; never put the UUID or private link in this public repository
- `target_distance_km`: shared monthly target in kilometers, when every participant has the same goal
- `goals`: optional list of group-specific goals, each with a `name`, optional `pace_limit_min_per_km`, `pace_limit_operator` (`<` or `<=`), and `target_distance_km`
- `stage_month` inside a goal: optional progression stage when stated in the challenge title
- `status`: `planned`, `active`, or `archived`

The annual files are the initial registry format. Garmin's challenge title contains the group rules and distances; the authenticated response did not have a separate goal field. The March and June links supplied were assigned by their Garmin start dates because the links' titles and dates showed those two months were reversed. The daily report pipeline currently reads `GARMIN_CHALLENGE_UUID` and does not yet load these files. Registry loading and lookup of the named GitHub Actions Secrets still need to be implemented.
