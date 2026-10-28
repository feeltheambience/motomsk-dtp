// Брелок №2 — ладонь с лапой внутри и командой
// Основа печатается первым цветом, рельеф (ладонь, ободок, команда) — вторым.
// На обороте зеркально выдавлена кличка.
include <common.scad>

/* [Текст] */
COMMAND = "FUSS!";     // команда: FUSS!, PLATZ!, SITZ!, HIER!, РЯДОМ!, ...
NAME    = "RIO";       // кличка на обороте ("" — без клички)
/* [Размеры, мм] */
D       = 40;          // диаметр жетона
BASE_H  = 3;           // толщина основы (смена цвета на этой высоте)
RELIEF  = 1.2;         // высота рельефа
RIM_W   = 1.6;         // ширина ободка
HOLE_D  = 4.2;
BACK_DEPTH = 0.6;      // глубина клички на обороте

module hand_2d() {
    // ладонь
    hull() for (p = [[-5, -4], [5, -4], [-5.5, 3], [5.5, 3]]) translate(p) circle(r = 2.6);
    // пальцы: указательный, средний, безымянный, мизинец
    capsule([-4.6, 3], [-5.4, 12.0], 3.7);
    capsule([-0.9, 3], [-1.0, 13.8], 3.8);
    capsule([ 2.8, 3], [ 3.4, 12.6], 3.6);
    capsule([ 5.8, 2], [ 7.4,  9.6], 3.2);
    // большой палец
    capsule([-5.5, -3], [-11.4, 3.2], 3.9);
}

module paw_2d() {
    // главная подушечка
    hull() { translate([0, -4.6]) scale([1.25, 0.8]) circle(r = 3);
             for (s = [-1, 1]) translate([s * 2.2, -3.0]) circle(r = 1.8); }
    // пальцы
    for (p = [[-4.5, -0.6, 15], [-1.6, 1.3, 5], [1.6, 1.3, -5], [4.5, -0.6, -15]])
        translate([p[0], p[1]]) rotate(p[2]) scale([0.82, 1]) circle(r = 1.55);
}

module tag_outline() {
    hull() { circle(d = D); translate([0, D / 2 + 1]) circle(d = 10); }
}
HOLE_Y = D / 2 + 1.5;

module tag() {
    difference() {
        union() {
            linear_extrude(BASE_H) tag_outline();
            color("white") translate([0, 0, BASE_H - 0.01]) linear_extrude(RELIEF) {
                // ободок
                difference() { tag_outline(); offset(delta = -RIM_W) tag_outline(); }
                // ладонь с вырезанной лапой
                translate([0.8, 2.5]) difference() { hand_2d(); translate([-0.2, 0.6]) paw_2d(); }
                // команда
                translate([0, -D / 2 + 9.6]) label(COMMAND, D - 14, 5.6);
            }
        }
        translate([0, HOLE_Y, -1]) cylinder(d = HOLE_D, h = 10);
        // кличка на обороте (зеркально)
        if (NAME != "") translate([0, 0, -0.01]) linear_extrude(BACK_DEPTH)
            mirror([1, 0]) label(NAME, D - 10, 8);
    }
}

tag();
