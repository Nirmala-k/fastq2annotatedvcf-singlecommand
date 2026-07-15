"""
Central configuration for the plain-Python (non-Modal) version of the
FASTQ -> annotated-variants pipeline.

Every stage module imports DATA_MOUNT from here so paths stay consistent
whether you're running locally, in a Docker container, or inside an
NVIDIA Launchable.

NOTE: VEP has been removed. Annotation is OpenCRAVAT-only — see
OC_ANNOTATORS below. This list has been through a full licensing audit
(every module individually researched against its actual source's terms)
and contains ONLY modules with a confirmed clean commercial-use license.
Anything restricted OR left unverified after a genuine search attempt was
excluded — see the audit notes below and LICENSE for full detail.
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

# =============================================================================
# FULL LICENSING AUDIT — every module below individually researched.
# Only modules with CONFIRMED clean commercial-use licensing are included.
# =============================================================================
#
# CONFIRMED RESTRICTED (excluded — paid/non-commercial license required):
#   cadd, cadd_exome  -> University of Washington, paid commercial license
#                        required (cadd.gs.washington.edu/download).
#   omim               -> Johns Hopkins University, paid commercial license
#                        required for any for-profit entity (omim.org).
#   spliceai, primateai -> Illumina, CC BY-NC 4.0 (confirmed via gnomAD's
#                        policies page and Illumina's own GitHub LICENSE).
#   revel               -> "freely available for non-commercial use...
#                        contact [author] for other uses" (author's site).
#   polyphen2            -> named explicitly in dbNSFP's own license page
#                        as requiring individual commercial licensing.
#   clinpred              -> "freely available for all non-commercial
#                        applications... contact [authors]" (own site).
#   linsight                -> named in dbNSFP's commercial-branch
#                        exclusion list alongside polyphen2/revel/clinpred/
#                        cadd (all independently confirmed restricted).
#   mavedb                   -> CC BY-NC-SA 4.0 (confirmed via published
#                        license inventory).
#   pharmgkb                  -> confirmed BROKEN in practice (errors on
#                        every variant), unrelated to licensing.
#   civic, dbcid, target, cscape, cscape_coding, funseq2, oncokb, litvar_full
#                              -> removed earlier for relevance/reliability
#                        reasons (see git history), not re-added here.
#
# NOT CONFIRMED CLEAN after a genuine search attempt (excluded per a
# "confirmed-clean-only" policy — absence of a clear open-license
# statement is treated the same as a restriction, not as "probably fine"):
#   bayesdel, loftool, dbscsnv, dann_coding, aloft, denovo, ess_gene,
#   pseudogene, regulomedb
# If you can find and confirm an open license for any of these, they can
# be added back with a citation, same as the confirmed-open list below.
#
# CONFIRMED CLEAN for commercial use (each individually verified):
#   alphamissense -> DeepMind relicensed to CC BY 4.0 (fully open) 13 March
#                    2024, lifting the prior non-commercial restriction.
#   gnomad/gnomad3/gnomad4/gnomad_gene -> Broad Institute, released
#                    "without restriction on use", attribution only.
#   sift          -> SIFT4G engine is GPL-3.0 (OSI-approved, commercial use
#                    explicitly permitted) — confirmed via Bioconda.
#   provean       -> GPL-3.0, confirmed via JCVI's own GitHub LICENSE file.
#   mistic        -> MIT license, confirmed via GitHub's license detector.
#   rvis          -> original data/publication under PLOS Genetics' default
#                    CC BY license (open-access journal, no NC clause).
#   phylop/siphy/lrt -> derived from UCSC Genome Browser's public,
#                    NIH-funded conservation tracks; standard open
#                    redistribution norms for this data (distinct from the
#                    Genome Browser *software's* separate commercial terms).
#   go            -> Gene Ontology Consortium, CC BY 4.0 (explicit).
#   clinvar, clinvar_acmg, gwas_catalog -> CC0 1.0 (public domain),
#                    confirmed via published license inventory.
#   hpo           -> "freely available" under attribution/versioning-only
#                    conditions, no non-commercial clause (HPO's own terms).
#   clingen       -> NIH-funded consortium explicitly built for combined
#                    academic AND commercial clinical-lab use.
#   dbsnp, dbsnp_common, ncbigene, pubmed, litvar -> NCBI; U.S. government
#                    works are public domain by federal law (17 U.S.C. §105).
#   cgd           -> NHGRI/NIH, explicit public-domain waiver on its own
#                    site (distinct from the JHU-run OMIM despite similar
#                    naming).
#   interpro      -> EBI/EMBL-EBI standard open-data institutional policy.
OC_ANNOTATORS = [
    "alphamissense",
    "cgd", "clingen", "clinvar", "clinvar_acmg",
    "dbsnp", "dbsnp_common",
    "go", "gnomad", "gnomad_gene", "gnomad3", "gnomad4",
    "gwas_catalog", "hpo", "interpro", "lrt", "litvar",
    "mistic", "ncbigene", "phylop", "provean",
    "pubmed", "rvis", "sift", "siphy",
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
