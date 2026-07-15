# 🧬 FASTQ to Annotated Variants — The Complete Pipeline Guide

Raw reads in → GPU-accelerated alignment & variant calling → **25-module
OpenCRAVAT annotation** → a fully annotated TSV, plus a phased and an
unphased VCF.

Questions/issues: **nirmala@genepowerx.com**

> ⚖️ **Licensing note:** This pipeline's code is MIT-licensed (see `LICENSE`).
> The annotation *data* it downloads is not — each source sets its own
> terms, and a few (CADD, OMIM, SpliceAI, PrimateAI) require a paid
> commercial license and are excluded from this default configuration for
> that reason. Commercial users must independently verify and license any
> annotation source before commercial use. See `LICENSE` for details.

---

## 1. 🔬 From Raw Reads to Annotated, Phased Variants — What This Pipeline Does

Given a pair of paired-end FASTQ files for one sample, the pipeline runs
nine stages end to end and produces three final deliverables per sample:

1. `<sample>.annotated.tsv` — every variant, annotated across 25
   OpenCRAVAT modules (pathogenicity predictors, population frequency,
   ClinVar, OMIM, HPO, ClinGen, gene constraint, splice prediction, etc.)
2. `<sample>.unphased.vcf.gz` — the raw normalized variant calls
3. `<sample>.phased.vcf.gz` — the same calls, read-based phased with
   WhatsHap (haplotype-resolved, useful for compound-het analysis)

### Stage-by-stage workflow

```
[0]   download_references     Reference genome (GRCh38 + bwa index),
                                dbSNP, ClinVar, gnomAD, AlphaMissense.
                                Run ONCE, directly on the machine —
                                NOT inside Docker (see Step 1 below).
[0.5] install_opencravat        Installs the 25 OpenCRAVAT annotator
                                modules. One-time per module — already-
                                installed modules are skipped.
[1]   adapter_trim               fastp — trims sequencing adapters.
[2]   fq2bam                      Parabricks GPU-accelerated alignment
                                  to GRCh38 (BWA + sorting + BQSR).
[3]   call_variants                Parabricks GPU deepvariant — produces
                                    the raw VCF.
[4]   normalize                     bcftools norm — splits multiallelics,
                                    left-aligns indels.
[5]   annotate_multi                OpenCRAVAT — runs all 25 modules,
                                    joins variant-level and gene-level
                                    results, drops a few low-value/
                                    irrelevant columns.
[6]   merge_annotations              Carries the annotation table forward.
[7]   fallback_fill (optional)        Fills a handful of still-missing
                                      fields via external API/dbNSFP
                                      lookups. Slow on WGS-scale variant
                                      counts — skippable.
[8]   dedupe_columns                  Collapses exact-duplicate and
                                      semantically-overlapping columns →
                                      the final annotated TSV.
[9]   phase_variants                  WhatsHap phasing on the RAW/
                                      normalized VCF + BAM (not the
                                      annotated one) → unphased.vcf.gz
                                      + phased.vcf.gz.
```

---

## 2. 📥 Step 1 — Download Reference Data (Local Machine, NOT Docker)

Reference data (GRCh38 + bwa index, dbSNP, ClinVar, gnomAD,
AlphaMissense) is large (~400GB+) and only needs downloading **once per
machine**. Do this directly on the host — no GPU or container needed for
this step, so there's no reason to pay Docker's overhead for it.

**Requirements on the host:** `wget`, `tabix` (install via
`apt-get install -y wget tabix` if missing).

```bash
cd ~/genomics-pipeline
python3 download_references.py
```

This writes everything under `/data/genomics-pipeline/data/refs/` and
`/data/genomics-pipeline/data/annotation/`. It's safe to re-run — every
file is skipped if already present, and the whole stage short-circuits
instantly once a `.download_references_done` marker exists.

---

## 3. 📦 Step 2 — Get Sample FASTQ Data (Hugging Face)

Sample FASTQ files for testing are hosted here:

**https://huggingface.co/datasets/nirmala29/grch38-bwa-index**

```bash
mkdir -p /data/genomics-pipeline/data/fastq

wget -O /data/genomics-pipeline/data/fastq/sample2_R1.fastq.gz \
  https://huggingface.co/datasets/nirmala29/grch38-bwa-index/resolve/main/data/sample2_R1.fastq.gz

wget -O /data/genomics-pipeline/data/fastq/sample2_R2.fastq.gz \
  https://huggingface.co/datasets/nirmala29/grch38-bwa-index/resolve/main/data/sample2_R2.fastq.gz
```

For your own samples, place them anywhere under
`/data/genomics-pipeline/data/` and use their real paths in the commands
below.

---

## 4. ⚙️ Step 3 — Build the Docker Image

```bash
docker build -t genomics-pipeline:test .
```

Deployed via **NVIDIA Launchable**, which handles NGC access for the
Parabricks base image automatically — no manual `docker login` or NGC API
key setup needed. This installs bwa/samtools/bcftools/tabix, fastp,
WhatsHap, and OpenCRAVAT (its own isolated Python 3.11 environment). Only
needs redoing when the code or Dockerfile changes.

### Sanity-check before running anything heavy

```bash
docker run --rm genomics-pipeline:test python3 check_functions.py
```

Should report `ALL STAGES OK`.

---

## 5. 🚀 Step 4 — Run the Pipeline: Sub-Commands, Then the Main Command

**Everything lives under one root: `/data/genomics-pipeline/data/`.**
Every command below mounts it with `-v /data:/data`. Always include
`-e PYTHONUNBUFFERED=1` so progress prints live instead of one big burst
at the end.

