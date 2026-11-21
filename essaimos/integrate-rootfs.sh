#!/usr/bin/env bash
# Install Linux-optimized ESSAIM-OS/liquidctl into a live system or EssaimOS rootfs / chroot.
# Zero compilers and zero Pillow required (~0 MB RAM when no supported USB device is connected).
set -euo pipefail

ROOTFS="${1:-}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${ROOTFS}/opt/essaim/liquidctl"

install -dm755 "$TARGET_DIR" "${ROOTFS}/usr/local/bin" "${ROOTFS}/etc/udev/rules.d"
rm -rf "${TARGET_DIR}/liquidctl"
cp -r "$SRC_DIR/liquidctl" "${TARGET_DIR}/liquidctl"

# Write static version module if setuptools_scm did not pre-generate _version.py
if [[ ! -f "${TARGET_DIR}/liquidctl/_version.py" ]]; then
    cat > "${TARGET_DIR}/liquidctl/_version.py" <<'EOF'
version = "1.16.0-essaim-linux"
version_tuple = (1, 16, 0, "essaim-linux")
EOF
fi

cat > "${ROOTFS}/usr/local/bin/liquidctl" <<'EOF'
#!/bin/sh
export PYTHONPATH="/opt/essaim/liquidctl${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m liquidctl "$@"
EOF
chmod 755 "${ROOTFS}/usr/local/bin/liquidctl"

cat > "${ROOTFS}/usr/local/bin/liquidctl-essaim" <<'EOF'
#!/bin/sh
export PYTHONPATH="/opt/essaim/liquidctl${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m liquidctl.essaim_bridge "$@"
EOF
chmod 755 "${ROOTFS}/usr/local/bin/liquidctl-essaim"

if [[ -f "$SRC_DIR/extra/linux/71-liquidctl.rules" ]]; then
    install -Dm644 "$SRC_DIR/extra/linux/71-liquidctl.rules" "${ROOTFS}/etc/udev/rules.d/71-liquidctl.rules"
fi

echo "Installed Linux-optimized liquidctl + liquidctl-essaim into ${ROOTFS:-/}"
