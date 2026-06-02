# ============================================================
#  BIMOS — fpm package specification
#  Used by builder.py to generate .deb and .rpm
#
#  Install fpm:  gem install fpm
#  Or via pip:   pip install fpm  (fpm-cookery)
#
#  Manual build example:
#    fpm -s dir -t deb \
#        --name bimos \
#        --version 0.1.0 \
#        --architecture amd64 \
#        --description "Biomolecular Modeling Suite" \
#        --url "https://github.com/your-org/bimos" \
#        --maintainer "BIMOS Project <bimos@example.com>" \
#        --license "GPLv3" \
#        --depends "docker.io >= 20.0" \
#        --depends "docker-compose-plugin >= 2.0" \
#        --after-install installer/postinst.sh \
#        --after-remove  installer/postrm.sh \
#        --deb-desktop-entries installer/assets/bimos.desktop \
#        backend/dist/bimos=/usr/bin/bimos \
#        backend/dockers=/opt/bimos/dockers \
#        backend/README.md=/usr/share/doc/bimos/README.md \
#        installer/assets/bimos.png=/usr/share/pixmaps/bimos.png
# ============================================================

# This file is parsed by builder.py — do not rename keys.
name:         bimos
version:      0.1.0
architecture: amd64
description:  >
  Biomolecular Modeling Suite — virtual screening, docking,
  molecular dynamics and quantum chemistry in one desktop app.
url:          https://github.com/your-org/bimos
maintainer:   BIMOS Project <bimos@example.com>
license:      GPLv3
category:     science

recommends:
  - docker.io >= 20.0
  - docker-compose-plugin >= 2.0

files:
  - src: backend/dist/bimos
    dst: /usr/bin/bimos
    mode: "0755"
  - src: backend/dockers
    dst: /opt/bimos/dockers
  - src: backend/README.md
    dst: /usr/share/doc/bimos/README.md
  - src: installer/assets/bimos.png
    dst: /usr/share/pixmaps/bimos.png
  - src: installer/assets/bimos.desktop
    dst: /usr/share/applications/bimos.desktop
