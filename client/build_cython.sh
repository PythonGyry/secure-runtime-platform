#!/bin/bash
# Збірка Cython-розширень для bootstrap (Linux / macOS).
# З кореня проекту: bash client/build_cython.sh
# Потрібно: pip install cython, gcc (зазвичай вже є на Linux).

set -e
cd "$(dirname "$0")/.."
python client/cython_prebuild_cleanup.py
python setup_cython_bootstrap.py build_ext --inplace
echo "Cython build done."
