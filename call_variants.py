import os

from config import CALLS_DIR
from utils import mkdirs, run


def call_variants(sample_id: str, bam_path: str, ref_fasta: str) -> str:
    mkdirs(CALLS_DIR)
    # This version of Parabricks' deepvariant requires --out-variants to end
    # in .vcf (errors out if given .vcf.gz directly). It does NOT reliably
    # auto-produce a bgzipped copy in every version/config, so we bgzip +
    # tabix it ourselves afterward to satisfy downstream stages that expect
    # a compressed, indexed .vcf.gz.
    out_vcf = f"{CALLS_DIR}/{sample_id}.vcf"
    out_vcf_gz = f"{out_vcf}.gz"

    run(["pbrun", "deepvariant", "--ref", ref_fasta, "--in-bam", bam_path,
         "--out-variants", out_vcf, "--num-gpus", "1"])

    if os.path.exists(out_vcf_gz):
        print(f"[call_variants] pbrun already produced {out_vcf_gz}")
    elif os.path.exists(out_vcf):
        print(f"[call_variants] bgzipping {out_vcf} -> {out_vcf_gz}")
        with open(out_vcf_gz, "wb") as f_out:
            run(["bgzip", "-c", out_vcf], stdout=f_out)
        run(["tabix", "-p", "vcf", out_vcf_gz])
    else:
        raise FileNotFoundError(f"Neither {out_vcf} nor {out_vcf_gz} was produced by pbrun deepvariant")

    return out_vcf_gz


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("usage: python call_variants.py <sample_id> <bam_path> <ref_fasta>")
        raise SystemExit(1)
    print(call_variants(sys.argv[1], sys.argv[2], sys.argv[3]))
