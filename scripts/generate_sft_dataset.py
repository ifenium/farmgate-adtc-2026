#!/usr/bin/env python3
"""Generate the agriculture SFT dataset from WFP VAM Global Food Prices CSVs.

Five generator families, gold answers computed by arithmetic over the raw
CSV rows (never hand-written or LLM-generated). See:
  milestones/02-domain-and-dataset-design.md  (approved schema)

Deliberate design point: abstention_negative prompts are phrased IDENTICALLY
to state_at_time prompts (same template). The model has to recognize the
absence of a training signal on its own — it must not learn to keyword-spot
a differently-worded "abstention question."
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd

SEED = 42
DATA_DIR = Path("/Users/Apple/Documents/hack/data")
OUT_DIR = Path("/Users/Apple/Documents/hack/dataset")
OUT_DIR.mkdir(exist_ok=True)

CUTOFF_YEAR_MONTH = (2024, 12)  # last month present in the training corpus

AFRICAN_ISO3_TO_NAME = {
    "DZA": "Algeria", "AGO": "Angola", "BEN": "Benin", "BWA": "Botswana",
    "BFA": "Burkina Faso", "BDI": "Burundi", "CPV": "Cabo Verde",
    "CMR": "Cameroon", "CAF": "Central African Republic", "TCD": "Chad",
    "COM": "Comoros", "COG": "Congo", "COD": "Democratic Republic of the Congo",
    "CIV": "Côte d'Ivoire", "DJI": "Djibouti", "EGY": "Egypt",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "SWZ": "Eswatini",
    "ETH": "Ethiopia", "GAB": "Gabon", "GMB": "Gambia", "GHA": "Ghana",
    "GIN": "Guinea", "GNB": "Guinea-Bissau", "KEN": "Kenya", "LSO": "Lesotho",
    "LBR": "Liberia", "LBY": "Libya", "MDG": "Madagascar", "MWI": "Malawi",
    "MLI": "Mali", "MRT": "Mauritania", "MUS": "Mauritius", "MAR": "Morocco",
    "MOZ": "Mozambique", "NAM": "Namibia", "NER": "Niger", "NGA": "Nigeria",
    "RWA": "Rwanda", "STP": "São Tomé and Príncipe", "SEN": "Senegal",
    "SYC": "Seychelles", "SLE": "Sierra Leone", "SOM": "Somalia",
    "ZAF": "South Africa", "SSD": "South Sudan", "SDN": "Sudan",
    "TZA": "Tanzania", "TGO": "Togo", "TUN": "Tunisia", "UGA": "Uganda",
    "ZMB": "Zambia", "ZWE": "Zimbabwe",
}

ABSTAIN_GAP_TEMPLATES = [
    "No reported retail price for {commodity} in {market} in {month_year}.",
    "Data unavailable: WFP VAM has no retail price for {commodity} in {market} for {month_year}.",
    "I don't have a retail price for {commodity} in {market} in {month_year}.",
]
ABSTAIN_CUTOFF_TEMPLATES = [
    "No price data available — {month_year} is beyond this dataset's coverage (through December 2024).",
    "I don't have data for {month_year}; price coverage only extends through December 2024.",
    "Data unavailable: {month_year} is after the most recent period in the training data (December 2024).",
]


def month_year(ts: pd.Timestamp) -> str:
    return ts.strftime("%B %Y")


def country_name(iso3: str) -> str:
    return AFRICAN_ISO3_TO_NAME.get(iso3, iso3)


def load_year(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[df["countryiso3"].isin(AFRICAN_ISO3_TO_NAME.keys())]
    df = df[df["pricetype"] == "Retail"]
    df = df.dropna(subset=["price"])
    df = df[df["price"] > 0]
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["market", "commodity", "date", "pricetype"])
    return df


def load_corpus() -> pd.DataFrame:
    df23 = load_year(DATA_DIR / "wfp_2023.csv")
    df24 = load_year(DATA_DIR / "wfp_2024.csv")
    df = pd.concat([df23, df24], ignore_index=True)
    return df


def source_row(row) -> dict:
    return {
        "market": row["market"],
        "commodity": row["commodity"],
        "date": row["date"].strftime("%Y-%m-%d"),
        "price": float(row["price"]),
        "usdprice": None if pd.isna(row.get("usdprice")) else float(row["usdprice"]),
        "currency": row["currency"],
        "unit": row["unit"],
        "pricetype": row["pricetype"],
        "priceflag": row.get("priceflag"),
    }


def classify_change(pct: float) -> str:
    if pct > 1.0:
        return "rise"
    if pct < -1.0:
        return "fall"
    return "flat"


def change_phrase(cls: str) -> str:
    return {"rise": "Rose", "fall": "Fell", "flat": "Stayed about the same"}[cls]


# ---------------------------------------------------------------------------
# Family 1: state_at_time
# ---------------------------------------------------------------------------

def gen_state_at_time(df: pd.DataFrame, rng: random.Random, n_local: int, n_usd: int) -> list[dict]:
    examples = []
    pool = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    seq = 0
    picked = pool.iloc[: n_local + n_usd]
    local_rows = picked.iloc[:n_local]
    usd_rows = picked.iloc[n_local : n_local + n_usd]
    # usd subtype needs non-null usdprice; refill from remaining pool if any sampled row lacks it.
    remaining = pool.iloc[n_local + n_usd :].iterrows()
    usd_rows_list = list(usd_rows.iterrows())
    fixed_usd_rows = []
    for idx, row in usd_rows_list:
        r = row
        while pd.isna(r["usdprice"]):
            idx2, r = next(remaining)
        fixed_usd_rows.append(r)

    for _, row in local_rows.iterrows():
        my = month_year(row["date"])
        country = country_name(row["countryiso3"])
        prompt = (
            f"What was the retail price of {row['commodity']} in {row['market']}, "
            f"{country} in {my}?"
        )
        gold = f"{row['price']:.2f} {row['currency']} per {row['unit']}"
        examples.append({
            "id": f"agmkt-sat-{seq:04d}", "generator_family": "state_at_time",
            "generator_subtype": "local_currency", "country_iso3": row["countryiso3"],
            "market": [row["market"]], "commodity": row["commodity"], "unit": row["unit"],
            "currency": row["currency"], "pricetype": row["pricetype"],
            "query_period": {"month_year": my}, "prompt": prompt, "gold_answer": gold,
            "gold_value": float(row["price"]), "answer_type": "numeric",
            "source_rows": [source_row(row)],
        })
        seq += 1

    for row in fixed_usd_rows:
        my = month_year(row["date"])
        country = country_name(row["countryiso3"])
        prompt = (
            f"What was the retail price of {row['commodity']} in {row['market']}, "
            f"{country} in {my}, in US dollars?"
        )
        gold = f"{row['usdprice']:.2f} USD per {row['unit']}"
        examples.append({
            "id": f"agmkt-sat-{seq:04d}", "generator_family": "state_at_time",
            "generator_subtype": "usd_converted", "country_iso3": row["countryiso3"],
            "market": [row["market"]], "commodity": row["commodity"], "unit": row["unit"],
            "currency": "USD", "pricetype": row["pricetype"],
            "query_period": {"month_year": my}, "prompt": prompt, "gold_answer": gold,
            "gold_value": float(row["usdprice"]), "answer_type": "numeric",
            "source_rows": [source_row(row)],
        })
        seq += 1

    return examples


# ---------------------------------------------------------------------------
# Family 2: trend_change  /  Family 3: yoy_comparison (shared two-point logic)
# ---------------------------------------------------------------------------

def two_point_examples(
    df: pd.DataFrame, rng: random.Random, n: int, family: str,
    same_month_only: bool, id_prefix: str,
) -> list[dict]:
    groups = df.groupby(["countryiso3", "market", "commodity"])
    candidates = []
    for (iso3, market, commodity), g in groups:
        if len(g) < 2:
            continue
        g = g.sort_values("date")
        if same_month_only:
            by_month = {}
            for _, r in g.iterrows():
                by_month.setdefault(r["date"].month, []).append(r)
            for month, rows in by_month.items():
                years = sorted({r["date"].year for r in rows})
                if len(years) < 2:
                    continue
                r1 = next(r for r in rows if r["date"].year == years[0])
                r2 = next(r for r in rows if r["date"].year == years[-1])
                candidates.append((r1, r2))
        else:
            rows = list(g.iterrows())
            if len(rows) >= 2:
                candidates.append((rows[0][1], rows[-1][1]))

    rng.shuffle(candidates)
    examples = []
    seq = 0
    for r1, r2 in candidates:
        if len(examples) >= n:
            break
        if r1["unit"] != r2["unit"] or r1["currency"] != r2["currency"]:
            continue
        if r1["price"] <= 0:
            continue
        pct = (r2["price"] - r1["price"]) / r1["price"] * 100.0
        cls = classify_change(pct)
        my1, my2 = month_year(r1["date"]), month_year(r2["date"])
        country = country_name(r1["countryiso3"])
        if family == "trend_change":
            prompt = (
                f"Did the retail price of {r1['commodity']} in {r1['market']}, {country} "
                f"rise, fall, or stay about the same between {my1} and {my2}, and by how much?"
            )
        else:
            prompt = (
                f"How does the {my2} retail price of {r1['commodity']} in {r1['market']}, "
                f"{country} compare to {my1}?"
            )
        gold = (
            f"{change_phrase(cls)} {abs(pct):.1f}% "
            f"({r1['price']:.2f} → {r2['price']:.2f} {r1['currency']} per {r1['unit']})."
        )
        examples.append({
            "id": f"agmkt-{id_prefix}-{seq:04d}", "generator_family": family,
            "generator_subtype": cls, "country_iso3": r1["countryiso3"],
            "market": [r1["market"]], "commodity": r1["commodity"], "unit": r1["unit"],
            "currency": r1["currency"], "pricetype": r1["pricetype"],
            "query_period": {"period_1": my1, "period_2": my2}, "prompt": prompt,
            "gold_answer": gold,
            "gold_value": {"a": float(r1["price"]), "b": float(r2["price"]), "pct": round(pct, 2)},
            "answer_type": "classification",
            "source_rows": [source_row(r1), source_row(r2)],
        })
        seq += 1
    return examples


# ---------------------------------------------------------------------------
# Family 4: cross_market_ranking
# ---------------------------------------------------------------------------

def gen_cross_market_ranking(df: pd.DataFrame, rng: random.Random, n: int) -> list[dict]:
    groups = df.groupby(["countryiso3", "commodity", "date"])
    candidates = []
    for (iso3, commodity, date), g in groups:
        g = g.drop_duplicates(subset=["market"])
        if g["market"].nunique() < 3:
            continue
        if g["unit"].nunique() != 1 or g["currency"].nunique() != 1:
            continue
        candidates.append((iso3, commodity, date, g))
    rng.shuffle(candidates)

    variants = ["lowest", "highest", "full_rank"]
    examples = []
    seq = 0
    for iso3, commodity, date, g in candidates:
        if len(examples) >= n:
            break
        k = rng.randint(3, min(5, g["market"].nunique()))
        chosen = g.sample(n=k, random_state=rng.randint(0, 2**31))
        chosen = chosen.sort_values("price")
        variant = variants[seq % len(variants)]
        country = country_name(iso3)
        my = month_year(date)
        markets_list = ", ".join(chosen["market"].tolist())
        unit = chosen.iloc[0]["unit"]
        currency = chosen.iloc[0]["currency"]

        if variant == "lowest":
            best = chosen.iloc[0]
            prompt = (
                f"Among {markets_list} in {country}, which had the lowest retail price of "
                f"{commodity} in {my}?"
            )
            gold = f"{best['market']} ({best['price']:.2f} {currency} per {unit})."
        elif variant == "highest":
            best = chosen.iloc[-1]
            prompt = (
                f"Among {markets_list} in {country}, which had the highest retail price of "
                f"{commodity} in {my}?"
            )
            gold = f"{best['market']} ({best['price']:.2f} {currency} per {unit})."
        else:
            prompt = (
                f"Rank {markets_list} in {country} by retail price of {commodity} in {my}, "
                f"from lowest to highest."
            )
            gold = " < ".join(
                f"{r['market']} ({r['price']:.2f})" for _, r in chosen.iterrows()
            )

        examples.append({
            "id": f"agmkt-rank-{seq:04d}", "generator_family": "cross_market_ranking",
            "generator_subtype": variant, "country_iso3": iso3,
            "market": chosen["market"].tolist(), "commodity": commodity, "unit": unit,
            "currency": currency, "pricetype": chosen.iloc[0]["pricetype"],
            "query_period": {"month_year": my}, "prompt": prompt, "gold_answer": gold,
            "gold_value": {r["market"]: float(r["price"]) for _, r in chosen.iterrows()},
            "answer_type": "ranking",
            "source_rows": [source_row(r) for _, r in chosen.iterrows()],
        })
        seq += 1
    return examples


# ---------------------------------------------------------------------------
# Family 5: abstention_negative
# ---------------------------------------------------------------------------

def gen_abstention_gap(df: pd.DataFrame, rng: random.Random, n: int) -> list[dict]:
    all_months = pd.period_range("2023-01", "2024-12", freq="M")
    groups = df.groupby(["countryiso3", "market", "commodity"])
    candidates = []
    for (iso3, market, commodity), g in groups:
        covered = set(g["date"].dt.to_period("M"))
        if len(covered) < 8:  # need real, regular reporting for a "gap" to mean something
            continue
        missing = [m for m in all_months if m not in covered]
        if not missing:
            continue
        candidates.append((iso3, market, commodity, rng.choice(missing), g.iloc[0]))
    rng.shuffle(candidates)

    examples = []
    for seq, (iso3, market, commodity, missing_month, sample_row) in enumerate(candidates[:n]):
        my = missing_month.strftime("%B %Y")
        country = country_name(iso3)
        prompt = f"What was the retail price of {commodity} in {market}, {country} in {my}?"
        gold = rng.choice(ABSTAIN_GAP_TEMPLATES).format(commodity=commodity, market=market, month_year=my)
        examples.append({
            "id": f"agmkt-abst-gap-{seq:04d}", "generator_family": "abstention_negative",
            "generator_subtype": "gap_within_range", "country_iso3": iso3,
            "market": [market], "commodity": commodity, "unit": sample_row["unit"],
            "currency": sample_row["currency"], "pricetype": "Retail",
            "query_period": {"month_year": my}, "prompt": prompt, "gold_answer": gold,
            "gold_value": None, "answer_type": "abstain", "source_rows": [],
        })
    return examples


def gen_abstention_cutoff(df: pd.DataFrame, rng: random.Random, n: int) -> list[dict]:
    known = df.drop_duplicates(subset=["countryiso3", "market", "commodity"])
    pool = known.sample(frac=1.0, random_state=SEED + 1).reset_index(drop=True)
    beyond_months = pd.period_range("2025-01", "2025-12", freq="M")

    examples = []
    for seq in range(n):
        row = pool.iloc[seq % len(pool)]
        target_month = rng.choice(list(beyond_months))
        my = target_month.strftime("%B %Y")
        country = country_name(row["countryiso3"])
        prompt = f"What was the retail price of {row['commodity']} in {row['market']}, {country} in {my}?"
        gold = rng.choice(ABSTAIN_CUTOFF_TEMPLATES).format(month_year=my)
        examples.append({
            "id": f"agmkt-abst-cut-{seq:04d}", "generator_family": "abstention_negative",
            "generator_subtype": "beyond_cutoff", "country_iso3": row["countryiso3"],
            "market": [row["market"]], "commodity": row["commodity"], "unit": row["unit"],
            "currency": row["currency"], "pricetype": "Retail",
            "query_period": {"month_year": my}, "prompt": prompt, "gold_answer": gold,
            "gold_value": None, "answer_type": "abstain", "source_rows": [],
        })
    return examples


# ---------------------------------------------------------------------------
# Split + write
# ---------------------------------------------------------------------------

def stratified_split(examples: list[dict], rng: random.Random, ratios=(0.75, 0.125, 0.125)):
    """Split within each (generator_family, generator_subtype) bucket."""
    from collections import defaultdict

    buckets = defaultdict(list)
    for ex in examples:
        buckets[(ex["generator_family"], ex["generator_subtype"])].append(ex)

    train, val, test = [], [], []
    for key, items in buckets.items():
        items = items[:]
        rng.shuffle(items)
        n = len(items)
        n_train = round(n * ratios[0])
        n_val = round(n * ratios[1])
        for i, ex in enumerate(items):
            if i < n_train:
                split = "train"
            elif i < n_train + n_val:
                split = "val"
            else:
                split = "test"
            ex["split"] = split
            (train if split == "train" else val if split == "val" else test).append(ex)
    return train, val, test


def main():
    rng = random.Random(SEED)
    df = load_corpus()
    print(f"loaded corpus: {len(df)} rows after cleaning (African, Retail, non-null/positive price)")

    all_examples = []
    all_examples += gen_state_at_time(df, rng, n_local=200, n_usd=200)
    all_examples += two_point_examples(df, rng, n=240, family="trend_change", same_month_only=False, id_prefix="trend")
    all_examples += two_point_examples(df, rng, n=200, family="yoy_comparison", same_month_only=True, id_prefix="yoy")
    all_examples += gen_cross_market_ranking(df, rng, n=160)
    all_examples += gen_abstention_gap(df, rng, n=100)
    all_examples += gen_abstention_cutoff(df, rng, n=100)

    train, val, test = stratified_split(all_examples, rng)

    for name, rows in [("train", train), ("val", val), ("test", test), ("all", all_examples)]:
        path = OUT_DIR / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False, default=str) + "\n")

    # stats
    from collections import Counter
    fam_counts = Counter((e["generator_family"], e.get("generator_subtype")) for e in all_examples)
    split_counts = Counter(e["split"] for e in all_examples)
    fam_split_counts = Counter((e["generator_family"], e["split"]) for e in all_examples)

    stats = {
        "total": len(all_examples),
        "by_family_subtype": {f"{k[0]}/{k[1]}": v for k, v in sorted(fam_counts.items())},
        "by_split": dict(split_counts),
        "by_family_and_split": {f"{k[0]}/{k[1]}": v for k, v in sorted(fam_split_counts.items())},
    }
    with (OUT_DIR / "stats.json").open("w") as f:
        json.dump(stats, f, indent=2)

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
