from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from sportsdata_mcp.market_analysis import (
    TARGET_FOOTBALL_COMPETITIONS,
    TOP_FIVE_LEAGUES,
    analyse_markets,
    analyse_snapshot_directory,
    decimal_implied_probability,
    filter_events_for_local_date,
    select_target_football_competitions,
    select_top_five_competitions,
    snapshot_freshness,
)
from sportsdata_mcp.spec_loader import load_all_specs


@pytest.mark.parametrize(
    ("odds", "expected"),
    [(2, 0.5), (1, 1.0), (None, None), (0, None), (0.99, None), (float("inf"), None), (True, None)],
)
def test_decimal_odds_convert_to_implied_probability(odds, expected):
    assert decimal_implied_probability(odds) == expected


def test_complete_open_win_draw_win_market_is_de_vigged():
    payload = [
        {
            "id": 12,
            "name": "Win-Draw-Win",
            "statusCode": "A",
            "marketSort": "MR",
            "selections": [
                {"id": 1, "name": "Home", "resultType": "H", "statusCode": "A", "price": {"winPrice": 2}},
                {"id": 2, "name": "Draw", "resultType": "D", "statusCode": "A", "price": {"winPrice": 3}},
                {"id": 3, "name": "Away", "resultType": "A", "statusCode": "A", "price": {"winPrice": 4}},
            ],
        }
    ]

    result = analyse_markets(payload)

    market = result["markets"][0]
    assert market["noVig"]["rawImpliedProbabilitySum"] == pytest.approx(1.0833333333)
    assert market["noVig"]["overroundPercent"] == pytest.approx(8.3333333)
    assert [row["normalizedImpliedProbability"] for row in market["selections"]] == pytest.approx(
        [6 / 13, 4 / 13, 3 / 13]
    )


def test_non_1x2_market_gets_raw_implied_probability_without_normalization():
    result = analyse_markets(
        [
            {
                "name": "Over/Under 2.5 Goals",
                "statusCode": "A",
                "selections": [
                    {"name": "Over", "statusCode": "A", "price": {"winPrice": 1.9}},
                    {"name": "Under", "statusCode": "A", "price": {"winPrice": 1.9}},
                ],
            }
        ]
    )
    assert result["markets"][0]["selections"][0]["impliedProbability"] == pytest.approx(1 / 1.9)
    assert result["markets"][0]["selections"][0]["normalizedImpliedProbability"] is None
    assert result["markets"][0]["noVig"] is None


def test_prices_and_statuses_are_counted_separately():
    result = analyse_markets(
        [
            {
                "name": "Win-Draw-Win",
                "statusCode": "A",
                "selections": [
                    {"resultType": "H", "statusCode": "A", "price": {"winPrice": 2}},
                    {"resultType": "D", "statusCode": "S", "price": {"winPrice": 3}},
                    {"resultType": "A", "statusCode": "A", "price": None},
                ],
            }
        ]
    )
    assert result["selectionCount"] == 3
    assert result["pricedSelectionCount"] == 2
    assert result["activePricedSelectionCount"] == 1
    assert result["suspendedPricedSelectionCount"] == 1
    assert result["missingOrInvalidPriceCount"] == 1
    assert result["markets"][0]["noVig"] is None


def test_snapshot_freshness_requires_an_aware_timestamp_and_flags_age():
    now = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert snapshot_freshness("2026-10-12T23:55:00+00:00", now=now)["status"] == "fresh"
    assert snapshot_freshness("2026-10-12T23:00:00+00:00", now=now)["status"] == "stale"
    assert snapshot_freshness("2026-10-12T23:00:00", now=now)["status"] == "unknown"


def test_fixture_filter_uses_brisbane_local_date_from_the_event_instant():
    events = [
        {"id": 1, "name": "Early", "startTime": 1791909900},  # 2026-10-13 16:45 UTC
        {"id": 2, "name": "Late", "startTime": 1791918000},  # 2026-10-13 19:00 UTC
        {"id": 3, "name": "Next Brisbane date", "startTime": 1791996300},
    ]
    grouped = [{"groupName": "Match Betting", "events": events}]
    assert [event["id"] for event in filter_events_for_local_date(grouped, "2026-10-14")] == [1, 2]


