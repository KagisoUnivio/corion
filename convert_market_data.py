#!/usr/bin/env python3
"""Convert this SSMS market-data export using only the Python standard library."""

import argparse
import codecs
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import os
import re
import sqlite3
from tempfile import TemporaryDirectory

COLUMNS = {
    "Instruments": (
        "InstrumentId", "Code", "Name", "AssetClass", "Exchange",
        "Currency", "QuoteUnit", "ContractSize",
    ),
    "DailyPrices": ("InstrumentId", "PriceDate", "ClosePrice", "AccruedPer100", "Source"),
}
SCHEMA = """
CREATE TABLE Instruments (
    InstrumentId INTEGER PRIMARY KEY,
    Code TEXT NOT NULL,
    Name TEXT,
    AssetClass TEXT,
    Exchange TEXT,
    Currency TEXT,
    QuoteUnit TEXT,
    ContractSize NUMERIC
);
CREATE TABLE DailyPrices (
    InstrumentId INTEGER NOT NULL REFERENCES Instruments (InstrumentId),
    PriceDate TEXT NOT NULL,
    ClosePrice NUMERIC,
    AccruedPer100 NUMERIC,
    Source TEXT,
    PRIMARY KEY (InstrumentId, PriceDate)
);
"""

INSERT = re.compile(
    r"INSERT\s+(?:INTO\s+)?\[dbo\]\.\[(?P<table>\w+)\]"
    r"\s*\((?P<columns>[^)]*)\)\s+VALUES\s*\(\s*", re.IGNORECASE
)
VALUE = re.compile(
    r"(?P<null>NULL)\b"
    r"|CAST\(\s*N?'(?P<day>[0-9]{4}-[0-9]{2}-[0-9]{2})'\s+AS\s+Date\s*\)"
    r"|CAST\(\s*(?P<decimal>[+-]?[0-9]+(?:\.[0-9]+)?)\s+AS\s+Decimal"
    r"\(\s*18\s*,\s*[46]\s*\)\s*\)"
    r"|N?'(?P<text>(?:[^']|'')*)'"
    r"|(?P<integer>[+-]?[0-9]+)", re.IGNORECASE
)
SEPARATOR = re.compile(r"\s*,\s*")
END = re.compile(r"\s*\)\s*;?\s*(?:--.*)?")
INSERT_START = re.compile(r"^\s*INSERT\b", re.IGNORECASE)
TYPES = {
    "Instruments": (int, str, str, str, str, str, str, Decimal),
    "DailyPrices": (int, date, Decimal, Decimal, str),
}
REQUIRED_FIELDS = {
    "Instruments": {"InstrumentId", "Code"},
    "DailyPrices": {"InstrumentId", "PriceDate"},
}
CONVERTERS = {
    "null": lambda _: None,
    "day": date.fromisoformat,
    "decimal": Decimal,
    "text": lambda value: value.replace("''", "'"),
    "integer": int,
}


def parse_values(sql, start, table, columns):
    """Parse a single exported row without executing any source SQL."""
    values = {}
    column_types = dict(zip(COLUMNS[table], TYPES[table]))
    for index, column in enumerate(columns):
        value = VALUE.match(sql, start)
        if not value:
            raise ValueError(f"{column} has an invalid or unfinished value")
        parsed = CONVERTERS[value.lastgroup](value[value.lastgroup])
        if parsed is None:
            if column in REQUIRED_FIELDS[table]:
                raise ValueError(f"{column} is required")
        elif not isinstance(parsed, column_types[column]):
            raise ValueError(f"{column} has the wrong value type")
        values[column] = parsed
        if index + 1 == len(columns):
            if not END.fullmatch(sql, value.end()):
                raise ValueError("row has extra data or is missing its closing parenthesis")
        else:
            separator = SEPARATOR.match(sql, value.end())
            if not separator:
                raise ValueError(f"missing separator after {column}")
            start = separator.end()
    return tuple(values[column] for column in COLUMNS[table])


