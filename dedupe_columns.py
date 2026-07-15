import csv
from collections import defaultdict

from config import FINAL_DIR
from utils import mkdirs

SEMANTIC_GROUPS = {
    "pathogenicity_call": [
        "sift__prediction",
        "alphamissense__am_class", "provean__prediction",
        "mistic_local",
    ],
    "conservation_score": ["conservation__phylop"],
    "rsid": ["dbsnp__rs"],
    "population_af": ["gnomad3__af"],
}


def dedupe_columns(sample_id: str, tsv_path: str) -> str:
    mkdirs(FINAL_DIR)
    out_tsv = f"{FINAL_DIR}/{sample_id}.annotated.tsv"

    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    key_cols = {"base__chrom", "base__pos", "base__ref_base", "base__alt_base", "base__uid"}
    candidate_cols = [c for c in fieldnames if c not in key_cols]
    signatures = defaultdict(list)
    for col in candidate_cols:
        sig = tuple(row.get(col, "") for row in rows)
        signatures[sig].append(col)
    dup_map = {}
    for cols in signatures.values():
        if len(cols) > 1:
            for dup in cols[1:]:
                dup_map[dup] = cols[0]
    fieldnames = [f for f in fieldnames if f not in dup_map]
    print(f"[dedupe] Dropped {len(dup_map)} exact-duplicate columns")

    present_groups = {g: [c for c in cols if c in fieldnames] for g, cols in SEMANTIC_GROUPS.items()}
    present_groups = {g: c for g, c in present_groups.items() if len(c) >= 2}
    for row in rows:
        for group, cols in present_groups.items():
            values, sources = [], []
            for c in cols:
                v = row.get(c, "")
                if v not in ("", None, "."):
                    values.append(v)
                    sources.append(c.split("__")[0])
            row[f"{group}_merged"] = " | ".join(values)
            row[f"{group}_sources"] = ",".join(sources)
    new_fieldnames = [f for f in fieldnames if not any(f in c for c in present_groups.values())]
    for group in present_groups:
        new_fieldnames += [f"{group}_merged", f"{group}_sources"]

    with open(out_tsv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"[dedupe] Final column count: {len(new_fieldnames)} -> {out_tsv}")
    return out_tsv


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python dedupe_columns.py <sample_id> <tsv_path>")
        raise SystemExit(1)
    print(dedupe_columns(sys.argv[1], sys.argv[2]))
