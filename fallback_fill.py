import csv
import functools
import os
import time

import requests

from config import FILLED_DIR
from utils import mkdirs

REQUEST_TIMEOUT = 10
RATE_LIMIT = 0.34


def _get(url, params=None, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


def _post(url, json_body, headers=None):
    try:
        r = requests.post(url, json=json_body, headers=headers, timeout=REQUEST_TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


@functools.lru_cache(maxsize=4096)
def myvariant_lookup(chrom, pos, ref, alt):
    hgvs = f"chr{chrom.replace('chr', '')}:g.{pos}{ref}>{alt}"
    data = _get("https://myvariant.info/v1/variant/" + hgvs,
                params={"fields": "dbnsfp,clinvar,dbsnp"})
    time.sleep(RATE_LIMIT)
    return data


def dbnsfp_field(chrom, pos, ref, alt, *path):
    data = myvariant_lookup(chrom, pos, ref, alt)
    node = (data or {}).get("dbnsfp")
    for key in path:
        if isinstance(node, list):
            node = node[0] if node else None
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, list):
        node = node[0] if node else None
    return str(node) if node is not None else None


def api_clinvar(chrom, pos, ref, alt):
    data = myvariant_lookup(chrom, pos, ref, alt)
    clinvar = (data or {}).get("clinvar")
    if isinstance(clinvar, dict):
        rcv = clinvar.get("rcv")
        if isinstance(rcv, list) and rcv:
            return rcv[0].get("clinical_significance")
        if isinstance(rcv, dict):
            return rcv.get("clinical_significance")
    return None


def api_dbsnp(chrom, pos, ref, alt):
    data = myvariant_lookup(chrom, pos, ref, alt)
    if data and isinstance(data.get("dbsnp"), dict) and data["dbsnp"].get("rsid"):
        return data["dbsnp"]["rsid"]
    region = f"{chrom.replace('chr', '')}:{pos}-{pos}/{alt}"
    result = _get(f"https://rest.ensembl.org/vep/human/region/{region}",
                  headers={"Content-Type": "application/json"})
    time.sleep(RATE_LIMIT)
    if result and isinstance(result, list) and result[0].get("colocated_variants"):
        return result[0]["colocated_variants"][0].get("id")
    return None


def api_gnomad(chrom, pos, ref, alt):
    query = """query V($id: String!) { variant(variantId: $id, dataset: gnomad_r4) {
        genome { af } exome { af } } }"""
    vid = f"{chrom.replace('chr', '')}-{pos}-{ref}-{alt}"
    result = _post("https://gnomad.broadinstitute.org/api", {"query": query, "variables": {"id": vid}})
    time.sleep(RATE_LIMIT)
    v = (result or {}).get("data", {}).get("variant")
    if v:
        af = (v.get("genome") or {}).get("af") or (v.get("exome") or {}).get("af")
        return str(af) if af is not None else None
    return None


def api_civic(chrom, pos, ref, alt):
    query = """query V($chr: String!, $start: Int!, $stop: Int!) {
        coordinateEvidenceItems(chromosome: $chr, start: $start, stop: $stop) {
            edges { node { significance } } } }"""
    result = _post("https://civicdb.org/api/graphql",
                    {"query": query, "variables": {"chr": chrom.replace("chr", ""), "start": pos, "stop": pos}})
    time.sleep(RATE_LIMIT)
    edges = (result or {}).get("data", {}).get("coordinateEvidenceItems", {}).get("edges", [])
    return edges[0]["node"].get("significance") if edges else None


def api_gwas_catalog(chrom, pos, ref, alt):
    rsid = api_dbsnp(chrom, pos, ref, alt)
    if not rsid:
        return None
    result = _get(f"https://www.ebi.ac.uk/gwas/rest/api/singleNucleotidePolymorphisms/{rsid}/associations")
    time.sleep(RATE_LIMIT)
    assoc = (result or {}).get("_embedded", {}).get("associations")
    if assoc:
        traits = assoc[0].get("efoTraits") or []
        return traits[0].get("trait") if traits else None
    return None


def api_litvar(chrom, pos, ref, alt):
    rsid = api_dbsnp(chrom, pos, ref, alt)
    if not rsid:
        return None
    result = _get(f"https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/get/rs{rsid.lstrip('rs')}")
    time.sleep(RATE_LIMIT)
    return ",".join(str(p) for p in result["pmids"][:10]) if result and result.get("pmids") else None


def api_regulomedb(chrom, pos, ref, alt):
    c = chrom if chrom.startswith("chr") else f"chr{chrom}"
    result = _get("https://www.regulomedb.org/regulome-search/",
                  params={"regions": f"{c}:{pos}-{pos}", "genome": "GRCh38", "format": "json"})
    time.sleep(RATE_LIMIT)
    features = (result or {}).get("features")
    return (features[0].get("assembled_from") or str(features[0].get("ranking"))) if features else None


ANNOTATOR_FALLBACKS = {
    "clinvar__sig": api_clinvar,
    "gwas_catalog__trait": api_gwas_catalog,
    "litvar__pmids": api_litvar,
    "dbsnp__rs": api_dbsnp,
    "regulomedb__score": api_regulomedb,
    "gnomad3__af": api_gnomad,
    "alphamissense__am_class": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "alphamissense", "am_pathogenicity"),
    "cadd__phred": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "cadd", "phred"),
    "revel__score": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "revel", "score"),
    "sift__prediction": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "sift", "pred"),
    "polyphen2__prediction": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "polyphen2", "hdiv", "pred"),
    "provean__prediction": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "provean", "pred"),
    "dann__score": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "dann", "score"),
    "clinpred__prediction": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "clinpred", "pred"),
    "primateai__score": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "primateai", "pred"),
    "conservation__phylop": lambda c, p, r, a: dbnsfp_field(c, p, r, a, "phylop", "100way_vertebrate"),
}


def _is_missing(v):
    return v in ("", None, ".", "NA", "N/A")


def fallback_fill(sample_id: str, tsv_path: str) -> str:
    mkdirs(FILLED_DIR)
    out_tsv = f"{FILLED_DIR}/{sample_id}.filled.tsv"

    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    fill_counts = {col: 0 for col in ANNOTATOR_FALLBACKS}
    for row in rows:
        chrom, pos, ref, alt = row.get("base__chrom"), row.get("base__pos"), row.get("base__ref_base"), row.get("base__alt_base")
        if not (chrom and pos and ref and alt):
            continue
        for col, fn in ANNOTATOR_FALLBACKS.items():
            if col not in row or not _is_missing(row.get(col, "")):
                continue
            try:
                result = fn(chrom, int(pos), ref, alt)
            except Exception as e:
                print(f"[fallback] {col} failed for {chrom}:{pos}: {e}")
                result = None
            if result:
                row[col] = result
                row[f"{col}_fallback_used"] = "api_or_dbnsfp"
                fill_counts[col] += 1

    for col in ANNOTATOR_FALLBACKS:
        flag = f"{col}_fallback_used"
        if flag not in fieldnames and any(flag in r for r in rows):
            fieldnames.append(flag)

    with open(out_tsv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    for col, n in fill_counts.items():
        if n:
            print(f"[fallback] {col}: filled {n} missing values")

    return out_tsv


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python fallback_fill.py <sample_id> <tsv_path>")
        raise SystemExit(1)
    print(fallback_fill(sys.argv[1], sys.argv[2]))
