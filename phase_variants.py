import os
import re
import shutil

from config import FINAL_DIR, PHASED_DIR
from utils import mkdirs, run


def fix_vcf_header(src: str, dst: str) -> None:
    """Strip unescaped inner double-quotes from ##INFO/##FORMAT Description
    fields. Some annotation tools (e.g. OpenCRAVAT) emit
    Description="...\"D\" (\"probably damaging\")..." — htslib's header
    parser chokes on that unescaped inner quoting and whatshap fails with
    "Could not parse the header line" / "INFO 'X' not defined in header".

    This pipeline now feeds whatshap the RAW/normalized deepvariant VCF
    (not the OpenCRAVAT-annotated one), which shouldn't have this problem
    in the first place — so this is a defensive no-op here, kept in case
    you ever point this stage at an annotated VCF instead.
    """
    with open(src, "r", errors="replace") as fin, open(dst, "w") as fout:
        for line in fin:
            if line.startswith("##INFO") or line.startswith("##FORMAT"):
                def clean_description(match):
                    desc_content = match.group(1)
                    desc_content = desc_content.replace('\\"', "")
                    desc_content = desc_content.replace('"', "")
                    return f'Description="{desc_content}"'

                line = re.sub(
                    r'Description="(.*?)"(?=>)',
                    clean_description,
                    line,
                    flags=re.DOTALL,
                )
            fout.write(line)


def phase_variants(sample_id: str, norm_vcf_gz: str, bam_path: str, ref_fasta: str) -> tuple[str, str]:
    """Produce both an unphased and a phased VCF for this sample, using the
    RAW/normalized (pre-annotation) VCF plus its BAM — not the OpenCRAVAT
    -annotated TSV/VCF. Phasing only needs genotypes + read evidence, so
    running it on the raw calls avoids OpenCRAVAT's header-quoting quirk
    entirely and doesn't require re-running annotation afterward.

    Returns (unphased_vcf_path, phased_vcf_path), both under FINAL_DIR.
    """
    mkdirs(PHASED_DIR, FINAL_DIR)

    # --- 1. Unphased ("normal") VCF: just the normalized calls, copied to
    # a clearly-labeled final path. Nothing to compute — it already is the
    # unphased VCF; this just makes it a first-class, obviously-named
    # deliverable alongside the phased one. ---
    unphased_vcf = f"{FINAL_DIR}/{sample_id}.unphased.vcf.gz"
    shutil.copy(norm_vcf_gz, unphased_vcf)
    if os.path.exists(f"{norm_vcf_gz}.tbi"):
        shutil.copy(f"{norm_vcf_gz}.tbi", f"{unphased_vcf}.tbi")
    else:
        run(["tabix", "-p", "vcf", unphased_vcf])
    print(f"[phase_variants] unphased VCF -> {unphased_vcf}")

    # --- 2. Fix header (no-op on this raw input, defensive) -> bgzip ->
    # bcftools index (.csi) -> whatshap phase. ---
    decompressed = f"{PHASED_DIR}/{sample_id}.norm.vcf"
    run(["bash", "-c", f"gunzip -c {norm_vcf_gz} > {decompressed}"])

    fixed_vcf = f"{PHASED_DIR}/{sample_id}.header_fixed.vcf"
    fix_vcf_header(decompressed, fixed_vcf)
    os.remove(decompressed)

    fixed_vcf_gz = f"{fixed_vcf}.gz"
    run(["bgzip", "-f", fixed_vcf])
    run(["bcftools", "index", "-f", fixed_vcf_gz])

    phased_bcf = f"{PHASED_DIR}/{sample_id}.phased.bcf"
    run([
        "whatshap", "phase",
        f"--reference={ref_fasta}",
        "-o", phased_bcf,
        fixed_vcf_gz, bam_path,
    ])
    if not os.path.exists(phased_bcf):
        raise RuntimeError(f"whatshap did not produce {phased_bcf}")

    # --- 3. Convert phased BCF -> vcf.gz + tabix index, for a uniform,
    # consistent final-output format matching every other VCF in this
    # pipeline (rather than leaving it as a .bcf). ---
    phased_vcf = f"{FINAL_DIR}/{sample_id}.phased.vcf.gz"
    run(["bash", "-c", f"bcftools view {phased_bcf} -Oz -o {phased_vcf}"])
    run(["tabix", "-p", "vcf", phased_vcf])
    print(f"[phase_variants] phased VCF -> {phased_vcf}")

    return unphased_vcf, phased_vcf


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 5:
        print("usage: python phase_variants.py <sample_id> <norm_vcf_gz> <bam_path> <ref_fasta>")
        raise SystemExit(1)
    print(phase_variants(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
