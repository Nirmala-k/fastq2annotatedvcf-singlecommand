"""
Central configuration for the plain-Python (non-Modal) version of the
FASTQ -> annotated-variants pipeline.

Every stage module imports DATA_MOUNT from here so paths stay consistent
whether you're running locally, in a Docker container, or inside an
NVIDIA Launchable.

NOTE: VEP has been removed. Annotation is OpenCRAVAT-only — see
OC_ANNOTATORS below, which both install_opencravat.py and annotate_multi.py
read from, so the installed module set and the requested module set can
never drift apart. Cancer-specific modules (civic, dbcid, target) and the
slow/unreliable litvar_full module have been removed. custom_annotators.py
still exists in stages/ but is no longer called from run_all.py.
"""
import os

# Root data directory. This is where your reference genome, dbSNP, ClinVar,
# gnomAD, AlphaMissense, and OpenCRAVAT modules already live — do not change
# this default, it points at data that already exists. Override with
# PIPELINE_DATA_MOUNT env var only if running on a different machine.
DATA_MOUNT = os.environ.get("PIPELINE_DATA_MOUNT", "/data/genomics-pipeline/data")

REFS_DIR = f"{DATA_MOUNT}/refs"
ANNOT_DIR = f"{DATA_MOUNT}/annotation"
OC_DATA_DIR = f"{DATA_MOUNT}/opencravat_modules"
OC_HOME_DIR = f"{DATA_MOUNT}/opencravat_home"

TRIM_DIR = f"{DATA_MOUNT}/trim"
ALIGN_DIR = f"{DATA_MOUNT}/align"
CALLS_DIR = f"{DATA_MOUNT}/calls"
NORM_DIR = f"{DATA_MOUNT}/norm"
ANNOT_OUT_DIR = f"{DATA_MOUNT}/annot"
MERGED_DIR = f"{DATA_MOUNT}/merged"
CUSTOM_DIR = f"{DATA_MOUNT}/custom"
FILLED_DIR = f"{DATA_MOUNT}/filled"
FINAL_DIR = f"{DATA_MOUNT}/final"
PHASED_DIR = f"{DATA_MOUNT}/phased"

# OpenCRAVAT annotator set. Both install_opencravat_modules() and
# annotate_multi() read from this single list so they can't drift out of
# sync with each other.
#
# Removed from the original 53-module set:
#   civic, dbcid, target   -> cancer/oncology-specific (CIViC = cancer
#                              variant interpretation, dbCID = cancer driver
#                              indels, TARGET = NCI pediatric cancer
#                              genomics program) — not relevant to a
#                              germline pediatric cardiac pipeline.
#   litvar_full             -> slow and unreliable (831s+ CADD-scale runtime
#                              in practice, plus intermittent
#                              "Connection aborted" failures against NCBI's
#                              API). Plain `litvar` (rsid-only, ~1s) kept.
#   pharmgkb                -> confirmed broken in practice: every call
#                              errors with "cannot access local variable
#                              'ca'" (a bug in this OC module version, not
#                              a data-sparsity issue) — 99.88% null and
#                              climbing, contributes nothing real.
#   cscape, cscape_coding, funseq2, oncokb -> previously removed by hand.
OC_ANNOTATORS = [
    "aloft", "alphamissense", "bayesdel", "cadd", "cadd_exome",
    "cgd", "clingen", "clinpred", "clinvar", "clinvar_acmg",
    "dann_coding", "dbsnp", "dbscsnv", "dbsnp_common", "denovo",
    "ess_gene", "go", "gnomad", "gnomad_gene", "gnomad3", "gnomad4",
    "gwas_catalog", "hpo", "interpro", "lrt", "linsight",
    "litvar", "loftool", "mavedb", "mistic", "ncbigene", "omim",
    "phylop", "polyphen2", "primateai", "provean",
    "pseudogene", "pubmed", "regulomedb", "revel", "rvis", "sift",
    "siphy", "spliceai",
]

# Binaries each stage needs on PATH. Used by check_functions.py to verify
# the environment BEFORE anything is actually run.
STAGE_BINARIES = {
    "download_references": ["wget", "tabix", "samtools", "bwa"],
    "install_opencravat": ["oc"],
    "adapter_trim": ["fastp"],
    "fq2bam": ["pbrun"],
    "call_variants": ["pbrun", "bgzip", "tabix"],
    "normalize": ["bcftools", "tabix"],
    "annotate_multi": ["oc"],
    "merge_annotations": [],  # pure python file copy
    "custom_annotators": ["tabix"],  # kept for standalone use, not in run_all chain
    "fallback_fill": [],  # pure python + requests
    "dedupe_columns": [],  # pure python
    "phase_variants": ["whatshap", "bcftools", "bgzip", "tabix"],
}

# Python packages each stage needs importable.
STAGE_PY_IMPORTS = {
    "fallback_fill": ["requests"],
}