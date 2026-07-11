from config import TRIM_DIR
from utils import mkdirs, run


def adapter_trim(sample_id: str, fastq_r1: str, fastq_r2: str) -> tuple[str, str]:
    mkdirs(TRIM_DIR)
    out_r1 = f"{TRIM_DIR}/{sample_id}_R1.trimmed.fastq.gz"
    out_r2 = f"{TRIM_DIR}/{sample_id}_R2.trimmed.fastq.gz"
    run([
        "fastp", "--in1", fastq_r1, "--in2", fastq_r2,
        "--out1", out_r1, "--out2", out_r2,
        "--detect_adapter_for_pe", "--thread", "4",
        "--json", f"{TRIM_DIR}/{sample_id}.fastp.json",
        "--html", f"{TRIM_DIR}/{sample_id}.fastp.html",
    ])
    return out_r1, out_r2


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("usage: python adapter_trim.py <sample_id> <r1.fastq.gz> <r2.fastq.gz>")
        raise SystemExit(1)
    print(adapter_trim(sys.argv[1], sys.argv[2], sys.argv[3]))
