# ============================================================
#  BIMOS — package metadata REFERENCE (NOT USED BY THE BUILDER)
# ============================================================
#  !! ARCHIVED REFERENCE — DO NOT BUILD FROM THIS FILE. !!
#
#  The .deb is NOT produced from this spec. Nothing in the repository parses
#  it: the real packaging happens in builder.py::package_linux_deb(), which
#  passes equivalent metadata to fpm directly on the command line.
#
#  Keep this file only as human-readable documentation of the .deb metadata.
#  If you change packaging, change builder.py (the source of truth); mirror
#  the change here so the reference does not drift.
#
#  NOTE: this is a YAML-ish note, not a real RPM spec. An actual .rpm would
#  need the RPM %install/%files/%changelog macro syntax instead.
# ============================================================
#  Install fpm:  gem install fpm
#  Or via pip:   pip install fpm  (fpm-cookery)
#
#  Manual build example (equivalent to what builder.py runs):
#    fpm -s dir -t deb \
#        --name bimos \
#        --version 0.1.0 \
#        --architecture amd64 \
#        --description "Biomolecular Modeling Suite" \
#        --url "https://github.com/RenatoJVA/BIMOS" \
#        --maintainer "RenatoJVA <https://github.com/RenatoJVA/BIMOS/issues>" \
#        --license "GPLv3" \
#        --depends "docker.io >= 20.0" \
#        --depends "docker-compose-plugin >= 2.0" \
#        --after-install installer/postinst.sh \
#        --after-remove  installer/postrm.sh \
#        --deb-desktop-entries installer/assets/bimos.desktop \
#        backend/dist/bimos=/usr/bin/bimos \
#        backend/dockers=/opt/bimos/dockers \
#        backend/README.md=/usr/share/doc/bimos/README.md \
#        LICENSE=/usr/share/doc/bimos/LICENSE \
#        NOTICE.md=/usr/share/doc/bimos/NOTICE.md \
#        TERMS.md=/usr/share/doc/bimos/TERMS.md \
#        PRIVACY.md=/usr/share/doc/bimos/PRIVACY.md \
#        installer/assets/bimos.png=/usr/share/pixmaps/bimos.png
# ============================================================

# Payload mirror of builder.py::package_linux_deb() — kept for documentation.
# fpm-cookery keys below; note that builder.py does not read them.
name:         bimos
version:      0.1.0
architecture: amd64
description:  >
  Biomolecular Modeling Suite — virtual screening, docking,
  molecular dynamics and quantum chemistry in one desktop app.
url:          https://github.com/RenatoJVA/BIMOS
maintainer:   RenatoJVA <https://github.com/RenatoJVA/BIMOS/issues>
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
  - src: LICENSE
    dst: /usr/share/doc/bimos/LICENSE
  - src: NOTICE.md
    dst: /usr/share/doc/bimos/NOTICE.md
  - src: TERMS.md
    dst: /usr/share/doc/bimos/TERMS.md
  - src: PRIVACY.md
    dst: /usr/share/doc/bimos/PRIVACY.md
  - src: installer/assets/bimos.png
    dst: /usr/share/pixmaps/bimos.png
  - src: installer/assets/bimos.desktop
    dst: /usr/share/applications/bimos.desktop
