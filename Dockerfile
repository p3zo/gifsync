FROM tensorflow/tensorflow:2.8.0

#apt-key del 3bf863cc && \
#    apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/3bf863cc.pub && \

RUN apt update -y && \
    rm -rf /var/lib/apt/lists/* && \
    apt clean -y && \
    apt update -y && \
    apt upgrade -y && \
    apt install -y --no-install-recommends autoconf automake pkg-config libtool ffmpeg

RUN pip3 install --no-cache -U pip && \
    pip install --no-cache pip-autoremove && \
    pip-autoremove tensorflow -y && \
    pip3 install --no-cache essentia-tensorflow Pillow ipython

WORKDIR /opt/gifsync
