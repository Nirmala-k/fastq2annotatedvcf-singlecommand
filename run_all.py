#!/usr/bin/env python3
"""
run_all.py — plain-Python orchestrator (no Modal, no Flask).

Chains every stage by calling its function directly, in-process, on
whatever machine you run this on (your GPU box / NVIDIA Launchable
container). Each stage still writes to DATA_MOUNT (see config.py) exactly
like the Modal version did — just without volume.commit(), since there's
no Modal Volume anymore; it's a normal filesystem.

NOTE:
  - VEP has been removed. Annotation is OpenCRAVAT-only (config.OC_ANNOTATORS).
  - Cancer-specific OC modules (civic, dbcid, target) and the slow/flaky
    litvar_full module have been removed from config.OC_ANNOTATORS.
  - The custom_annotators step (ClinPred/CScape/denovo-db/FunSeq2/MISTIC
    local flat-file lookups) has been removed from this chain while the
    OpenCRAVAT side of the pipeline is still being validated. The file
    still exists at stages/custom_annotators.py and can be run standalone,
    or re-added to main() below, once you want it back.
  - A new final stage, phase_variants, runs WhatsHap on the raw/normalized
    VCF + BAM (NOT the OpenCRAVAT-annotated one) and produces both an
    unphased and a phased VCF under FINAL_DIR.

Usage:
    python run_all.py --sample-id KHAHPGXSTD2 \
        --fastq-r1 /data/fastq/KHAHPGXSTD2_R1.fastq.gz \
        --fastq-r2 /data/fastq/KHAHPGXSTD2_R2.fastq.gz

Run check_functions.py first to confirm every stage/binary is available.
"""
import argparse

from download_references import download_references
from install_opencravat import install_opencravat_modules
from adapter_trim import adapter_trim
from fq2bam import fq2bam
from call_variants import call_variants
from normalize import normalize
from annotate_multi import annotate_multi
from merge_annotations import merge_annotations
from fallback_fill import fallback_fill
from dedupe_columns import dedupe_columns
from phase_variants import phase_variants

from config import DATA_MOUNT


def parse_args():
    p = argparse.ArgumentParser(description="FASTQ -> annotated + phased variants pipeline (plain python)")
    p.add_argument("--sample-id", default="KHAHPGXSTD2")
    p.add_argument("--fastq-r1", default=f"{DATA_MOUNT}/fastq/KHAHPGXSTD2_R1.fastq.gz")
    p.add_argument("--fastq-r2", default=f"{DATA_MOUNT}/fastq/KHAHPGXSTD2_R2.fastq.gz")
    p.add_argument("--ref-fasta", default=f"{DATA_MOUNT}/refs/GRCh38.fa")
    p.add_argument("--known-sites", default=f"{DATA_MOUNT}/refs/dbsnp.vcf.gz")
    p.add_argument("--skip-download", action="store_true",
                    help="skip stage 0/0.5 if refs + OC modules already prepared")
    p.add_argument("--skip-fallback-fill", action="store_true",
                    help="skip stage 7 (per-variant API/dbNSFP fallback fill) — "
                         "it's slow (rate-limited external API calls per missing "
                         "value, can take hours on WGS-scale variant counts)")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.skip_download:
        print("[0/9] Checking/downloading reference genome + annotation databases")
        download_references()

        print("[0.5/9] Checking/installing OpenCRAVAT annotator modules")
        install_opencravat_modules()
    else:
        print("[0-0.5/9] Skipped (--skip-download)")

    print(f"[1/9] Trimming adapters for {args.sample_id}")
    trimmed_r1, trimmed_r2 = adapter_trim(args.sample_id, args.fastq_r1, args.fastq_r2)

    print("[2/9] Aligning (pbrun fq2bam, GPU)")
    bam = fq2bam(args.sample_id, trimmed_r1, trimmed_r2, args.ref_fasta, args.known_sites)

    print("[3/9] Calling variants (pbrun deepvariant, GPU)")
    vcf = call_variants(args.sample_id, bam, args.ref_fasta)

    print("[4/9] Normalizing VCF")
    norm_vcf = normalize(args.sample_id, vcf, args.ref_fasta)

    print("[5/9] Annotating (OpenCRAVAT only)")
    oc_tsv = annotate_multi(args.sample_id, norm_vcf)

    print("[6/9] Carrying OpenCRAVAT annotations forward")
    merged_tsv = merge_annotations(args.sample_id, oc_tsv)

    if args.skip_fallback_fill:
        print("[7/9] Skipped (--skip-fallback-fill)")
        filled_tsv = merged_tsv
    else:
        print("[7/9] Per-annotator fallback fill (API + dbNSFP)")
        filled_tsv = fallback_fill(args.sample_id, merged_tsv)

    print("[8/9] Deduping exact + semantic overlapping columns")
    final_tsv = dedupe_columns(args.sample_id, filled_tsv)

    print("[9/9] Phasing (WhatsHap on the raw/normalized VCF + BAM)")
    unphased_vcf, phased_vcf = phase_variants(args.sample_id, norm_vcf, bam, args.ref_fasta)

    print(f"\nDONE.")
    print(f"  Final annotated table : {final_tsv}")
    print(f"  Unphased VCF           : {unphased_vcf}")
    print(f"  Phased VCF              : {phased_vcf}")


if __name__ == "__main__":
    main()
