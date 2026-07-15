# Genomics Pipeline

A plain-Python (no Modal, no Flask), Dockerized genomic variant-analysis
pipeline: FASTQ -> GPU-accelerated alignment + variant calling (NVIDIA
Parabricks) -> OpenCRAVAT annotation -> a final annotated TSV, plus
read-based phasing (WhatsHap) producing both an unphased and a phased VCF.

## Pipeline stages

```
[0/9]  download_references     — GRCh38 + bwa index (Hugging Face), dbSNP,
                                  ClinVar, gnomAD, AlphaMissense
[0.5/9] install_opencravat      — installs OC_ANNOTATORS modules (config.py)
[1/9]  adapter_trim             — fastp
[2/9]  fq2bam                   — Parabricks GPU alignment
[3/9]  call_variants            — Parabricks GPU deepvariant
[4/9]  normalize                — bcftools norm
[5/9]  annotate_multi           — OpenCRAVAT only (VEP removed)
[6/9]  merge_annotations        — carries OC's sqlite export forward
[7/9]  fallback_fill            — API/dbNSFP fallback for missing OC fields
[8/9]  dedupe_columns           — exact + semantic column dedup -> final TSV
[9/9]  phase_variants           — WhatsHap phasing on the RAW/normalized
                                  VCF + BAM -> unphased.vcf.gz + phased.vcf.gz
```

`custom_annotators.py` (ClinPred/CScape/denovo-db/FunSeq2/MISTIC local
flat-file lookups) still exists in `stages/` and works standalone, but is
**not called** by `run_all.py` right now while the OpenCRAVAT side of the
pipeline is being validated. Re-add the call in `run_all.py`'s `main()`
whenever you want it back.

## What changed recently

- **VEP removed entirely** — annotation is OpenCRAVAT-only now.
- **Cancer-specific OC modules removed**: `civic`, `dbcid`, `target`
  (CIViC/dbCID/TARGET are all oncology-focused — not relevant to a
  germline pediatric cardiac pipeline).
- **`litvar_full` removed** — slow (800s+ in practice) and prone to
  intermittent connection failures against NCBI's API. Plain `litvar`
  (rsid-only, ~1s) is kept.
- **`custom_annotators` step removed from the main chain** (file still
  present, runnable standalone).
- **Annotation reads from OpenCRAVAT's sqlite, not its `-t text` report** —
  the text reporter is a human-readable format (comment lines, section
  headers), not a clean single-header TSV; parsing it as one collapsed
  everything into 1 garbage column. `annotate_multi.py` now exports
  straight from the `variant` table in the `.sqlite` OC always produces.
- **New `phase_variants` stage** (adapted from a separate WhatsHap/Modal/GCS
  script) — ported down to plain-Python, single-sample, local-file
  operation matching the rest of this repo. Deliberately runs on the
  **raw/normalized** VCF (pre-OpenCRAVAT), not the annotated one — phasing
  only needs genotypes + read evidence, and this sidesteps OpenCRAVAT's
  known header-quoting issue entirely.

## Repository files

```
config.py               — central paths, OC_ANNOTATORS, binary requirements
utils.py                 — shared mkdirs/run/fetch helpers, csv field-size fix
run_all.py                — orchestrates the chain above
check_functions.py        — validates every stage imports + required binaries
Dockerfile                 — Parabricks base + bwa/samtools/bcftools/fastp +
                             isolated Python 3.11 venv for OpenCRAVAT +
                             whatshap
.dockerignore
requirements.txt
stages/
  download_references.py
  install_opencravat.py
  adapter_trim.py
  fq2bam.py
  call_variants.py
  normalize.py
  annotate_multi.py
  merge_annotations.py
  custom_annotators.py    — present, not called from run_all.py right now
  fallback_fill.py
  dedupe_columns.py
  phase_variants.py       — new
```

## Requirements

- Docker
- NVIDIA GPU + drivers (Parabricks stages) + NGC access for the base image
- ~400GB+ disk for reference/annotation data (one-time)

## Build

```bash
docker build -t genomics-pipeline:test .
```

## Check environment (no GPU/network needed)

```bash
docker run --rm genomics-pipeline:test python3 check_functions.py
```

## Run the full pipeline

```bash
docker run --rm --gpus all -v /data:/data genomics-pipeline:test \
  --sample-id YOUR_SAMPLE \
  --fastq-r1 /data/path/to/R1.fastq.gz \
  --fastq-r2 /data/path/to/R2.fastq.gz
```

Add `--skip-download` once references + OC modules are already prepared
(skips stage 0/0.5 entirely).

## Data layout

Everything lives under `PIPELINE_DATA_MOUNT` (default
`/data/genomics-pipeline/data`):

```text
refs/               GRCh38.fa + bwa index, dbsnp.vcf.gz
annotation/         clinvar, gnomad (per-chrom), alphamissense
opencravat_modules/ OC_ANNOTATORS module data
opencravat_home/    OC's $HOME (config, not the ephemeral container one)
trim/ align/ calls/ norm/ annot/ merged/ filled/
final/              <sample>.annotated.tsv, <sample>.unphased.vcf.gz,
                    <sample>.phased.vcf.gz
phased/             intermediate whatshap working files
```

## Standalone stage usage

Every stage file has a `if __name__ == "__main__":` block, so you can run
any single stage directly without the full chain — useful for resuming
after a partial failure without redoing GPU-heavy work:

```bash
docker run --rm -v /data:/data --entrypoint python3 genomics-pipeline:test \
  phase_variants.py sample1 /data/.../sample1.norm.vcf.gz \
  /data/.../sample1.bam /data/.../GRCh38.fa
```
