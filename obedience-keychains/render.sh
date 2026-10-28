#!/bin/sh
# Пересборка STL и превью. Пример своей клички:
#   openscad -o rio_dumbbell.stl -D 'NAME="РИО"' 1_dumbbell.scad
set -e
cd "$(dirname "$0")"
mkdir -p stl preview
for f in 1_dumbbell 2_paw_hand 3_border_collie 4_cones; do
  [ -f "$f.scad" ] || continue
  openscad -q -o "stl/$f.stl" "$f.scad"
  xvfb-run -a openscad -q --preview --imgsize=1200,900 --viewall --autocenter --colorscheme=Tomorrow \
    --camera=0,0,0,30,0,15,0 -o "preview/$f.png" "$f.scad"
done
