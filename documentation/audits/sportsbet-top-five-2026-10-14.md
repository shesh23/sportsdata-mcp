# Top-five league fixture audit — 14 October 2026 Brisbane time

## Scope and result

The checked competitions were the English Premier League, Spanish La Liga, Italian Serie A,
German Bundesliga, and French Ligue 1. Sportsbet navigation identified these as Soccer
competitions with internal IDs 718, 1029, 1015, 739, and 876, respectively.

The anonymous Sportsbet navigation request and all five competition match-feed requests
returned HTTP 200. Filtering returned kickoff instants in `Australia/Brisbane` found **0
fixtures** on 14 October 2026. No market endpoint was called because no matching event was
returned. For this snapshot, retrieved markets: **0**; priced selections: **0**. This does
not assert that the leagues have no other fixtures or markets on other dates.

## Request log

All timestamps below are UTC, recorded immediately before the request.

| Request | HTTP | Retrieved at |
| --- | ---: | --- |
| Soccer navigation hierarchy | 200 | 2026-10-12T16:01:51.0885209+00:00 |
| English Premier League matches | 200 | 2026-10-12T16:01:51.4748988+00:00 |
| Spanish La Liga matches | 200 | 2026-10-12T16:01:51.6653989+00:00 |
| Italian Serie A matches | 200 | 2026-10-12T16:01:51.8456718+00:00 |
| German Bundesliga matches | 200 | 2026-10-12T16:01:51.9558823+00:00 |
| French Ligue 1 matches | 200 | 2026-10-12T16:01:52.0486891+00:00 |

The raw response bodies and `manifest.json` are in
`data/audits/sportsbet-top-five-2026-10-14-raw/`.

## Schedule references

- [Premier League 2026/27 fixtures](https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-202627-premier-league-season)
- [La Liga 2026/27 calendar](https://www.laliga.com/calendar-2026-2027/laliga-easports)
- [Serie A 2026/27 schedule and results](https://www.legaseriea.it/serie-a/calendario-risultati)
- [Bundesliga fixtures](https://products.bundesliga.com/fixtures)
- [Ligue 1 2026/27 calendar](https://ligue1.com/en/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released)

There are no odds, independent forecasts, team-stat comparisons, or bookmaker-price
comparisons in this audit because there were no confirmed matching events to compare.
