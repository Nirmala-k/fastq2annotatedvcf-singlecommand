# Base image: NVIDIA Clara Parabricks (provides pbrun, CUDA, GPU libs)
FROM nvcr.io/nvidia/clara/clara-parabricks:4.3.0-1

# Prevent apt from trying to open an interactive dialog (e.g. tzdata asking
# for timezone) during the build, which hangs with no terminal attached.
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# --- Python (use whatever python3 the base image ships, avoid PPAs that
# depend on reaching external keyservers, which is flaky in some build envs) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-distutils \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3 \
    && ln -sf $(command -v python3) /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

# --- CLI bioinformatics tools ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl unzip git ca-certificates \
    tabix samtools bwa \
    bcftools \
    build-essential zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# --- fastp (adapter trimming) ---
RUN wget -q http://opengene.org/fastp/fastp \
    && chmod a+x fastp \
    && mv fastp /usr/local/bin/

# --- whatshap (read-based phasing for phase_variants.py) ---
RUN pip install --no-cache-dir whatshap

# --- OpenCRAVAT (`oc` CLI) in its own isolated Python 3.11 venv ---
# open-cravat's codebase assumes Python 3.9+ (list[str]-style generics) and
# in places even 3.12+ (nested-quote f-strings). Whatever python3 this base
# image's `pip` was using when we installed open-cravat is an old 3.8, which
# chokes on both. Rather than patching open-cravat's source file-by-file
# (whack-a-mole), give it a real, modern, self-contained Python — fetched
# via `uv`, which downloads prebuilt interpreters over plain HTTPS and has
# no dependency on apt/PPAs/keyservers (which is what broke deadsnakes).
RUN pip install --no-cache-dir uv \
    && uv python install 3.11 \
    && UV_PY311=$(uv python find 3.11) \
    && echo "using interpreter: $UV_PY311" \
    && $UV_PY311 -m venv /opt/oc-venv \
    && /opt/oc-venv/bin/pip install --no-cache-dir open-cravat requests pytabix

# Even Python 3.11 doesn't support nested-quote f-strings (that needs 3.12),
# and open-cravat's cravat_web.py has exactly one: f'...{d['host']}...'.
# Patch that one line to use double quotes on the outside.
RUN CRAVAT_DIR=$(/opt/oc-venv/bin/python -c "import cravat, os; print(os.path.dirname(cravat.__file__))") \
    && CRAVAT_WEB="$CRAVAT_DIR/cravat_web.py" \
    && echo "patching: $CRAVAT_WEB" \
    && sed -i \
       -E "s/f'http:\/\/\{server_config\['host'\]\}:\{server_config\['port'\]\}'/f\"http:\/\/{server_config['host']}:{server_config['port']}\"/" \
       "$CRAVAT_WEB" \
    && /opt/oc-venv/bin/python -c "import cravat.oc" \
    && /opt/oc-venv/bin/python -c "import tabix" \
    && echo "oc-venv: cravat.oc and pytabix both import cleanly on Python 3.11"

# Expose oc/ocweb/ocx from the isolated venv on PATH, so `oc ...` anywhere
# in the pipeline transparently uses the working Python 3.11 env instead of
# the base image's Python 3.8.
RUN for bin in /opt/oc-venv/bin/oc /opt/oc-venv/bin/oc-*; do \
        [ -e "$bin" ] && ln -sf "$bin" "/usr/local/bin/$(basename "$bin")"; \
    done; true
ENV PATH="/opt/oc-venv/bin:${PATH}"

# --- Pipeline code ---
WORKDIR /app
COPY . /app

# Force unbuffered stdout/stderr — without this, Python block-buffers when
# stdout isn't a TTY (i.e. every `docker run` without -it), so all the
# pipeline's print() progress lines sit invisible in a buffer instead of
# showing up live, making it look like nothing is happening.
ENV PYTHONUNBUFFERED=1

# Data volume mount point (refs, fastq, outputs live here — mounted at runtime)
ENV PIPELINE_DATA_MOUNT=/data/genomics-pipeline/data
VOLUME ["/data"]

# Default entrypoint: run the full pipeline. Override args at `docker run` /
# Launchable job config time, e.g.:
#   docker run ... genomics-pipeline --sample-id X --fastq-r1 ... --fastq-r2 ...
ENTRYPOINT ["python3", "run_all.py"]
