# LawTracker container image — produced by Fly's builder during `fly deploy`.
# Single-stage build; image is small enough that multi-stage adds complexity
# without meaningful payoff for our pilot scale.

FROM python:3.12-slim

WORKDIR /app

# Build deps for any wheels that need compiling (curl_cffi has C extensions).
# Removed after install to keep the runtime image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps. pyproject.toml + src/ together are enough for
# `pip install .` to build a wheel. data/ is intentionally not copied —
# the live app should not ship the pilot scout outputs.
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Trim build-only system packages now that everything is installed.
RUN apt-get purge -y gcc libffi-dev \
    && apt-get autoremove -y

# Fly maps internal_port (8080) → public 80/443 via fly.toml.
EXPOSE 8080

CMD ["uvicorn", "lawtracker.web:app", "--host", "0.0.0.0", "--port", "8080"]
