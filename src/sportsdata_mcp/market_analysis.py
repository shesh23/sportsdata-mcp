"""Read-only helpers for analysing Sportsbet market snapshots.

This module consumes responses from the existing Sportsbet read tools. It never makes
HTTP requests and contains no betting, account, or wallet operations.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_SUPPORTED_NO_VIG_MARKET = "Win-Draw-Win"
_ONE_X_TWO_RESULTS = {"H", "D", "A"}
TOP_FIVE_LEAGUE_ALIASES = {
    "English Premier League": {"english premier league", "premier league", "epl"},
    "Spanish La Liga": {"spanish la liga", "la liga", "laliga", "laliga ea sports"},
    "Italian Serie A": {"italian serie a", "serie a", "serie a enilive"},
    "German Bundesliga": {"german bundesliga", "bundesliga"},
    "French Ligue 1": {"french ligue 1", "ligue 1", "ligue 1 mcdonald's"},
}
TOP_FIVE_LEAGUES = tuple(TOP_FIVE_LEAGUE_ALIASES)


def select_top_five_competitions(payload: Any) -> list[dict[str, Any]]:
    """Select only the five requested domestic leagues from Sportsbet's soccer navigation."""
    if not isinstance(payload, dict):
        raise TypeError("Expected a Sportsbet navigation object.")

    roots = payload.get("navItems", payload.get("nav"))
    if not isinstance(roots, list):
        raise TypeError("Expected Sportsbet navigation items.")

    matches: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if not isinstance(value, dict):
            return

        name = value.get("name")
        if isinstance(name, str):
            normalized_name = name.casefold().strip()
            for league, aliases in TOP_FIVE_LEAGUE_ALIASES.items():
                if normalized_name in aliases and (
                    value.get("idType") == "competition" or "competitionId" in value
                ):
                    competition_id = (
                        value.get("id") if value.get("idType") == "competition" else value.get("competitionId")
                    )
                    if competition_id is None:
                        competition_id = value.get("id")
                    if competition_id is not None:
                        matches[league] = {
                            "league": league,
                            "competitionName": name,
                            "competitionId": competition_id,
                            "competitionExternalId": value.get("competitionExternalId"),
                        }
                    break

        for key in ("navItems", "competitions"):
            if key in value:
                visit(value[key])

    soccer_roots = [
        node
        for node in roots
        if isinstance(node, dict)
        and isinstance(node.get("name"), str)
        and node["name"].casefold().strip() in {"soccer", "football"}
        and (node.get("idType") == "class" or "classId" in node or node.get("name") == "Soccer")
    ]
    if not soccer_roots:
        raise ValueError("Sportsbet navigation did not contain a Soccer/Football class.")
    for soccer in soccer_roots:
        visit(soccer.get("navItems", soccer.get("competitions", [])))

    return [matches[league] for league in TOP_FIVE_LEAGUES if league in matches]


def decimal_implied_probability(decimal_odds: Any) -> float | None:
    """Return 1 / decimal odds, or ``None`` when the quote is absent or invalid."""
    if isinstance(decimal_odds, bool):
        return None
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(odds) or odds < 1.0:
        return None
    return 1.0 / odds


def _market_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [market for market in payload if isinstance(market, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("markets"), list):
        return [market for market in payload["markets"] if isinstance(market, dict)]
    raise ValueError("Expected a Sportsbet markets array or an object containing 'markets'.")


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("statusCode") or "missing") for row in rows)
    return dict(sorted(counts.items()))


def _selection_odds(selection: dict[str, Any]) -> Any:
    price = selection.get("price")
    return price.get("winPrice") if isinstance(price, dict) else None


