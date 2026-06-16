FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git zip unzip sudo \
    openjdk-17-jdk \
    python3-pip python3-setuptools python3-dev \
    patch autoconf automake build-essential \
    libtool pkg-config gettext \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libltdl-dev libssl-dev \
    && apt-get remove -y ccache \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -U builder && echo "builder ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER builder
WORKDIR /home/builder/hostcwd

ENV PATH="/home/builder/.local/bin:$PATH"
RUN pip3 install --user --no-cache-dir --upgrade buildozer Cython wheel pip setuptools virtualenv

RUN mkdir -p /home/builder/.gradle && \
    echo "org.gradle.logging.stacktrace=all" > /home/builder/.gradle/gradle.properties

ENTRYPOINT ["buildozer"]
