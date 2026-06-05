FROM nvidia/cuda:12.2.0-base-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    curl \
    wget \
    software-properties-common \
    unzip \
    git \
    poppler-utils \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    libgl1 libsm6 libxext6 libxrender-dev libpangocairo-1.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

RUN python -m pip install \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -U pip setuptools wheel

COPY demo/requirements.txt /tmp/requirements.txt
RUN python -m pip install \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    --no-cache-dir \
    -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

RUN python -m pip show \
    streamlit \
    opencv-python-headless \
    python-doctr \
    pdf2image \
    thefuzz \
    openpyxl

    WORKDIR /app
COPY . /app

CMD ["streamlit", "run", "demo/app.py", "--server.address=0.0.0.0", "--server.port=8501"]