def test_top_five_competition_selection_uses_soccer_nodes_and_internal_ids_only():
    nav = {
        "idType": "CONST",
        "navItems": [
            {
                "idType": "class",
                "name": "Soccer",
                "navItems": [
                    {
                        "name": "UEFA Competitions",
                        "navItems": [
                            {"idType": "competition", "id": 10, "name": "UEFA Champions League"}
                        ],
                    },
                    {
                        "name": "United Kingdom",
                        "navItems": [
                            {
                                "idType": "competition",
                                "id": 718,
                                "competitionExternalId": "289",
                                "name": "English Premier League",
                            },
                            {"idType": "competition", "id": 719, "name": "English Championship"},
                        ],
                    },
                    {
                        "name": "Spain",
                        "navItems": [
                            {"idType": "competition", "id": 1029, "name": "Spanish La Liga"}
                        ],
                    },
                    {
                        "name": "Italy",
                        "navItems": [
                            {"idType": "competition", "id": 1015, "name": "Italian Serie A"}
                        ],
                    },
                    {
                        "name": "Germany",
                        "navItems": [
                            {"idType": "competition", "id": 739, "name": "German Bundesliga"}
                        ],
                    },
                    {
                        "name": "France",
                        "navItems": [
                            {"idType": "competition", "id": 876, "name": "French Ligue 1"}
                        ],
                    },
                ],
            },
            {
                "idType": "class",
                "name": "Basketball",
                "navItems": [
                    {"idType": "competition", "id": 999, "name": "Italian Serie A"}
                ],
            },
        ],
    }

    competitions = select_top_five_competitions(nav)

    assert tuple(row["league"] for row in competitions) == TOP_FIVE_LEAGUES
    assert [row["competitionId"] for row in competitions] == [718, 1029, 1015, 739, 876]
    assert competitions[0]["competitionExternalId"] == "289"


def test_top_five_competition_selection_supports_competition_id_shape():
    nav = {
        "nav": [
            {
                "name": "Soccer",
                "competitions": [
                    {"competitionId": "77", "name": "LaLiga EA Sports"},
                    {"competitionId": "78", "name": "Ligue 1 McDonald's"},
                ],
            }
        ]
    }

    competitions = select_top_five_competitions(nav)

    assert [(row["league"], row["competitionId"]) for row in competitions] == [
        ("Spanish La Liga", "77"),
        ("French Ligue 1", "78"),
    ]


def test_top_five_competition_selection_requires_a_soccer_navigation_node():
    with pytest.raises(ValueError, match="Soccer/Football class"):
        select_top_five_competitions({"navItems": [{"name": "Basketball", "navItems": []}]})


def test_target_competition_selection_includes_all_requested_leagues_and_cups():
    names = [
        "English Premier League",
        "Spanish La Liga",
        "Italian Serie A",
        "German Bundesliga",
        "French Ligue 1",
        "UEFA Champions League",
        "UEFA Europa League",
        "UEFA Conference League",
        "UEFA Super Cup",
        "English FA Cup",
        "English Football League Cup",
        "FA Community Shield",
        "Spanish Copa del Rey",
        "Spanish Supercopa de España",
        "German DFB Pokal",
        "German DFL-Supercup",
        "Italian Coppa Italia",
        "Italian Supercoppa Italiana",
        "French Coupe de France",
        "French Trophée des Champions",
    ]
    payload = {
        "navItems": [
            {
                "idType": "class",
                "name": "Soccer",
                "navItems": [
                    {"name": "European competitions", "navItems": [
                        {"idType": "competition", "id": index, "name": name}
                        for index, name in enumerate(names, start=100)
                    ]},
                    # Duplicate live navigation rows should still select one competition.
                    {"idType": "competition", "id": 100, "name": "UEFA Champions League"},
                ],
            },
            {
                "idType": "class",
                "name": "Basketball",
                "navItems": [{"idType": "competition", "id": 999, "name": "UEFA Champions League"}],
            },
        ]
    }

    competitions = select_target_football_competitions(payload)

    assert tuple(row["competition"] for row in competitions) == TARGET_FOOTBALL_COMPETITIONS
    assert len(competitions) == 20
    assert competitions[-1]["competitionName"] == "French Trophée des Champions"
    assert [row["competitionId"] for row in competitions] == list(range(100, 120))


