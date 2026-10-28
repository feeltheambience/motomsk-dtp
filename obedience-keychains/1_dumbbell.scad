// Брелок №1 — апорт-гантель с кличкой
// Печать плашмя, без поддержек. Смена цвета на высоте BAR_H (кличка).
include <common.scad>

/* [Текст] */
NAME = "RIO";          // кличка собаки
/* [Размеры, мм] */
PLATE_W = 9;           // ширина «блина» (по длине гантели)
PLATE_H = 24;          // высота «блина»
PLATE_T = 7;           // толщина «блинов»
BAR_L   = 36;          // длина перекладины между блинами
BAR_H   = 9;           // высота перекладины
BAR_T   = 5;           // толщина перекладины
TEXT_H  = 0.8;         // высота рельефа клички
HOLE_D  = 4.2;         // отверстие под кольцо

TOTAL_L = BAR_L + 2 * PLATE_W;
px = BAR_L / 2 + PLATE_W / 2;   // центр блина по X

module plate_2d() { rrect(PLATE_W, PLATE_H, 2.5); }

module dumbbell() {
    difference() {
        union() {
            // перекладина со скруглёнными кромками
            linear_extrude(BAR_T) rrect(BAR_L + 2, BAR_H, 1.5);
            // блины
            for (s = [-1, 1]) translate([s * px, 0, 0]) linear_extrude(PLATE_T) plate_2d();
        }
        // отверстие в левом блине
        translate([-px, PLATE_H / 2 - 4.6, -1]) cylinder(d = HOLE_D, h = PLATE_T + 2);
        // декоративные пазы на блинах
        for (s = [-1, 1]) translate([s * px, 0, PLATE_T - 0.6])
            linear_extrude(1) for (y = [-6, 0]) translate([0, y]) rrect(PLATE_W - 3.5, 1.2, 0.5);
    }
    // кличка на перекладине (второй цвет)
    color("white") translate([0, 0, BAR_T])
        linear_extrude(TEXT_H) label(NAME, BAR_L - 4, BAR_H - 3);
}

dumbbell();
