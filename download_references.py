import os
import subprocess

from config import REFS_DIR, ANNOT_DIR
from utils import fetch, run

# Written once everything below completes successfully. If present, the
# whole stage is skipped on the next run instead of re-checking every file.
DONE_MARKER = f"{REFS_DIR}/.download_references_done"


def download_references() -> None:
    if os.path.exists(DONE_MARKER):
        print(f"[skip] {DONE_MARKER} found — reference download already complete, skipping entire stage")
        return

    # GRCh38.fa + prebuilt bwa/samtools index files, hosted by us on Hugging
    # Face (one-time indexing already done — avoids repeating the ~1hr
    # `bwa index` build on every fresh environment).
    HF_BASE = "https://huggingface.co/datasets/nirmala29/grch38-bwa-index/resolve/main"
    ref_fa = f"{REFS_DIR}/GRCh38.fa"
    for suffix in ["", ".fai", ".bwt", ".amb", ".ann", ".pac", ".sa"]:
        fname = f"GRCh38.fa{suffix}"
        fetch(f"{HF_BASE}/{fname}", f"{REFS_DIR}/{fname}")
    if not os.path.exists(ref_fa):
        print(f"[WARNING] {ref_fa} still missing after download attempt — check the HF_BASE URL above.")

    fetch(
        "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz",
        f"{REFS_DIR}/dbsnp.vcf.gz",
        post_cmd=["tabix", "-p", "vcf", f"{REFS_DIR}/dbsnp.vcf.gz"],
    )
    fetch(
        "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz",
        f"{ANNOT_DIR}/clinvar.vcf.gz",
        post_cmd=["tabix", "-p", "vcf", f"{ANNOT_DIR}/clinvar.vcf.gz"],
    )

    # NOTE: gnomAD genome-wide "sites" VCFs are large (many 10-50GB+ each);
    # pulling all 22 autosomes needs serious disk space. Each fetch here is
    # required=False so a disk-full/network failure on any one chromosome
    # logs a warning and moves on instead of crashing the entire 9-stage
    # pipeline run.
    for chrom in range(1, 23):
        fetch(
            f"https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/"
            f"gnomad.genomes.v4.1.sites.chr{chrom}.vcf.bgz",
            f"{ANNOT_DIR}/gnomad.chr{chrom}.vcf.bgz",
            post_cmd=["tabix", "-p", "vcf", f"{ANNOT_DIR}/gnomad.chr{chrom}.vcf.bgz"],
            required=False,
        )

    am_tsv_gz = f"{ANNOT_DIR}/alphamissense_hg38.tsv.gz"
    fetch("https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg38.tsv.gz", am_tsv_gz)
    if not os.path.exists(f"{ANNOT_DIR}/alphamissense_hg38.tsv"):
        run(["gunzip", "-k", am_tsv_gz])
    else:
        print(f"[skip] {ANNOT_DIR}/alphamissense_hg38.tsv already exists")

    # NOTE: VEP + its cache have been removed. Annotation is OpenCRAVAT-only
    # now (see OC_ANNOTATORS in config.py / install_opencravat.py).

    manual_only = ["GRCh38.fa (+ indexes)", "dbNSFP", "ClinPred", "CScape", "denovo-db", "FunSeq2", "MISTIC", "full CADD"]
    print(f"[manual] Require manual placement / click-through registration, NOT auto-downloaded: {manual_only}")

    os.makedirs(os.path.dirname(DONE_MARKER), exist_ok=True)
    open(DONE_MARKER, "w").close()
    print("Reference/DB download pass complete.")


if __name__ == "__main__":
    download_references()
