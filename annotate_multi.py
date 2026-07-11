import csv
import sqlite3

from config import ANNOT_OUT_DIR, OC_ANNOTATORS
from install_opencravat import configure_oc_home
from utils import mkdirs, run


def _find_col(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def _should_drop(col: str) -> bool:
    """Columns dropped even though their parent module is otherwise useful:
    ClinVar's oncology/somatic sub-fields aren't relevant to a germline
    pediatric-cardiac pipeline (100% null on real data anyway, since these
    variants are germline not tumor), and base__note_variant is an unused
    internal OpenCRAVAT field (100% null in practice)."""
    if col == "base__note_variant":
        return True
    if col.startswith("clinvar__onc_") or col.startswith("clinvar__somatic_"):
        return True
    return False


def _export_sqlite_annotations(sqlite_path: str, out_tsv: str) -> str:
    """Export BOTH the variant-level and gene-level OpenCRAVAT tables,
    joined by gene symbol.

    Several configured modules (hpo, clingen, cgd, go, ncbigene,
    gnomad_gene, loftool, rvis, ess_gene, ...) write to OpenCRAVAT's `gene`
    table, not `variant` — exporting only `variant` (the previous behavior)
    silently dropped every one of them from the final output, even though
    install_opencravat_modules() was paying the full install cost for them.

    NOTE: this assumes the gene table's gene-symbol column is named
    'base__hugo' or 'hugo' (matching the variant table's own convention).
    If that guess is wrong for your OpenCRAVAT version, this prints the
    real column list it found so the join key can be corrected in one line.
    """
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    # Gene table is small (one row per gene) — load fully into memory.
    cur.execute("SELECT * FROM gene")
    gene_cols = [d[0] for d in cur.description]
    gene_rows = cur.fetchall()

    gene_key_col = _find_col(gene_cols, ["base__hugo", "hugo"])
    if gene_key_col:
        gene_key_idx = gene_cols.index(gene_key_col)
        gene_by_symbol = {row[gene_key_idx]: row for row in gene_rows}
        gene_out_cols = [c for c in gene_cols if c != gene_key_col]
        gene_out_indices = [gene_cols.index(c) for c in gene_out_cols]
        print(f"[annotate_multi] gene table: {len(gene_rows)} genes, "
              f"{len(gene_out_cols)} gene-level columns, joining on '{gene_key_col}'")
    else:
        print(f"[annotate_multi] WARNING: no gene-symbol column found in gene "
              f"table (actual columns: {gene_cols}) — skipping gene-table join, "
              f"gene-level annotators (hpo/clingen/cgd/etc) will be absent from "
              f"the final output. Fix _find_col()'s candidate list above with "
              f"whichever of these is the real gene-symbol column.")
        gene_by_symbol, gene_out_cols, gene_out_indices = {}, [], []

    # Variant table is WGS-scale — stream it row by row, don't fetchall().
    cur.execute("SELECT * FROM variant")
    variant_cols = [d[0] for d in cur.description]
    variant_key_col = _find_col(variant_cols, ["base__hugo", "hugo"])
    variant_key_idx = variant_cols.index(variant_key_col) if variant_key_col else None

    combined_cols = list(variant_cols) + gene_out_cols
    keep_mask = [not _should_drop(c) for c in combined_cols]
    out_cols = [c for c, keep in zip(combined_cols, keep_mask) if keep]
    dropped = [c for c, keep in zip(combined_cols, keep_mask) if not keep]
    if dropped:
        print(f"[annotate_multi] dropping {len(dropped)} low-value columns: {dropped}")

    n = 0
    with open(out_tsv, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(out_cols)
        for vrow in cur:
            gene_symbol = vrow[variant_key_idx] if variant_key_idx is not None else None
            grow = gene_by_symbol.get(gene_symbol)
            extra = [grow[i] for i in gene_out_indices] if grow else [""] * len(gene_out_cols)
            combined = list(vrow) + extra
            writer.writerow([v for v, keep in zip(combined, keep_mask) if keep])
            n += 1
    conn.close()

    print(f"[annotate_multi] exported {n} variants x {len(out_cols)} columns "
          f"(variant + gene table joined, low-value columns dropped) -> {out_tsv}")
    return out_tsv


def annotate_multi(sample_id: str, vcf_path: str) -> str:
    """OpenCRAVAT-only annotation. VEP has been removed from this pipeline —
    all annotation now comes from the OC_ANNOTATORS module list in config.py.
    """
    mkdirs(ANNOT_OUT_DIR, f"{ANNOT_OUT_DIR}/opencravat")
    configure_oc_home()

    run([
        "oc", "run", vcf_path, "-l", "hg38",
        "-a", *OC_ANNOTATORS,
        "-t", "text", "-d", f"{ANNOT_OUT_DIR}/opencravat", "-n", sample_id,
    ])

    sqlite_path = f"{ANNOT_OUT_DIR}/opencravat/{sample_id}.sqlite"
    out_tsv = f"{ANNOT_OUT_DIR}/opencravat/{sample_id}.export.tsv"
    return _export_sqlite_annotations(sqlite_path, out_tsv)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python annotate_multi.py <sample_id> <vcf_path>")
        raise SystemExit(1)
    print(annotate_multi(sys.argv[1], sys.argv[2]))
