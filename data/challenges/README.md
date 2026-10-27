# Annual challenge registry

Keep one YAML file per calendar year (`YYYY.yaml`). Add each monthly Garmin challenge once. Use a stable ID in the form `<series>-<year>-<month>`.

Fields:

- `year`: calendar year for this file
- `id`: stable identifier for this occurrence
- `month`: month number (1–12)
- `title`: display title
- `start_date`, `end_date`: challenge period from Garmin
- `garmin_uuid_secret`: name of the GitHub Actions Secret containing this challenge's Garmin UUID; never put the UUID or private link in this public repository
- `target_distance_km`: common distance threshold used to count achievers across every tier. When Garmin's title lists multiple tier distances, use the longest one here.
- `goals`: optional list of tier rules, each with a `name`, optional `pace_limit_min_per_km`, and `pace_limit_operator` (`<` or `<=`). Do not repeat the common distance for each tier.
- `stage_month` inside a goal: optional progression stage when stated in the challenge title
- `status`: `planned`, `active`, or `archived`

Garmin's challenge title contains group rules and distances; the authenticated response did not have a separate goal field. The March and June links supplied were assigned by their Garmin start dates because their titles and dates showed those two months were reversed. The daily pipeline loads the active entry and its named GitHub Actions Secret. When tier distances differ, the common achievement threshold must be at least the longest tier distance.
