set -eux

echo "Running linters..."
python3 -m pip install --upgrade pip setuptools

echo "Running linters..."
sh scripts/linters.sh || true
