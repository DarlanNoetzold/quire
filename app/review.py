import csv
import json
import re
from collections import defaultdict

from . import db


NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?P<number>[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?)(?P<space>\s*)(?P<unit>%|percent(?:age)?|participants?|subjects?|patients?|samples?|instances?|records?|folds?|ms|milliseconds?|s|seconds?|minutes?|hours?|days?|years?|MB|GB|TB|KB|kB|mW|W|kW|GHz|MHz|kHz|Hz|°C|C|F1|AUC|AUROC|accuracy|precision|recall|RMSE|MAE|MSE|ROUGE(?:-\d)?|BLEU)?(?!\w)",
    re.IGNORECASE,
)


def extract_numeric_evidence(summary):
    """Extract explicit numeric mentions; output is a review aid, not verified data."""
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except (TypeError, ValueError):
            summary = {"summary": summary}
    if not isinstance(summary, dict):
        return []

    results = []
    seen_values = set()
    for field, original_text in summary.items():
        if not isinstance(original_text, str):
            continue
        text = original_text
        field_name = str(field)
        if field_name.casefold() in {"results", "result", "findings", "key findings", "resultados", "achados"}:
            text = re.sub(r"\b(?:including|include|includes)\s+\d[\d,]*(?:\.\d+)?\b", "", text, flags=re.IGNORECASE)
        for match in NUMBER_PATTERN.finditer(text):
            raw = match.group("number").replace(",", "")
            try:
                value = float(raw) if any(c in raw for c in ".eE") else int(raw)
            except ValueError:
                continue
            if abs(value) > 1e12:
                continue
            unit = _normalize_unit(match.group("unit") or "")
            if not unit and text[match.end():match.end() + 6].lower().startswith("-fold"):
                unit = "folds"
            unique_key = (value, unit)
            if unique_key in seen_values:
                continue
            seen_values.add(unique_key)
            evidence = re.sub(r"\s+", " ", original_text[max(0, match.start() - 90):min(len(original_text), match.end() + 90)]).strip()
            results.append({
                "campo": field_name, "valor": value, "unidade": unit,
                "evidencia": evidence, "pagina": None,
            })
    return results


def _normalize_unit(unit):
    normalized = unit.strip()
    if normalized.lower() in {"percent", "percentage"}:
        return "%"
    if normalized.lower() in {"participant", "participants", "subject", "subjects", "patient", "patients"}:
        return "participants"
    if normalized.lower() in {"sample", "samples", "instance", "instances", "record", "records"}:
        return "samples"
    if normalized.lower() == "fold":
        return "folds"
    if normalized.lower() in {"ms", "millisecond", "milliseconds"}:
        return "ms"
    return normalized


def write_csv(file_obj, rows):
    writer = csv.writer(file_obj)
    writer.writerow(["artigo_id", "artigo", "ano", "campo", "valor", "unidade", "evidencia", "pagina"])
    for row in rows:
        writer.writerow([
            row.get("artigo_id"), row.get("titulo", ""), row.get("ano"),
            row.get("campo", ""), row.get("valor", ""), row.get("unidade", ""),
            row.get("evidencia", ""), row.get("pagina") or "",
        ])


def create_review(title, description=""):
    return db.criar_revisao(title, description)


def list_reviews():
    return db.listar_revisoes()


def review_details(review_id):
    return {
        "revisao": db.get_revisao(review_id),
        "artigos": db.listar_artigos_revisao(review_id),
        "extracoes": db.listar_extracoes_revisao(review_id),
    }


def extraction_chart_data(review_id):
    rows = db.listar_extracoes_revisao(review_id)
    grouped = defaultdict(lambda: {"labels": [], "values": [], "unit": ""})
    for row in rows:
        try:
            value = float(row["valor"])
        except (TypeError, ValueError):
            continue
        key = (row.get("campo", ""), row.get("unidade", ""))
        group = grouped[key]
        group["labels"].append(row.get("titulo", f"Article {row.get('artigo_id')}"))
        group["values"].append(value)
        group["unit"] = key[1]
    return [
        {"campo": field, "unidade": unit, **data}
        for (field, unit), data in sorted(grouped.items()) if data["values"]
    ]


def csv_filename(review_id):
    return f"quire-review-{review_id}-extractions.csv"
