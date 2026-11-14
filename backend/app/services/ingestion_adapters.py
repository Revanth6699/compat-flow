"""Format-neutral catalog ingestion parsers.

Parsers return source-preserving records. They do not validate business fields,
write to the database, or infer relationships; those steps belong to the shared
mapping/validation/persistence pipeline.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from xml.etree.ElementTree import iterparse

from defusedxml.ElementTree import fromstring

MAX_RECORDS = 10_000
MAX_COLUMNS = 500
MAX_CELL_CHARS = 1_000_000


class IngestionParseError(ValueError):
    """Raised when an input cannot be parsed safely."""


@dataclass(frozen=True)
class SourceRecord:
    values: dict[str, Any]
    source_location: str
    source_key: str | None = None


@dataclass(frozen=True)
class ParsedSource:
    format: str
    records: list[SourceRecord]
    headers: list[str]
    metadata: dict[str, Any]


def _clean_headers(headers: list[Any]) -> list[str]:
    cleaned = [str(value).strip() if value is not None else "" for value in headers]
    if not cleaned or any(not value for value in cleaned):
        raise IngestionParseError("The source contains an empty or missing header.")
    if len(cleaned) > MAX_COLUMNS:
        raise IngestionParseError(f"Input exceeds the {MAX_COLUMNS} column limit.")
    normalized = [re.sub(r"\s+", " ", value).casefold() for value in cleaned]
    if len(normalized) != len(set(normalized)):
        raise IngestionParseError("Duplicate headers are not allowed.")
    return cleaned


def _record(values: dict[str, Any], location: str, key: Any = None) -> SourceRecord:
    for name, value in values.items():
        if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
            raise IngestionParseError(f"Value in '{name}' exceeds the maximum cell size.")
    return SourceRecord(values=values, source_location=location,
                        source_key=None if key is None else str(key))


def parse_csv(data: bytes, *, max_records: int = MAX_RECORDS) -> ParsedSource:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestionParseError("CSV must be UTF-8 encoded.") from None
    sample = text[:65_536]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        first = next((line for line in sample.splitlines() if line.strip()), "")
        counts = {char: first.count(char) for char in ",;\t|"}
        delimiter = max(counts, key=counts.get) if max(counts.values(), default=0) else ","
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        raw_headers = next(reader, None)
        if not raw_headers:
            raise IngestionParseError("CSV header row is missing.")
        headers = _clean_headers(raw_headers)
        records = []
        for row_number, row in enumerate(reader, start=2):
            if not row or all(not str(value).strip() for value in row):
                continue
            if len(row) != len(headers):
                raise IngestionParseError(
                    f"CSV row {row_number} has {len(row)} cells; expected {len(headers)}."
                )
            if len(records) >= max_records:
                raise IngestionParseError(f"Input exceeds the {max_records:,}-record limit.")
            records.append(_record(dict(zip(headers, row)), f"row:{row_number}"))
    except csv.Error as exc:
        raise IngestionParseError(f"Malformed CSV: {exc}") from None
    return ParsedSource("csv", records, headers, {"delimiter": delimiter})


def parse_excel(data: bytes, extension: str, *, sheet_name: str | None = None,
                header_row: int = 1, max_records: int = MAX_RECORDS) -> ParsedSource:
    ext = extension.lower().lstrip(".")
    if ext not in {"xlsx", "xls"}:
        raise IngestionParseError("Excel format must be .xlsx or .xls.")
    if header_row < 1:
        raise IngestionParseError("header_row must be 1 or greater.")
    records: list[SourceRecord] = []
    if ext == "xlsx":
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise IngestionParseError(f"Unable to read XLSX workbook: {type(exc).__name__}.") from None
        try:
            if sheet_name and sheet_name not in workbook.sheetnames:
                raise IngestionParseError("Requested worksheet does not exist.")
            sheet = workbook[sheet_name] if sheet_name else workbook[workbook.sheetnames[0]]
            iterator = sheet.iter_rows(values_only=True)
            for _ in range(header_row - 1):
                next(iterator, None)
            raw_headers = next(iterator, None)
            if raw_headers is None:
                raise IngestionParseError("Worksheet header row is missing.")
            headers = _clean_headers(list(raw_headers))
            for row_number, row in enumerate(iterator, start=header_row + 1):
                values = list(row[:len(headers)])
                if len(values) < len(headers):
                    values.extend([None] * (len(headers) - len(values)))
                if all(value is None or str(value).strip() == "" for value in values):
                    continue
                if len(records) >= max_records:
                    raise IngestionParseError(f"Input exceeds the {max_records:,}-record limit.")
                records.append(_record(dict(zip(headers, values)),
                                       f"sheet:{sheet.title}!row:{row_number}"))
            selected_sheet = sheet.title
        finally:
            workbook.close()
    else:
        try:
            import xlrd
            workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
        except Exception as exc:
            raise IngestionParseError(f"Unable to read XLS workbook: {type(exc).__name__}.") from None
        try:
            if sheet_name:
                try:
                    sheet = workbook.sheet_by_name(sheet_name)
                except xlrd.XLRDError:
                    raise IngestionParseError("Requested worksheet does not exist.") from None
            else:
                sheet = workbook.sheet_by_index(0)
            if sheet.nrows < header_row:
                raise IngestionParseError("Worksheet header row is missing.")
            headers = _clean_headers(sheet.row_values(header_row - 1))
            for index in range(header_row, sheet.nrows):
                values = sheet.row_values(index)[:len(headers)]
                if all(value is None or str(value).strip() == "" for value in values):
                    continue
                if len(records) >= max_records:
                    raise IngestionParseError(f"Input exceeds the {max_records:,}-record limit.")
                records.append(_record(dict(zip(headers, values)),
                                       f"sheet:{sheet.name}!row:{index + 1}"))
            selected_sheet = sheet.name
        finally:
            workbook.release_resources()
    return ParsedSource(ext, records, headers,
                        {"sheet": selected_sheet, "header_row": header_row})


def _flatten_json_object(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            flattened.update(_flatten_json_object(item, name))
        else:
            flattened[name] = item
    return flattened


def parse_json(data: bytes, *, record_path: str | None = None,
               max_records: int = MAX_RECORDS) -> ParsedSource:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IngestionParseError("JSON must be valid UTF-8 JSON.") from None
    if record_path:
        current: Any = payload
        for part in record_path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise IngestionParseError("Configured JSON record path does not exist.")
            current = current[part]
        payload = current
    if isinstance(payload, dict):
        candidates = [value for value in payload.values()
                      if isinstance(value, list) and (not value or isinstance(value[0], dict))]
        if len(candidates) == 1:
            payload = candidates[0]
        else:
            payload = [payload]
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise IngestionParseError("JSON must contain an object or an array of objects; configure record_path for nested arrays.")
    if len(payload) > max_records:
        raise IngestionParseError(f"Input exceeds the {max_records:,}-record limit.")
    records = [_record(_flatten_json_object(item), f"item:{index}", item.get("id"))
               for index, item in enumerate(payload, start=1)]
    headers = sorted({key for item in records for key in item.values})
    if len(headers) > MAX_COLUMNS:
        raise IngestionParseError(f"Input exceeds the {MAX_COLUMNS} column limit.")
    return ParsedSource("json", records, headers, {"record_path": record_path})


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xml(data: bytes, *, record_tag: str | None = None,
              max_records: int = MAX_RECORDS) -> ParsedSource:
    try:
        root = fromstring(data)
    except Exception:
        raise IngestionParseError("XML is malformed or contains unsafe constructs.") from None
    candidates: dict[str, list[Any]] = {}
    for child in list(root):
        candidates.setdefault(_local_name(child.tag), []).append(child)
    selected_tag = record_tag
    if selected_tag is None:
        repeated = [name for name, elements in candidates.items() if len(elements) > 1]
        selected_tag = repeated[0] if len(repeated) == 1 else None
    elements = candidates.get(selected_tag, []) if selected_tag else []
    if not elements and selected_tag is None and list(root):
        elements = list(root)
        selected_tag = _local_name(elements[0].tag)
    if not elements:
        raise IngestionParseError("Could not identify XML record elements; supply record_tag.")
    if len(elements) > max_records:
        raise IngestionParseError(f"Input exceeds the {max_records:,}-record limit.")
    records = []
    for index, element in enumerate(elements, start=1):
        values = {f"@{_local_name(key)}": value for key, value in element.attrib.items()}
        for child in list(element):
            name = _local_name(child.tag)
            value = child.text.strip() if child.text else ""
            if list(child):
                nested = { _local_name(grand.tag): (grand.text or "").strip()
                           for grand in list(child) }
                for key, nested_value in nested.items():
                    values[f"{name}.{key}"] = nested_value
            elif name in values:
                raise IngestionParseError(f"XML record contains repeated field '{name}'; repeated values need an explicit mapping.")
            else:
                values[name] = value
        records.append(_record(values, f"element:{selected_tag}[{index}]", element.attrib.get("id")))
    headers = sorted({key for item in records for key in item.values})
    if len(headers) > MAX_COLUMNS:
        raise IngestionParseError(f"Input exceeds the {MAX_COLUMNS} column limit.")
    return ParsedSource("xml", records, headers, {"record_tag": selected_tag})


def parse_source(data: bytes, filename: str, *, sheet_name: str | None = None,
                 header_row: int = 1, json_record_path: str | None = None,
                 xml_record_tag: str | None = None,
                 max_records: int = MAX_RECORDS) -> ParsedSource:
    """Dispatch a bounded file upload to its parser based on its extension."""
    extension = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if not extension:
        raise IngestionParseError("A file extension is required.")
    if extension == ".csv":
        return parse_csv(data, max_records=max_records)
    if extension in {".xlsx", ".xls"}:
        return parse_excel(data, extension, sheet_name=sheet_name,
                           header_row=header_row, max_records=max_records)
    if extension == ".json":
        return parse_json(data, record_path=json_record_path, max_records=max_records)
    if extension == ".xml":
        return parse_xml(data, record_tag=xml_record_tag, max_records=max_records)
    raise IngestionParseError("Unsupported file type. Supported files: CSV, XLSX, XLS, JSON, XML.")
