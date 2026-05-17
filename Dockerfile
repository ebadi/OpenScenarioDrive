# ── Stage 1: build esmini shared libraries (headless, no OSG) ────────────────
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \
        pkg-config \
        libgl-dev \
        libpthread-stubs0-dev \
        libjpeg-dev \
        libpng-dev \
        libtiff5-dev \
        libxml2-dev \
        libxrandr-dev \
        libxinerama-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build - only the two library targets we need.
# Using --depth 1 for speed; pin to the same tag as this wrapper if desired.
ARG ESMINI_REF=master
ARG BUILD_JOBS=
RUN git clone --depth 1 --branch ${ESMINI_REF} \
        https://github.com/esmini/esmini.git /tmp/esmini \
    && cmake -S /tmp/esmini -B /tmp/esmini/build \
        -DUSE_OSG=false \
        -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/esmini/build \
        --target esminiLib esminiRMLib \
        ${BUILD_JOBS:+-j${BUILD_JOBS}} \
    && mkdir -p /out/esmini \
    && find /tmp/esmini/build -name "libesminiLib.so"    -exec cp {} /out/esmini/ \; \
    && find /tmp/esmini/build -name "libesminiRMLib.so"  -exec cp {} /out/esmini/ \; \
    && cp -r /tmp/esmini/resources /out/esmini/resources \
    && rm -rf /tmp/esmini


# ── Stage 2: runtime / test runner ───────────────────────────────────────────
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Libraries and bundled resources from the build stage
COPY --from=builder /out/esmini /app/esmini

# Install the esmini Python wrapper package and test runner
COPY esmini-python/ /app/esmini-python/
RUN pip install --no-cache-dir pytest /app/esmini-python

COPY conftest.py    /app/conftest.py
COPY pytest.ini     /app/pytest.ini
COPY tests/         /app/tests/

# Tell the wrapper where to find the shared libraries
ENV ESMINI_LIB_DIR=/app/esmini
# Tell the tests where the resources (xosc, xodr) live
ENV ESMINI_RESOURCE_PATH=/app/esmini/resources

# Default command: run the full test suite
CMD ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"]
