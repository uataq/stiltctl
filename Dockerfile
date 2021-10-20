FROM python:3.9.0-buster

WORKDIR /src

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1
ENV TZ UTC

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libhdf5-serial-dev \
    libmagic-dev \
    libnetcdf-dev \
    libssl-dev \
    locales \
    netcdf-bin \
    procps \
    r-base \
    r-base-dev \
    unzip \
    wget \
    && locale-gen en_US.UTF-8 \
    && update-locale \
    && rm -rf /var/lib/apt/lists/*

ENV TINI_VERSION v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

# Pull STILT framework.
#   https://github.com/uataq/stilt/commit/733d95712072c7a13cfc6a9a0106d712f480c002
ENV STILT_PATH /usr/local/stilt
RUN git clone --depth=1 \
    https://github.com/uataq/stilt ${STILT_PATH} \
    && (cd ${STILT_PATH} \
    && ./setup \
    && Rscript r/dependencies.r)

# Install python dependencies.
COPY . .
RUN pip install --upgrade pip \
    && pip install .

CMD [ "stiltctl", "--help" ]
