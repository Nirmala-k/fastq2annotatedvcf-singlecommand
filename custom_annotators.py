import csv
import os
import subprocess

from config import CUSTOM_DIR
from utils import mkdirs


def _tabix_lookup(path, chrom, pos, ref, alt, value_col, ref_col=2, alt_col=3):
    if not path or not os.path.exists(path):
        return None
    for c in (chrom, chrom.replace("chr", ""), f"chr{chrom.replace('chr', '')}"):
        region = f"{c}:{pos}-{pos}"
        result = subprocess.run(["tabix", path, region], capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            continue
        for line in result.stdout.strip().splitlines():
            fields = line.split("\t")
            if len(fields) > max(ref_col, alt_col, value_col) and fields[ref_col] == ref and fields[alt_col] == alt:
                return fields[value_col]
    return None


def custom_annotators(sample_id: str, merged_tsv: str,
                       clinpred: str | None, cscape: str | None, denovo_db: str | None,
                       funseq2: str | None, mistic: str | None) -> str:
    paths = {"clinpred": clinpred, "cscape": cscape, "denovo_db": denovo_db,
             "funseq2": funseq2, "mistic": mistic}
    value_cols = {"clinpred": 5, "cscape": 4, "denovo_db": 4, "funseq2": -1, "mistic": 5}

    mkdirs(CUSTOM_DIR)
    out_tsv = f"{CUSTOM_DIR}/{sample_id}.enriched.tsv"

    with open(merged_tsv, newline="") as f_in:
        reader = csv.DictReader(f_in, delimiter="\t")
        fieldnames = list(reader.fieldnames) + [f"{k}_local" for k in paths]
        rows = list(reader)

    counts = {k: 0 for k in paths}
    for row in rows:
        chrom, pos, ref, alt = row["base__chrom"], int(row["base__pos"]), row["base__ref_base"], row["base__alt_base"]
        for name, path in paths.items():
            val = _tabix_lookup(path, chrom, pos, ref, alt, value_cols[name])
            row[f"{name}_local"] = val or ""
            if val:
                counts[name] += 1

    with open(out_tsv, "w", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    for name, n in counts.items():
        status = f"{n} hits" if paths[name] else "SKIPPED (no file path given)"
        print(f"[custom_annotators] {name}: {status}")

    return out_tsv


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 8:
        print("usage: python custom_annotators.py <sample_id> <merged_tsv> <clinpred> <cscape> <denovo_db> <funseq2> <mistic>")
        print("(pass empty string '' for any file you don't have)")
        raise SystemExit(1)
    sample_id, merged_tsv = sys.argv[1], sys.argv[2]
    args = [a or None for a in sys.argv[3:8]]
    print(custom_annotators(sample_id, merged_tsv, *args))
