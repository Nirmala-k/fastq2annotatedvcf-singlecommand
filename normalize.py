from config import NORM_DIR
from utils import mkdirs, run


def normalize(sample_id: str, vcf_path: str, ref_fasta: str) -> str:
    mkdirs(NORM_DIR)
    out_vcf = f"{NORM_DIR}/{sample_id}.norm.vcf.gz"
    run(["bcftools", "norm", "-m", "-any", "-f", ref_fasta, "-Oz", "-o", out_vcf, vcf_path])
    run(["tabix", "-p", "vcf", out_vcf])
    return out_vcf


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("usage: python normalize.py <sample_id> <vcf_path> <ref_fasta>")
        raise SystemExit(1)
    print(normalize(sys.argv[1], sys.argv[2], sys.argv[3]))