def read_export(source):
    data = source.read_bytes()
    encoding = "utf-16" if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else "utf-8-sig"
    findings = []
    source_lines = data.decode(encoding).splitlines()
    for number, line in enumerate(source_lines, 1):
        if line.rstrip().upper().endswith(") ON ["):
            findings.append((number, "Rebuilt in SQLite", "SQL Server table definition has an unfinished filegroup clause."))
    inserts = [
        (number, line.lstrip())
        for number, line in enumerate(source_lines, 1)
        if INSERT_START.match(line)
    ]
    tables = {table: {} for table in COLUMNS}
    scanned = Counter()
    for number, sql in inserts:
        header = INSERT.match(sql)
        if not header or header["table"] not in COLUMNS:
            raise ValueError(f"Line {number} has an unsupported INSERT header: {sql}")
        table = header["table"]
        columns = tuple(part.strip().strip("[]") for part in header["columns"].split(","))
        if sorted(columns) != sorted(COLUMNS[table]):
            raise ValueError(f"Line {number} has unexpected columns for {table}: {columns}")
        scanned[table] += 1
        values_sql = sql[header.end():]
        repaired_name = table == "Instruments" and "N'Karoo Winemakers' Co-op'" in values_sql
        if repaired_name:
            values_sql = values_sql.replace("N'Karoo Winemakers' Co-op'", "N'Karoo Winemakers'' Co-op'")
        try:
            row = parse_values(values_sql, 0, table, columns)
        except ValueError as error:
            reason = str(error)
            if number == inserts[-1][0] and not sql.rstrip(";").endswith(")"):
                reason = f"truncated final INSERT ({reason})"
            findings.append((number, "Excluded", f"{table}: {reason}. Source values: `{values_sql}`"))
            continue

        key = row[0] if table == "Instruments" else row[:2]
        if repaired_name:
            findings.append((number, "Repaired", f"Instrument {key}: escaped the apostrophe in `Karoo Winemakers' Co-op`."))
        previous = tables[table].get(key)
        if previous is None:
            tables[table][key] = (number, row)
            continue

        previous_line, previous_row = previous
        if row == previous_row:
            label = f"Instrument {key}" if table == "Instruments" else f"Price for instrument {key[0]} on {key[1]}"
            findings.append((number, "Excluded", f"{label} duplicates line {previous_line} exactly."))
            continue
        if table == "DailyPrices":
            corrected = str(row[-1]).casefold().endswith(" (corrected)")
            previous_corrected = str(previous_row[-1]).casefold().endswith(" (corrected)")
            if corrected != previous_corrected:
                kept_line, kept_row = (number, row) if corrected else previous
                removed_line, removed_row = previous if corrected else (number, row)
                tables[table][key] = (kept_line, kept_row)
                findings.append((
                    removed_line, "Superseded",
                    f"Instrument {key[0]} on {key[1]}: replaced close {removed_row[2]} "
                    f"with {kept_row[2]} from line {kept_line}, labeled `{kept_row[-1]}`.",
                ))
                continue
        raise ValueError(f"Unresolved duplicate {table} key {key} on lines {previous_line} and {number}")

    if any(not rows for rows in tables.values()):
        raise ValueError("The export must contain data for both Instruments and DailyPrices")
    return tables, scanned, findings


def review_data(tables, findings):
    instruments = tables["Instruments"]
    prices = tables["DailyPrices"]
    prices_by_instrument = defaultdict(list)
    instrument_codes = {}

    for instrument, (line, row) in instruments.items():
        _, code, name, asset, exchange, currency, unit, size = row
        for column, value in zip(COLUMNS["Instruments"][1:-1], (code, name, asset, exchange, currency, unit)):
            if not value or not value.strip():
                findings.append((line, "Retained for review", f"Instrument {instrument} has a missing or blank {column}."))
        if size is None or size <= 0:
            findings.append((line, "Retained for review", f"Instrument {instrument} has a missing or non-positive contract size."))
        code_key = (exchange or "", code.strip().casefold())
        if code_key in instrument_codes:
            findings.append((line, "Retained for review", f"Instrument {instrument} shares code {code} on {exchange} with line {instrument_codes[code_key]}."))
        instrument_codes[code_key] = line

    for key, (line, row) in sorted(prices.items()):
        instrument, day, close, accrued, source = row
        if instrument not in instruments:
            findings.append((line, "Excluded", f"Price for instrument {instrument} on {day} has no instrument record."))
            del prices[key]
            continue
        _, code, _, asset, *_ = instruments[instrument][1]
        label = f"{code} (instrument {instrument}) on {day}"
        if close is None:
            findings.append((line, "Retained as NULL", f"{label} has a missing close."))
        elif close <= 0:
            findings.append((line, "Retained for review", f"{label} has a non-positive close of {close}."))
        if asset == "BOND" and accrued is None:
            findings.append((line, "Retained as NULL", f"{label} has missing bond accrued interest."))
        elif accrued is not None and (asset != "BOND" or accrued < 0):
            findings.append((line, "Retained for review", f"{label} has unexpected accrued interest of {accrued}."))
        if not source or not source.strip() or day.weekday() >= 5:
            findings.append((line, "Retained for review", f"{label} has a missing source or a weekend date."))
        prices_by_instrument[instrument].append((day, line, close))

    for instrument, (_, row) in instruments.items():
        series = prices_by_instrument[instrument]
        code = row[1]
        if not series:
            findings.append((instruments[instrument][0], "Retained for review", f"{code} has no price rows."))
        for (prior_day, _, prior_close), (day, line, close) in zip(series, series[1:]):
            missing_day = prior_day + timedelta(days=1)
            while missing_day < day:
                if missing_day.weekday() < 5:
                    findings.append((line, "Flagged", f"{code} has no row on weekday {missing_day} within its observed date range."))
                missing_day += timedelta(days=1)
            if close is not None and prior_close and abs(close - prior_close) / abs(prior_close) >= Decimal("0.20"):
                findings.append((line, "Retained for review", f"{code} moved from {prior_close} on {prior_day} to {close} on {day}."))