def _complete_three_way_market(market: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    """Only de-vig the known soccer 1X2 market when all outcomes are open and priced."""
    if market.get("name") != _SUPPORTED_NO_VIG_MARKET or market.get("statusCode") != "A":
        return False
    if len(rows) != 3 or {row.get("resultType") for row in rows} != _ONE_X_TWO_RESULTS:
        return False
    return all(
        row.get("statusCode") == "A"
        and decimal_implied_probability(_selection_odds(row)) is not None
        for row in rows
    )


def _parse_timestamp(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp


def snapshot_freshness(
    retrieved_at: str | datetime | None,
    *,
    now: datetime | None = None,
    max_age_seconds: float = 900,
) -> dict[str, Any]:
    """Classify snapshot age; this cannot establish when Sportsbet last changed a price."""
    retrieved = _parse_timestamp(retrieved_at)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone.")
    age = (current - retrieved).total_seconds() if retrieved is not None else None
    if age is None or age < 0:
        status = "unknown"
    elif age > max_age_seconds:
        status = "stale"
    else:
        status = "fresh"
    return {
        "status": status,
        "ageSeconds": age,
        "maxAgeSeconds": max_age_seconds,
        "priceUpdatedAt": None,
        "note": "Freshness is measured from retrieval time; the provider response has no per-price update time.",
    }


def analyse_markets(
    payload: Any,
    *,
    retrieved_at: str | datetime | None = None,
    now: datetime | None = None,
    max_age_seconds: float = 900,
) -> dict[str, Any]:
    """Count and enrich all returned markets/selections without discarding raw statuses."""
    markets = _market_list(payload)
    market_rows: list[dict[str, Any]] = []
    all_selections: list[dict[str, Any]] = []

    for market in markets:
        selections = market.get("selections")
        selection_rows = [row for row in selections if isinstance(row, dict)] if isinstance(selections, list) else []
        enriched: list[dict[str, Any]] = []
        for selection in selection_rows:
            odds = _selection_odds(selection)
            implied = decimal_implied_probability(odds)
            row = {
                "selectionId": selection.get("id"),
                "name": selection.get("name"),
                "resultType": selection.get("resultType"),
                "statusCode": selection.get("statusCode"),
                "decimalOdds": odds,
                "impliedProbability": implied,
                "normalizedImpliedProbability": None,
            }
            enriched.append(row)
            all_selections.append(row)

        no_vig: dict[str, Any] | None = None
        if _complete_three_way_market(market, selection_rows):
            probabilities = [decimal_implied_probability(row["decimalOdds"]) for row in enriched]
            total = sum(probability for probability in probabilities if probability is not None)
            for row, probability in zip(enriched, probabilities, strict=True):
                row["normalizedImpliedProbability"] = probability / total if probability is not None else None
            no_vig = {
                "method": "proportional normalization of complete home/draw/away outcomes",
                "rawImpliedProbabilitySum": total,
                "overround": total - 1.0,
                "overroundPercent": (total - 1.0) * 100.0,
            }

        market_rows.append(
            {
                "marketId": market.get("id"),
                "name": market.get("name"),
                "statusCode": market.get("statusCode"),
                "marketSort": market.get("marketSort"),
                "selectionCount": len(selection_rows),
                "selections": enriched,
                "noVig": no_vig,
            }
        )

    return {
        "marketCount": len(markets),
        "selectionCount": len(all_selections),
        "pricedSelectionCount": sum(row["impliedProbability"] is not None for row in all_selections),
        "activePricedSelectionCount": sum(
            row["impliedProbability"] is not None and row["statusCode"] == "A" for row in all_selections
        ),
        "suspendedPricedSelectionCount": sum(
            row["impliedProbability"] is not None and row["statusCode"] == "S" for row in all_selections
        ),
        "missingOrInvalidPriceCount": sum(row["impliedProbability"] is None for row in all_selections),
        "marketStatusCounts": _status_counts(markets),
        "selectionStatusCounts": _status_counts(all_selections),
        "retrievedAt": retrieved_at.isoformat() if isinstance(retrieved_at, datetime) else retrieved_at,
        "snapshotFreshness": snapshot_freshness(
            retrieved_at, now=now, max_age_seconds=max_age_seconds
        ),
        "markets": market_rows,
    }


def extract_sports_events(payload: Any) -> list[dict[str, Any]]:
    """Flatten the grouped event response from ``sportsbet_competition_matches``."""
    found: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if "startTime" in value and "name" in value and ("id" in value or "eventId" in value):
                found.append(value)
                return
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)

    visit(payload)
    return found


def _timezone_for(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        # Brisbane has no daylight-saving transitions. This fallback keeps the default
        # usable on Windows systems without an installed IANA timezone database.
        if name == "Australia/Brisbane":
            return timezone(timedelta(hours=10), "AEST")
        raise


def filter_events_for_local_date(
    payload: Any,
    local_date: date | str,
    *,
    timezone_name: str = "Australia/Brisbane",
) -> list[dict[str, Any]]:
    """Keep events whose Unix ``startTime`` falls on the requested local calendar date."""
    target = date.fromisoformat(local_date) if isinstance(local_date, str) else local_date
    zone = _timezone_for(timezone_name)
    matches: list[dict[str, Any]] = []
    for event in extract_sports_events(payload):
        try:
            start = datetime.fromtimestamp(float(event["startTime"]), tz=zone)
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if start.date() == target:
            matches.append(event)
    return matches


def analyse_snapshot_directory(
    directory: Path,
    *,
    now: datetime | None = None,
    max_age_seconds: float = 900,
) -> dict[str, Any]:
    """Analyse a directory created from raw event-market responses and its manifest."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Snapshot directory has no manifest.json: {directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events: list[dict[str, Any]] = []
    for request in manifest.get("events", []):
        record: dict[str, Any] = {
            "eventId": request.get("eventId"),
            "endpoint": request.get("endpoint"),
            "httpStatus": request.get("httpStatus"),
            "retrievedAt": request.get("retrievedAt"),
            "rawFile": request.get("rawFile"),
        }
        if request.get("httpStatus") != 200 or not request.get("rawFile"):
            record["requestError"] = request.get("error") or "Market request did not return HTTP 200."
        else:
            raw_path = directory / request["rawFile"]
            if not raw_path.is_file():
                record["requestError"] = f"Raw response file is missing: {request['rawFile']}"
            else:
                try:
                    payload = json.loads(raw_path.read_text(encoding="utf-8"))
                    record["analysis"] = analyse_markets(
                        payload,
                        retrieved_at=request.get("retrievedAt"),
                        now=now,
                        max_age_seconds=max_age_seconds,
                    )
                except (OSError, json.JSONDecodeError, ValueError) as error:
                    record["requestError"] = f"Could not analyse raw response: {error}"
        events.append(record)
    return {
        "schemaVersion": 1,
        "provider": manifest.get("provider", "Sportsbet"),
        "fixtureDate": manifest.get("fixtureDate"),
        "fixtureTimezone": manifest.get("fixtureTimezone", "Australia/Brisbane"),
        "generatedAt": (now or datetime.now(UTC)).isoformat(),
        "maxSnapshotAgeSeconds": max_age_seconds,
        "events": events,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse saved, read-only Sportsbet event-market responses.")
    parser.add_argument("input", type=Path, help="Raw markets JSON file or snapshot directory with manifest.json")
    parser.add_argument("--retrieved-at", help="Timezone-aware retrieval timestamp for a single JSON file")
    parser.add_argument("--max-age-minutes", type=float, default=15.0)
    parser.add_argument("--output", type=Path, help="Write the enriched JSON report to this file")
    args = parser.parse_args(argv)
    if args.max_age_minutes < 0:
        parser.error("--max-age-minutes must be zero or greater")

    if args.input.is_dir():
        report = analyse_snapshot_directory(
            args.input, max_age_seconds=args.max_age_minutes * 60.0
        )
    else:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = {
            "schemaVersion": 1,
            "provider": "Sportsbet",
            "generatedAt": datetime.now(UTC).isoformat(),
            "analysis": analyse_markets(
                payload,
                retrieved_at=args.retrieved_at,
                max_age_seconds=args.max_age_minutes * 60.0,
            ),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
