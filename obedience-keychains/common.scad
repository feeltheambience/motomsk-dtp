// Общие параметры и функции для брелоков obedience
$fn = 64;

// Шрифт с кириллицей. На Windows можно поставить "Arial:style=Bold"
FONT = "Liberation Sans:style=Bold";

// Размер шрифта так, чтобы текст влез в max_w мм (для жирного шрифта ~0.68 ширины на символ)
function fit_size(txt, max_w, max_size) =
    min(max_size, max_w / (max(len(txt), 1) * 0.68));

module label(txt, max_w, max_size) {
    text(txt, size = fit_size(txt, max_w, max_size), font = FONT,
         halign = "center", valign = "center");
}

module rrect(w, h, r) {
    offset(r = r) square([w - 2 * r, h - 2 * r], center = true);
}

module capsule(p1, p2, d) {
    hull() { translate(p1) circle(d = d); translate(p2) circle(d = d); }
}

// Ушко под кольцо: круг с отверстием, к которому подходит основа
module eyelet_2d(pos, outer_d, hole_d) {
    translate(pos) difference() { circle(d = outer_d); circle(d = hole_d); }
}
