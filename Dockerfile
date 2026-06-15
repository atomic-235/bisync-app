FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git zip unzip openjdk-17-jdk-headless \
    autoconf automake libtool pkg-config \
    libffi-dev libssl-dev libltdl-dev \
    sudo patch gnumake gcc cmake \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m builder && echo "builder ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER builder
WORKDIR /home/builder/hostcwd

ENV PATH="/home/builder/.local/bin:$PATH"
RUN pip3 install --user --no-cache-dir --upgrade buildozer Cython wheel pip setuptools virtualenv

ENTRYPOINT ["buildozer"]