References are already on disk from Step 1 — so `download_references`
(stage 0) is not run again here. Everything below picks up from stage 0.5
onward, in order.

### 5.1 Sub-commands — run each stage on its own, in order

Useful when testing, or resuming after a partial failure without redoing
completed (GPU-heavy) work. Paths below use `sample2` as the example —
substitute your own sample ID and the real paths its earlier stages wrote.

```bash
# [0.5] Install OpenCRAVAT's 25 annotator modules (one-time; skips already-installed ones)
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test install_opencravat.py

# [1] Trim adapters
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test adapter_trim.py sample2 \
  /data/genomics-pipeline/data/fastq/sample2_R1.fastq.gz \
  /data/genomics-pipeline/data/fastq/sample2_R2.fastq.gz

# [2] Align (GPU)
docker run --rm --gpus all -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test fq2bam.py sample2 \
  /data/genomics-pipeline/data/trim/sample2_R1.trimmed.fastq.gz \
  /data/genomics-pipeline/data/trim/sample2_R2.trimmed.fastq.gz \
  /data/genomics-pipeline/data/refs/GRCh38.fa \
  /data/genomics-pipeline/data/refs/dbsnp.vcf.gz

# [3] Call variants (GPU)
docker run --rm --gpus all -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test call_variants.py sample2 \
  /data/genomics-pipeline/data/align/sample2.bam \
  /data/genomics-pipeline/data/refs/GRCh38.fa

# [4] Normalize
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test normalize.py sample2 \
  /data/genomics-pipeline/data/calls/sample2.vcf.gz \
  /data/genomics-pipeline/data/refs/GRCh38.fa

# [5] Annotate (OpenCRAVAT, 25 modules)
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test annotate_multi.py sample2 \
  /data/genomics-pipeline/data/norm/sample2.norm.vcf.gz

# [6] Carry annotations forward
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test merge_annotations.py sample2 \
  /data/genomics-pipeline/data/annot/opencravat/sample2.export.tsv

# [7] Fallback fill — OPTIONAL, slow (skip for faster runs)
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test fallback_fill.py sample2 \
  /data/genomics-pipeline/data/merged/sample2.merged.tsv

# [8] Dedupe columns -> final annotated TSV
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test dedupe_columns.py sample2 \
  /data/genomics-pipeline/data/filled/sample2.filled.tsv
  # (if you skipped step 7, point this at sample2.merged.tsv instead)

# [9] Phase variants -> unphased.vcf.gz + phased.vcf.gz
docker run --rm -v /data:/data -e PYTHONUNBUFFERED=1 --entrypoint python3 \
  genomics-pipeline:test phase_variants.py sample2 \
  /data/genomics-pipeline/data/norm/sample2.norm.vcf.gz \
  /data/genomics-pipeline/data/align/sample2.bam \
  /data/genomics-pipeline/data/refs/GRCh38.fa
```

### 5.2 Main command — run everything above in one shot

Does exactly the sequence above (skipping stage 0, since references are
already downloaded from Step 1), for a fresh sample:

```bash
docker run --rm --gpus all -v /data:/data \
  -e PYTHONUNBUFFERED=1 \
  genomics-pipeline:test \
  --skip-download \
  --sample-id sample2 \
  --fastq-r1 /data/genomics-pipeline/data/fastq/sample2_R1.fastq.gz \
  --fastq-r2 /data/genomics-pipeline/data/fastq/sample2_R2.fastq.gz
```

Add `--skip-fallback-fill` to also skip stage 7 (see §5.1's note on why
it's slow):

```bash
  --skip-fallback-fill
```

---

## 6. 📊 Your Results: Annotated Variants, Phased & Unphased VCFs

Everything lands under `/data/genomics-pipeline/data/`:

| Path | Contents |
|---|---|
| `final/<sample>.annotated.tsv` | The final annotated variant table |
| `final/<sample>.unphased.vcf.gz` | Raw normalized calls |
| `final/<sample>.phased.vcf.gz` | WhatsHap-phased calls |
| `align/<sample>.bam` | Aligned reads |
| `calls/<sample>.vcf.gz` | Raw deepvariant output (pre-normalization) |
| `norm/<sample>.norm.vcf.gz` | Normalized calls (input to annotation + phasing) |
| `annot/opencravat/<sample>.export.tsv` | Raw OpenCRAVAT export before dedup |
| `trim/<sample>.fastp.html` | Adapter-trimming QC report |

### 🧩 Making Sense of the Annotation Columns

Columns are named `<module>__<field>`, e.g. `clinvar__sig`,
`gnomad3__af`, `sift__prediction`, `hpo__term`. A large fraction of
pathogenicity-predictor columns (SIFT, PolyPhen2, REVEL, CADD,
AlphaMissense, etc.) will be empty for most rows — that's expected, not
an error: those tools only score missense/coding variants, and most
variants in a whole genome are intronic or intergenic.

---

## 7. 🛠️ Quick Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| No output printing during a run | Missing `-e PYTHONUNBUFFERED=1` — output is buffered, not lost; add the flag |
| `File not found` errors on paths under `/data/...` | Path mismatch — everything must be under `/data/genomics-pipeline/data/`, matching the `-v /data:/data` mount |
| Code changes don't seem to take effect | Rebuild the image: `docker build -t genomics-pipeline:test .` |
| A stage fails partway through a long run | Re-run just that stage standalone (§5.1) using the outputs already sitting on disk from earlier stages — no need to redo alignment/variant-calling |
| Want to check the environment before running anything heavy | `docker run --rm genomics-pipeline:test python3 check_functions.py` |

For anything else, email **nirmala@genepowerx.com**.