def test_target_competition_selection_returns_only_currently_available_names():
    payload = {
        "navItems": [
            {
                "idType": "class",
                "name": "Soccer",
                "navItems": [
                    {"idType": "competition", "id": 727, "name": "UEFA Champions League"},
                    {"idType": "competition", "id": 726, "name": "English FA Cup"},
                ],
            }
        ]
    }

    competitions = select_target_football_competitions(payload)

    assert [(row["competition"], row["competitionId"]) for row in competitions] == [
        ("UEFA Champions League", 727),
        ("English FA Cup", 726),
    ]


def test_target_competition_name_matching_folds_accents_and_punctuation():
    payload = {
        "nav": [
            {
                "name": "Soccer",
                "competitions": [
                    {"competitionId": "1", "name": "Spanish Supercopa de Espana"},
                    {"competitionId": "2", "name": "French Trophee des Champions"},
                    {"competitionId": "3", "name": "German DFL-Supercup"},
                ],
            }
        ]
    }

    competitions = select_target_football_competitions(payload)

    assert [row["competition"] for row in competitions] == [
        "Spanish Supercopa de España",
        "German DFL-Supercup",
        "French Trophée des Champions",
    ]


def test_documented_sportsbet_workflow_contains_only_anonymous_get_tools():
    spec = next(spec for spec in load_all_specs() if spec.provider.id == "sportsbet")
    tools = {
        endpoint.name: endpoint
        for endpoint in spec.endpoints
        if endpoint.name
        in {
            "sportsbet_nav_hierarchy",
            "sportsbet_competition_matches",
            "sportsbet_event_markets",
            "sportsbet_event_status",
        }
    }

    assert set(tools) == {
        "sportsbet_nav_hierarchy",
        "sportsbet_competition_matches",
        "sportsbet_event_markets",
        "sportsbet_event_status",
    }
    assert all(endpoint.method == "GET" for endpoint in tools.values())
    assert all(endpoint.auth == "default" for endpoint in tools.values())
    assert all(endpoint.group in {"sportsbet.sports", "sportsbet.cross"} for endpoint in tools.values())


def test_snapshot_directory_retains_failed_market_requests(tmp_path):
    manifest = {
        "provider": "Sportsbet",
        "requestedLocalDate": "2026-10-14",
        "timezone": "Australia/Brisbane",
        "events": [
            {
                "eventId": "broken",
                "endpoint": "https://example.invalid/markets",
                "httpStatus": 503,
                "retrievedAt": "2026-10-13T01:00:00+10:00",
                "error": "upstream unavailable",
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = analyse_snapshot_directory(tmp_path)

    assert result["events"][0]["httpStatus"] == 503
    assert result["events"][0]["requestError"] == "upstream unavailable"
    assert result["fixtureDate"] == "2026-10-14"
    assert result["fixtureTimezone"] == "Australia/Brisbane"
    assert "analysis" not in result["events"][0]


def test_snapshot_directory_flags_post_kickoff_prices_and_event_status_conflict(tmp_path):
    kickoff = datetime(2026, 10, 13, 16, 45, tzinfo=UTC).timestamp()
    (tmp_path / "markets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"eventStatus": "preview"}), encoding="utf-8")
    manifest = {
        "requestedLocalDate": "2026-10-14",
        "timezone": "Australia/Brisbane",
        "events": [
            {
                "eventId": "event-1",
                "eventName": "Example v Match",
                "competition": "UEFA Champions League",
                "httpStatus": 200,
                "retrievedAt": "2026-10-13T16:53:40+00:00",
                "scheduledStartTime": kickoff,
                "rawFile": "markets.json",
            }
        ],
        "eventStatuses": [
            {
                "eventId": "event-1",
                "httpStatus": 200,
                "retrievedAt": "2026-10-13T16:54:00+00:00",
                "rawFile": "status.json",
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = analyse_snapshot_directory(tmp_path)

    event = result["events"][0]
    assert event["retrievalTiming"]["status"] == "after-scheduled-kickoff"
    assert event["eventStatus"] == "preview"
    assert event["eventStatusConflict"] is True
