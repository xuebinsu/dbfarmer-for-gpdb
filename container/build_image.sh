#!/bin/bash

set -o errexit -o nounset -o pipefail -o xtrace

SRC_DIR=$*

install_deps() {
    sed -i s/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g /etc/apt/sources.list.d/debian.sources

    DEBIAN_FRONTEND=noninteractive apt-get update &&
        apt-get --no-install-recommends install -y \
            gcc \
            g++ \
            ca-certificates \
            curl \
            make \
            flex \
            bison \
            gettext-base \
            libapr1-dev \
            libbz2-dev \
            libcurl4-gnutls-dev \
            libevent-dev \
            libperl-dev \
            libreadline-dev \
            libxerces-c-dev \
            libxml2-dev \
            libyaml-dev \
            libzstd-dev \
            pkg-config \
            python3-dev >/dev/null

    apt-get clean
}

untar_as() {
    local tar_file=$1
    local dir=$2
    mkdir -p "$dir"
    tar -xzf "$tar_file" -C "$dir" --strip-components 1
}

install_gpdb() {
    untar_as "$SRC_DIR"/gpdb_src-*.tar.gz $HOME/gpdb_src
    pushd $HOME/gpdb_src
    mkdir -p $HOME/.local/gpdb
    ./configure --enable-debug --prefix=$HOME/.local/gpdb >/dev/null
    if ! make -j8 >/dev/null; then
        if ! make -j4 >/dev/null; then
            make >/dev/null
        fi
    fi
    make install >/dev/null
    popd

    export PATH=${PATH:-}:$HOME/.local/gpdb/bin
    export LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}:$HOME/.local/gpdb/lib
    echo "export PATH=${PATH}" >>"$HOME"/.profile
    echo "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}" >>"$HOME"/.profile

    rm -rf "$HOME"/gpdb_src
}

add_nonroot_user() {
    useradd -m "$PGUSER"
    export HOME=/home/$PGUSER
    mkdir "$HOME/pgdata"
    echo "export PGDATA=$HOME/pgdata" >>"$HOME"/.profile
}

install_extension() {
    untar_as "$SRC_DIR"/dbfarmer_src.tar.gz "$HOME"/dbfarmer_src
    pushd "$HOME"/dbfarmer_src
    make
    make install
    popd
}

clean() {
    chown -R "$PGUSER":"$PGUSER" "$HOME"
    rm -rf "${SRC_DIR:?}"/*
    apt-get purge -y gcc g++ python3 perl curl
    apt-get autoremove -y

    ls -lh $HOME
}

install_deps
add_nonroot_user
install_gpdb
install_extension
clean
