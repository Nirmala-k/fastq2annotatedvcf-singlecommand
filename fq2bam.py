from config import ALIGN_DIR
from utils import mkdirs, run


def fq2bam(sample_id: str, fastq_r1: str, fastq_r2: str, ref_fasta: str, known_sites: str) -> str:
    mkdirs(ALIGN_DIR)
    out_bam = f"{ALIGN_DIR}/{sample_id}.bam"
    run([
        "pbrun", "fq2bam",
        "--ref", ref_fasta,
        "--in-fq", fastq_r1, fastq_r2,
        "--knownSites", known_sites,
        "--out-bam", out_bam,
        "--out-recal-file", f"{ALIGN_DIR}/{sample_id}.recal.txt",
        "--num-gpus", "1",
    ])
    return out_bam


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print("usage: python fq2bam.py <sample_id> <r1> <r2> <ref_fasta> <known_sites>")
        raise SystemExit(1)
    print(fq2bam(*sys.argv[1:6]))
