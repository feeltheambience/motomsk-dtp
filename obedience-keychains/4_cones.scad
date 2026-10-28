// Брелок №4 — «посыл в квадрат»: 4 конуса и собака в положении «лежать»
// Основа — цвет 1, рисунок и кличка — цвет 2 (смена на высоте BASE_H).
include <common.scad>

/* [Текст] */
NAME = "RIO";          // кличка внизу ("" — без клички)
/* [Опции] */
DOG_IN_SQUARE = true;  // собака внутри квадрата
/* [Размеры, мм] */
W       = 46;          // ширина жетона
H       = 36;          // высота жетона (без ушка)
BASE_H  = 3;
RELIEF  = 1.2;
RIM_W   = 1.5;
LINE_W  = 1.0;         // толщина линий квадрата
HOLE_D  = 4.2;

// углы квадрата в перспективе: передние шире задних
FRONT_Y = -3; BACK_Y = 9;
CORNERS = [[-16, FRONT_Y], [16, FRONT_Y], [10.5, BACK_Y], [-10.5, BACK_Y]];

// конус: s — масштаб (задние меньше)
module cone_2d(p, s) {
    translate(p) scale(s) difference() {
        union() {
            polygon([[-2.3, 0], [2.3, 0], [0.5, 7], [-0.5, 7]]);
            translate([0, 0.3]) rrect(6.6, 1.4, 0.5);          // подставка
        }
        // светоотражающая полоса — прорезь, видна основа
        polygon([[-1.55, 3], [1.55, 3], [1.25, 4.2], [-1.25, 4.2]]);
    }
}

// собака в положении «лежать» (сфинкс), вид сбоку, морда вправо
DOWN_DOG = [
 [0,0],[-3.2,0.2],[-3.4,1.1],[-0.4,1.4],[0.2,3],[2.2,5.2],[6,6.1],[10,6.6],
 [11.4,9],[12,11],[12.5,12.6],[13.4,13.5],[14.2,12.3],[15.2,11.7],[16.1,10.7],
 [17.9,10.1],[18.1,9.1],[16,8.5],[14.4,7.4],[13.8,5],[14.2,2],[18.6,1.7],
 [18.8,0]
];
module down_dog_2d() {
    difference() {
        polygon(DOWN_DOG);
        translate([14.9, 10.6]) circle(d = 1.1);   // глаз
    }
}

module tag_outline() {
    rrect(W, H, 6);
    // ушко сверху
    hull() {
        translate([0, H / 2 + 1.5]) circle(d = 10);
        translate([0, H / 2 - 4]) square([18, 1], center = true);
    }
}

NAME_Y = -H / 2 + 7.5;

module tag() {
    difference() {
        union() {
            linear_extrude(BASE_H) tag_outline();
            color("white") translate([0, 0, BASE_H - 0.01]) linear_extrude(RELIEF) {
                difference() { tag_outline(); offset(delta = -RIM_W) tag_outline(); }
                // стороны квадрата (между основаниями конусов)
                for (i = [0:3]) capsule(CORNERS[i], CORNERS[(i + 1) % 4], LINE_W);
                // конусы: задние меньше
                for (i = [0:3]) cone_2d(CORNERS[i], i < 2 ? 1 : 0.75);
                if (DOG_IN_SQUARE) translate([-8.2, FRONT_Y + 2.4]) scale(0.85) down_dog_2d();
                if (NAME != "") translate([0, NAME_Y]) label(NAME, W - 12, 6.5);
            }
        }
        translate([0, H / 2 + 1.5, -1]) cylinder(d = HOLE_D, h = 10);
    }
}

tag();
