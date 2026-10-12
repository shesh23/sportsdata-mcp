# Soccer fixture and market audit — 14 October 2026 Brisbane time

## Run summary

The run queried the anonymous, read-only Sportsbet navigation, match, market, and event
status GET endpoints. All requests returned HTTP 200. The navigation exposed 11 of the 20
requested competitions; match feeds were queried only for those live navigation entries.
The returned event timestamps yielded nine UEFA Champions League fixtures on 14 October
in `Australia/Brisbane`. UEFA's official Matchday 2 preview independently lists these
same nine matches on Tuesday 13 October in Europe. The nine listings and start times are
in the [UEFA matchday preview](https://www.uefa.com/uefachampionsleague/news/02aa-21c5297d7408-32d70b5a4443-1000--champions-league-matchday-2-key-stats-and-what-to-look-o/).

| Request group | Retrieved at (UTC) | Requests | HTTP failures |
| --- | --- | ---: | ---: |
| Navigation | 2026-10-12 16:52:04.577Z | 1 | 0 |
| Competition match feeds | 2026-10-12 16:53:37.773Z–16:53:39.466Z | 11 | 0 |
| Event markets | 2026-10-12 16:53:39.747Z–16:53:41.871Z | 9 | 0 |
| Event status | 2026-10-12 16:57:02.568Z–16:57:03.755Z | 9 | 0 |

The raw response bodies, per-request timestamps, and selected/unavailable competition
lists are in [`data/audits/sportsbet-all-football-2026-10-14-rerun/`](../../data/audits/sportsbet-all-football-2026-10-14-rerun/).
The complete offline analysis is in [`market-analysis.json`](../../data/audits/sportsbet-all-football-2026-10-14-rerun/market-analysis.json).

## Competitions unavailable in this navigation response

Sportsbet did not expose these requested competitions under its current Soccer navigation:

- UEFA Super Cup
- FA Community Shield
- Spanish Copa del Rey and Supercopa de España
- German DFL-Supercup
- Italian Coppa Italia and Supercoppa Italiana
- French Coupe de France and Trophée des Champions

No IDs were guessed and no match request was made for these nine competitions. The other
11 competitions appeared in the live feed: the top five leagues, all three UEFA league
competitions, English FA Cup and EFL Cup, and German DFB-Pokal.

## Confirmed fixtures and Sportsbet markets

All times below are Brisbane time. Decimal odds are the Sportsbet `Win-Draw-Win` prices
from the raw markets response, ordered home/draw/away. De-vigged percentages use
proportional normalization of those three active outcomes. All markets had status `A`;
selection statuses are shown as active/suspended. Every returned selection had a valid
decimal price.

| Fixture | Kick-off | Markets | Selections (priced) | Active / suspended selections | 1X2 odds H / D / A | No-vig H / D / A | Overround |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |
| FC Sabah v Slavia Prague | 02:45 | 234 | 1,936 (1,936) | 1,897 / 39 | 3.50 / 3.60 / 2.03 | 27.05% / 26.30% / 46.64% | 5.61% |
| Lens v Sporting Lisbon | 02:45 | 250 | 1,657 (1,657) | 1,620 / 37 | 2.50 / 3.70 / 2.60 | 37.92% / 25.62% / 36.46% | 5.49% |
| Arsenal v Lille | 05:00 | 278 | 2,129 (2,129) | 2,091 / 38 | 1.21 / 6.75 / 14.00 | 79.01% / 14.16% / 6.83% | 4.60% |
| Atlético Madrid v Manchester United | 05:00 | 277 | 2,270 (2,270) | 2,230 / 40 | 1.93 / 3.80 / 3.75 | 49.44% / 25.11% / 25.45% | 4.80% |
| Galatasaray v Barcelona | 05:00 | 278 | 2,494 (2,494) | 2,465 / 29 | 8.75 / 6.75 / 1.25 | 10.76% / 13.94% / 75.30% | 6.24% |
| Inter v Club Brugge | 05:00 | 261 | 2,586 (2,586) | 2,548 / 38 | 1.25 / 6.25 / 11.50 | 76.41% / 15.28% / 8.31% | 4.70% |
| RB Leipzig v PSV | 05:00 | 229 | 1,817 (1,817) | 1,785 / 32 | 1.74 / 4.60 / 3.90 | 54.81% / 20.73% / 24.45% | 4.85% |
| Villarreal v Napoli | 05:00 | 252 | 1,987 (1,987) | 1,945 / 42 | 2.12 / 3.60 / 3.25 | 44.62% / 26.28% / 29.11% | 5.72% |
| Viking v Bayern Munich | 05:00 | 258 | 2,383 (2,383) | 2,353 / 30 | 19.00 / 13.00 / 1.09 | 5.03% / 7.35% / 87.63% | 4.70% |
| **Total** |  | **2,317** | **19,259 (19,259)** | **18,934 / 325** |  |  |  |

The event status endpoint returned `preview` for all nine matches. Each market response was
retrieved before its scheduled kickoff, including the two 02:45 Brisbane matches (scheduled
for 2026-10-13 16:45 UTC; retrieved at approximately 2026-10-12 16:53 UTC). This agrees
with the event status. The offline analysis was regenerated at 2026-10-12 17:15:51 UTC.
At that point the saved market snapshots were 22.2 minutes old and exceeded the 15-minute
freshness limit, so the analyser marks all nine events stale. Sportsbet did not return a
per-price update time, so the exact time each quote last changed is unknown. There were no
missing/invalid prices, failed requests, or status conflicts in this run. The 325
suspended selections did have prices, but are not counted as active prices.

## Independent context

These comparisons are contextual and use the same 1X2 definition where stated. They are
not a claim that the sources were synchronized with the Sportsbet capture. Published model
probabilities are kept separate from bookmaker odds.

| Match | Accessible independent comparison | Timing / limitation |
| --- | --- | --- |
| Sabah–Slavia | Rondo Research forecast: Sabah 32%, draw 22%, Slavia 46%; Sportsbet no-vig: 27.05%, 26.30%, 46.64%. Sportingbet also displayed 3.30 / 3.75 / 2.05. | Rondo says its model was computed 10 Oct. Sportingbet does not show a quote update time. [Rondo](https://rondoresearch.com/en/europe/champions-league/fixtures/sabah-slavia-praha-19873659), [Sportingbet](https://www.sportingbet.com/en/sports/events/fc-sabah-masazir-slavia-prague-2%3A7865739) |
| Lens–Sporting | An Oddschecker listing showed 2.35 / 3.75 / 2.70. | Its page says last updated 10 Sep, so it is stale for a 13 Oct match and excluded from a current-price comparison. [Oddschecker](https://www.oddschecker.com/football/champions-league/lens-v-sporting-lisbon/winner) |
| Arsenal–Lille | Ladbrokes published a 2–0 Arsenal prediction and displayed 1.25 / 6.50 / 11.00. | Article published 12 Oct; quote-specific timestamp not stated. [Ladbrokes](https://www.ladbrokes.com/en/news/arsenal-lille-champions-league-predictions-2026-10-13/) |
| Atlético–Manchester United | No quote with a clear update time was available in the sources checked. | Other pages displayed odds but did not establish when those quotes were captured; omitted as non-synchronous. UEFA's team-form notes are available in its matchday preview. |
| Galatasaray–Barcelona | Rondo model: 13% / 14% / 73% (computed 11 Oct), close to Sportsbet no-vig 10.76% / 13.94% / 75.30%. KrystalPredict gave a very different 43.4% / 21.5% / 35.1%. | The published forecasts materially disagree; no forecast consensus is claimed. [Rondo](https://rondoresearch.com/en/europe/champions-league/fixtures/galatasaray-fc-barcelona-19872596), [KrystalPredict](https://www.krystalpredict.com/football/galatasaray-sk-vs-fc-barcelona-2026-10-13-prediction) |
| Inter–Club Brugge | Unibet displayed 1.22 / 5.80 / 9.50. BetStudy model probabilities were 66% / 16% / 18%; Sportsbet no-vig was 76.41% / 15.28% / 8.31%. | Unibet quote time is unstated; BetStudy is a model forecast, not a bookmaker price. [Unibet](https://www.unibet.fr/paris-sportifs/ligue-des-champions-intermilan-clubbruges), [BetStudy](https://www.betstudy.com/fr/pronostic/19873230/inter-club-brugge/) |
| RB Leipzig–PSV | Oddsator listed Pinnacle at 1.76 / 4.72 / 3.91; Sportsbet returned 1.74 / 4.60 / 3.90. | Oddsator showed “35 min ago” on the page when checked; no exact absolute quote time was supplied. [Oddsator](https://www.oddsator.com/football/world/uefa-champions-league/psv-vs-rb-leipzig-2026-10-13) |
| Villarreal–Napoli | Betimate predicted Villarreal at 43% and a 2–1 score; Sportsbet no-vig home probability was 44.62%. OddsFilter's bookmaker average was 2.19 / 3.64 / 3.07. | Betimate updated 11 Oct. OddsFilter explicitly dated its price board 11 Oct 12:30 UTC, roughly 28 hours before the Sportsbet snapshot; treat as stale context. [Betimate](https://betimate.com/en/news/previews/villarreal-vs-napoli-prediction-odds-betting-tips-10132026-2837322), [OddsFilter](https://oddsfilter.com/event/1001635748-villarreal-napoli) |
| Viking–Bayern | No independently timestamped bookmaker quote or published 1X2 forecast was found in the sources checked. | UEFA's team-form notes are available in its matchday preview. |

The [UEFA matchday preview](https://www.uefa.com/uefachampionsleague/news/02aa-21c5297d7408-32d70b5a4443-1000--champions-league-matchday-2-key-stats-and-what-to-look-o/)
also publishes recent competition/team statistics for all nine fixtures. Examples include
Arsenal's 13-match league-phase winning run, Inter's six losses in their previous seven
Champions League games, PSV's one win in 21 away matches against German opponents, and
Villarreal's 12-match winless run in the competition. These are form indicators, not
probability estimates.

## Calculation and freshness rules

For each valid decimal quote `d`, the raw implied probability is `1 / d`. The displayed
no-vig percentages are only calculated for the complete, active three-outcome
`Win-Draw-Win` market, by dividing each raw probability by their sum. The reported
overround is that sum minus one. Other market types are preserved with raw prices and
statuses but are not normalized as if their outcomes were exhaustive.

The saved analyzer output classifies snapshot age and compares the market retrieval time
with scheduled kickoff. A post-kickoff market request is flagged as potentially live or
stale even if its returned market status is active. The analyzer does not manufacture
price-update times, probabilities, fixtures, or data for unavailable competitions.
