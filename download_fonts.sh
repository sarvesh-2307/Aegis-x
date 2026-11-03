#!/bin/bash
# AEGIS-X — Font Downloader
# Run this ONCE on Pi to download fonts locally
# Usage: bash download_fonts.sh

FONTS_DIR="$(dirname "$0")/static/fonts"
mkdir -p "$FONTS_DIR"

echo "📥 Downloading AEGIS-X fonts to $FONTS_DIR ..."
echo ""

# ── Orbitron ──────────────────────────────────────────────
echo "→ Orbitron Regular..."
curl -L "https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyGy6BoWgz.woff2" \
     -o "$FONTS_DIR/orbitron-v31-latin-regular.woff2" --silent --show-error

echo "→ Orbitron Bold (700)..."
curl -L "https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyGy6xuwWgz.woff2" \
     -o "$FONTS_DIR/orbitron-v31-latin-700.woff2" --silent --show-error

echo "→ Orbitron Black (900)..."
curl -L "https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyGy6FuwWgz.woff2" \
     -o "$FONTS_DIR/orbitron-v31-latin-900.woff2" --silent --show-error

# ── Share Tech Mono ────────────────────────────────────────
echo "→ Share Tech Mono Regular..."
curl -L "https://fonts.gstatic.com/s/sharetechmono/v15/J7aHnp1uDWRBEqV98dVQztYldFcLowEF.woff2" \
     -o "$FONTS_DIR/share-tech-mono-v13-latin-regular.woff2" --silent --show-error

echo ""
echo "✅ Fonts downloaded! Files in $FONTS_DIR:"
ls -lh "$FONTS_DIR"
echo ""
echo "🚀 Restart app.py — UI should now look identical to Live Server preview."