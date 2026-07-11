import shutil

from config import MERGED_DIR
from utils import mkdirs


def merge_annotations(sample_id: str, opencravat_tsv: str) -> str:
    """VEP has been removed, so there's nothing left to merge OpenCRAVAT's
    output with. This stage now just copies the OC TSV into MERGED_DIR so
    downstream stages (custom_annotators, fallback_fill, dedupe_columns) can
    keep reading from a stable, predictable path without caring that this
    used to be a two-source merge.
    """
    mkdirs(MERGED_DIR)
    out_tsv = f"{MERGED_DIR}/{sample_id}.merged.tsv"
    shutil.copy(opencravat_tsv, out_tsv)
    return out_tsv


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python merge_annotations.py <sample_id> <opencravat_tsv>")
        raise SystemExit(1)
    print(merge_annotations(sys.argv[1], sys.argv[2]))
