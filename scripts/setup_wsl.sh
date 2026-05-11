#!/usr/bin/env bash
# One-shot WSL/Ubuntu setup for Buildozer APK builds.
# Run inside Ubuntu (WSL): bash scripts/setup_wsl.sh
set -euo pipefail

echo "[1/4] Installing system packages required by python-for-android..."
sudo apt-get update
sudo apt-get install -y \
    git zip unzip openjdk-17-jdk python3 python3-pip python3-venv \
    autoconf libtool pkg-config zlib1g-dev libncurses-dev libncursesw5-dev \
    libtinfo-dev cmake libffi-dev libssl-dev build-essential ccache

echo "[2/4] Creating Python venv at ~/.aiodl-venv ..."
python3 -m venv ~/.aiodl-venv
source ~/.aiodl-venv/bin/activate

echo "[3/4] Installing Buildozer + Cython into the venv..."
pip install --upgrade pip
pip install buildozer cython==0.29.36

echo "[4/4] Done. To build the APK, run:"
echo "    source ~/.aiodl-venv/bin/activate"
echo "    bash scripts/build_apk.sh"