def sqlite_values(row):
    # Bind decimal strings to NUMERIC columns for SQLite's numeric affinity.
    # ISO date strings retain chronological sort order in TEXT columns.
    return tuple(str(value) if isinstance(value, (Decimal, date)) else value for value in row)


def verify(db, tables):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("SQLite foreign key check failed")
    for table, rows in tables.items():
        if db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] != len(rows):
            raise ValueError(f"Unexpected row count in {table}")


def write_report(path, source, tables, scanned, findings):
    lines = [
        "# Market data quality report", "",
        f"Source file `{source.name}`. Line numbers refer to the source export.", "",
        "| Table | Source INSERTs | SQLite rows | Excluded |",
        "| --- | ---: | ---: | ---: |",
    ]
    for table, rows in tables.items():
        lines.append(f"| {table} | {scanned[table]} | {len(rows)} | {scanned[table] - len(rows)} |")
    lines.extend([
        "", "## Record-level findings", "",
        "| Source line | Action | Details |",
        "| ---: | --- | --- |",
    ])
    for line, action, detail in sorted(findings):
        lines.append(f"| {line} | {action} | {detail.replace('|', '&#124;')} |")
    lines.extend([
        "", "## Conversion and checks", "",
        "- Rebuilt both tables and primary keys in SQLite, bypassing SQL Server directives and storage options. Added a foreign key from prices to instruments.",
        "- Stored dates as ISO text and decimals in SQLite NUMERIC columns, which can use floating-point storage. Kept each instrument's original quote unit.",
        "- Checked metadata completeness, duplicate codes by exchange, contract sizes, date validity, weekend dates, weekday gaps within each instrument's observed range, missing sources and closes, non-positive prices, accrued interest by asset class, and moves of 20% or more between adjacent observations. The weekday check uses weekdays without an exchange holiday calendar.",
        "- Verified row counts, database integrity and foreign keys. Loaded the generated SQL into a fresh SQLite database and compared its rows to the generated database.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert(source, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ("market_data.sqlite", "market_data_sqlite.sql", "market_data_quality.md")
    for name in names:
        output = output_dir / name
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"{output} already exists. Choose a new --output-dir.")

    tables, scanned, findings = read_export(source)
    review_data(tables, findings)
    with TemporaryDirectory(dir=output_dir) as work:
        staging = Path(work)
        database, script, report = (staging / name for name in names)
        with closing(sqlite3.connect(database)) as db, closing(sqlite3.connect(":memory:")) as replay:
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                db.executescript(SCHEMA)
                for table, rows in tables.items():
                    placeholders = ", ".join("?" for _ in COLUMNS[table])
                    db.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})",
                        (sqlite_values(row) for _, row in rows.values()),
                    )
            verify(db, tables)
            dump = list(db.iterdump())
            with script.open("w", encoding="utf-8") as sql:
                sql.write("PRAGMA foreign_keys = ON;\nBEGIN TRANSACTION;\n" + SCHEMA)
                for table in tables:
                    prefix = f'INSERT INTO "{table}"'
                    for statement in dump:
                        if statement.startswith(prefix):
                            sql.write(statement + "\n")
                sql.write("COMMIT;\n")
            replay.executescript(script.read_text(encoding="utf-8"))
            verify(replay, tables)
            for table in tables:
                query = f"SELECT * FROM {table} ORDER BY 1, 2"
                if db.execute(query).fetchall() != replay.execute(query).fetchall():
                    raise ValueError(f"SQL replay changed values in {table}")
        write_report(report, source, tables, scanned, findings)
        published = []
        try:
            for name in names:
                output = output_dir / name
                os.link(staging / name, output)
                published.append(output)
        except OSError:
            for output in published:
                output.unlink()
            raise

    for table, rows in tables.items():
        print(f"{table}: imported {len(rows)} of {scanned[table]} source records")
    for name in names:
        print(output_dir / name)


def main():
    default_source = Path(__file__).resolve().with_name("market_data.sql")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=default_source)
    parser.add_argument("--output-dir", type=Path, help="defaults to the source file's directory")
    args = parser.parse_args()
    try:
        convert(args.source, args.output_dir or args.source.parent)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Conversion failed: {error}\n")


if __name__ == "__main__":
    main()
