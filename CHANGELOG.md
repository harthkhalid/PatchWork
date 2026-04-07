# Changelog

## Unreleased

- Skip OpenAI call when a pull request has an empty diff (saves quota and avoids useless requests).
- Harden GitHub webhooks: ignore payloads where PR or installation IDs are not valid numbers.
- Rate limiter: treat non-positive `window_sec` or `limit` as safe defaults so Redis keys stay valid.
- Dashboard: show a top loading bar while analytics data is fetching (`aria-busy` for assistive tech).
