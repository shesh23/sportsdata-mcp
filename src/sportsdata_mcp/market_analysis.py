"""Read-only helpers for analysing Sportsbet market snapshots.

This module consumes responses from the existing Sportsbet read tools. It never makes
HTTP requests and contains no betting, account, or wallet operations.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
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

UEFA_COMPETITION_ALIASES = {
    "UEFA Champions League": {"uefa champions league", "champions league", "ucl"},
    "UEFA Europa League": {"uefa europa league", "europa league"},
    "UEFA Conference League": {"uefa conference league", "conference league"},
    "UEFA Super Cup": {"uefa super cup", "super cup"},
}

DOMESTIC_CUP_ALIASES = {
    "English FA Cup": {"english fa cup", "fa cup"},
    "English EFL Cup": {"english football league cup", "efl cup", "carabao cup", "english league cup"},
    "FA Community Shield": {"fa community shield", "community shield"},
    "Spanish Copa del Rey": {"spanish copa del rey", "copa del rey"},
    "Spanish Supercopa de España": {"spanish supercopa de espana", "supercopa de espana", "spanish super cup"},
    "German DFB-Pokal": {"german dfb pokal", "dfb pokal"},
    "German DFL-Supercup": {"german dfl supercup", "dfl supercup", "german super cup"},
    "Italian Coppa Italia": {"italian coppa italia", "coppa italia"},
    "Italian Supercoppa Italiana": {"italian supercoppa italiana", "supercoppa italiana"},
    "French Coupe de France": {"french coupe de france", "coupe de france"},
    "French Trophée des Champions": {"french trophee des champions", "trophee des champions"},
}

TARGET_FOOTBALL_COMPETITION_ALIASES = {
    **TOP_FIVE_LEAGUE_ALIASES,
    **UEFA_COMPETITION_ALIASES,
    **DOMESTIC_CUP_ALIASES,
}
TARGET_FOOTBALL_COMPETITIONS = tuple(TARGET_FOOTBALL_COMPETITION_ALIASES)


def _normalise_competition_name(value: str) -> str:
    """Fold accents and punctuation so official display-name variants match safely."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in ascii_text).split())


def _select_competitions(
    payload: Any,
    aliases_by_competition: dict[str, set[str]],
    *,
    output_key: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TypeError("Expected a Sportsbet navigation object.")

    roots = payload.get("navItems", payload.get("nav"))
    if not isinstance(roots, list):
        raise TypeError("Expected Sportsbet navigation items.")

    normalised_aliases = {
        canonical: {_normalise_competition_name(alias) for alias in aliases}
        for canonical, aliases in aliases_by_competition.items()
    }
    matches: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if not isinstance(value, dict):
            return

        name = value.get("name")
        if isinstance(name, str) and (value.get("idType") == "competition" or "competitionId" in value):
            normalized_name = _normalise_competition_name(name)
            for canonical, aliases in normalised_aliases.items():
                if normalized_name not in aliases:
                    continue
                competition_id = value.get("id") if value.get("idType") == "competition" else value.get("competitionId")
                if competition_id is None:
                    competition_id = value.get("competitionId", value.get("id"))
                if competition_id is not None and canonical not in matches:
                    matches[canonical] = {
                        output_key: canonical,
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
        and _normalise_competition_name(node["name"]) in {"soccer", "football"}
        and (node.get("idType") == "class" or "classId" in node or node.get("name") == "Soccer")
    ]
    if not soccer_roots:
        raise ValueError("Sportsbet navigation did not contain a Soccer/Football class.")
    for soccer in soccer_roots:
        visit(soccer.get("navItems", soccer.get("competitions", [])))

    return [matches[name] for name in aliases_by_competition if name in matches]


def select_top_five_competitions(payload: Any) -> list[dict[str, Any]]:
    """Select the five domestic leagues from Sportsbet's soccer navigation."""
    return _select_competitions(payload, TOP_FIVE_LEAGUE_ALIASES, output_key="league")


def select_target_football_competitions(payload: Any) -> list[dict[str, Any]]:
    """Select requested top-five leagues, UEFA tournaments, and domestic cups."""
    return _select_competitions(payload, TARGET_FOOTBALL_COMPETITION_ALIASES, output_key="competition")


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


def _scheduled_start_utc(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _retrieval_timing(retrieved_at: Any, scheduled_start: Any) -> dict[str, Any]:
    retrieved = _parse_timestamp(retrieved_at)
    scheduled = _scheduled_start_utc(scheduled_start)
    if retrieved is None or scheduled is None:
        return {"status": "unknown", "scheduledStartTime": scheduled.isoformat() if scheduled else None}
    after_start = retrieved.astimezone(UTC) >= scheduled
    return {
        "status": "after-scheduled-kickoff" if after_start else "before-scheduled-kickoff",
        "scheduledStartTime": scheduled.isoformat(),
        "secondsFromScheduledKickoff": (retrieved.astimezone(UTC) - scheduled).total_seconds(),
        "note": "No per-price update time is provided; post-kickoff snapshots may contain in-play or stale prices.",
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
    event_status_by_id: dict[str, dict[str, Any]] = {}
    for status_request in manifest.get("eventStatuses", []):
        if status_request.get("httpStatus") != 200 or not status_request.get("rawFile"):
            continue
        status_path = directory / status_request["rawFile"]
        try:
            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        event_status_by_id[str(status_request.get("eventId"))] = {
            "httpStatus": status_request.get("httpStatus"),
            "retrievedAt": status_request.get("retrievedAt"),
            "eventStatus": status_payload.get("eventStatus", status_payload.get("status")),
            "inPlay": status_payload.get("inPlay"),
            "suspended": status_payload.get("suspended"),
        }
    events: list[dict[str, Any]] = []
    for request in manifest.get("events", []):
        event_status = event_status_by_id.get(str(request.get("eventId")), {})
        retrieval_timing = _retrieval_timing(
            request.get("retrievedAt"), request.get("scheduledStartTime", request.get("startTime"))
        )
        record: dict[str, Any] = {
            "eventId": request.get("eventId"),
            "eventName": request.get("eventName"),
            "competition": request.get("competition"),
            "endpoint": request.get("endpoint"),
            "httpStatus": request.get("httpStatus"),
            "retrievedAt": request.get("retrievedAt"),
            "rawFile": request.get("rawFile"),
            "retrievalTiming": retrieval_timing,
            "eventStatusHttpStatus": event_status.get("httpStatus"),
            "eventStatusRetrievedAt": event_status.get("retrievedAt"),
            "eventStatus": event_status.get("eventStatus"),
            "inPlay": event_status.get("inPlay"),
            "suspended": event_status.get("suspended"),
        }
        record["eventStatusConflict"] = (
            retrieval_timing["status"] == "after-scheduled-kickoff"
            and str(event_status.get("eventStatus", "")).casefold() == "preview"
        )
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
        "fixtureDate": manifest.get("fixtureDate") or manifest.get("requestedLocalDate"),
        "fixtureTimezone": manifest.get("fixtureTimezone") or manifest.get("timezone", "Australia/Brisbane"),
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
