// LED turret for the LabInt photometer body (photometer-body.stl), draft 1.
//
// A disc carrying four 5 mm LEDs, turned by a micro servo, brings one LED at a time
// in front of the body's LED hole. A fixed diffuser and aperture sit in the hole's
// Ø7 counterbore, so the cuvette always sees the same patch of light, and a cup
// closes the turret against room light.
//
// Coordinates are the body's own (mm): the optical axis runs along y, the LED face of
// the tower is the plane y = -16, the LED axis is at x = 0, z = 15.5, and the top of
// the base plate is z = 3. Parts are modelled in place; `part` selects what to show
// or export, laid flat for printing.
//
//   openscad -D 'part="assembly"' led_turret.scad
//   openscad -D 'part="cup"' -o cup.stl led_turret.scad
//
// Parts: front_plate, cup, disc, spacer, washer (print these in black),
//        diffuser (print in white or natural PLA, or cut it from PTFE or opal acrylic).

part = "assembly";   // assembly | front_plate | cup | disc | spacer | washer | diffuser
turn = 0;            // assembly only: which LED is in front of the hole (0..3)

$fn = 72;

// ── the body (measured from photometer-body.stl) ──
face_y    = -16;     // outer face of the LED tower
led_z     = 15.5;    // LED axis height
base_top  = 3;       // top of the base plate
tower_w   = 25;      // tower width (x)
tower_top = 22;
screw_dx  = 10;      // body screw holes at x = ±10, z = led_z: Ø2.6, 3.5 deep
cb_d      = 7;       // counterbore diameter
cb_depth  = 3.5;     // counterbore depth (then Ø5.2 through to the cuvette)

// ── optics: washer, diffuser and spacer stacked in the counterbore ──
washer_t  = 0.8;     // black aperture washer, at the bottom of the counterbore
ap_d      = 2.5;     // aperture diameter
diff_t    = 1.0;     // diffuser disc
spacer_t  = cb_depth - washer_t - diff_t;   // black spacer, pressed by the front plate
fit       = 0.15;    // radial clearance for parts that go into holes
channel_d = 5.4;     // light channel through the spacer and the front plate

// ── turret ──
n_led     = 4;
pitch     = 60;      // degrees between LEDs: 4 × 60° fits a 180° servo
R         = 12;      // LED pitch radius
axis_z    = led_z + R;
led_bore  = 5.2;     // 5 mm LED body
flange_bore = 6.2;   // a 5 mm LED's flange is Ø5.8 × 1
flange_t  = 1.2;
disc_t    = 8.6;     // flange to tip of a standard 5 mm LED
disc_r    = 16.5;
notch     = 1.0;     // detent notch depth on the rim
plate_t   = 3;
gap       = 0.6;     // between the front plate and the disc
disc_y0   = face_y - plate_t - gap;   // front face of the disc
disc_y1   = disc_y0 - disc_t;         // back face of the disc

// ── servo: MG90S / SG90 class. MEASURE YOURS and fix these before printing ──
horn_d    = 21;      // round horn diameter
horn_t    = 2;       // horn thickness, recessed into the back of the disc
horn_hole_r = 7.5;   // radius of the horn holes used to screw it to the disc (M2 self-tapping)
servo_l   = 22.8;    // case length
servo_w   = 12.2;    // case width
servo_shaft_off = 6; // shaft centre to the near end of the case
servo_hole_pitch = 27.8;
servo_boss_d = 12;   // raised boss around the shaft on top of the case
servo_shaft_h = 4;   // top of the case to the horn's flat face, horn fitted
servo_tab_drop = 4.5;// top of the case down to the top face of the mounting tabs

// ── cup: light-tight housing around the disc, carries the servo ──
cup_ri    = disc_r + 1;
wall      = 2;
cup_ro    = cup_ri + wall;
cup_y0    = face_y - plate_t - 0.2;     // front edge, inside the plate's lip
cup_yb    = disc_y1 - 1;                // inside face of the back wall
servo_top_y = disc_y1 - servo_shaft_h;  // top face of the servo case
tab_y     = servo_top_y - servo_tab_drop;   // tabs rest on the back wall's outer face
lip_ri    = cup_ro + 0.2;
lip_ro    = lip_ri + 1.8;
lip_h     = 3;
servo_cx  = -servo_shaft_off + servo_l / 2;    // case centre, along +x from the axis
servo_holes = [servo_cx - servo_hole_pitch / 2, servo_cx + servo_hole_pitch / 2];

// ── detent: a 3 mm steel ball and a small spring (a ballpoint-pen spring) in a boss on top ──
ball_d    = 3;
boss_d    = 8;
boss_h    = 9;       // above the cup's outer surface

// a cylinder along -y, from y0 to y0 - h
module ycyl(x, z, y0, h, d, d2 = undef) {
    translate([x, y0, z]) rotate([90, 0, 0]) cylinder(h = h, d1 = d, d2 = (d2 == undef ? d : d2));
}
// a 2D shape drawn in (x, z), extruded along -y from y0
module yext(y0, h) { translate([0, y0, 0]) rotate([90, 0, 0]) linear_extrude(h) children(); }

function led_angle(k) = 270 + k * pitch;   // LED k is at the bottom after turning the disc by -k·pitch

// ── front plate: screwed to the tower, holds the optics stack, takes the cup ──
module front_plate() {
    difference() {
        union() {
            yext(face_y, plate_t) union() {
                translate([-tower_w / 2, base_top]) square([tower_w, tower_top - base_top]);
                translate([0, axis_z]) circle(r = lip_ro);
            }
            ycyl(0, axis_z, face_y - plate_t, lip_h, 2 * lip_ro);
        }
        ycyl(0, axis_z, face_y - plate_t + 0.01, lip_h + 0.02, 2 * lip_ri);
        ycyl(0, led_z, face_y + 0.01, plate_t + 0.02, channel_d);
        for (sx = [-1, 1]) {   // countersunk, flush: the disc turns over the heads
            ycyl(sx * screw_dx, led_z, face_y + 0.01, plate_t + 0.02, 3.2);
            ycyl(sx * screw_dx, led_z, face_y - plate_t + 1.6, 1.61, 3.2, 6.2);
        }
    }
}

// ── disc with the four LEDs ──
module disc() {
    difference() {
        ycyl(0, axis_z, disc_y0, disc_t, 2 * disc_r);
        for (k = [0 : n_led - 1]) {
            a = led_angle(k);
            x = R * cos(a); z = axis_z + R * sin(a);
            ycyl(x, z, disc_y0 + 0.01, disc_t + 0.02, led_bore);
            ycyl(x, z, disc_y1 + flange_t, flange_t + 0.01, flange_bore);
            // V notch on the rim, opposite the LED: the ball drops in when this LED is at the bottom
            b = a + 180;
            yext(disc_y0 + 0.01, disc_t + 0.02)
                translate([disc_r * cos(b), axis_z + disc_r * sin(b)]) rotate(b + 45)
                    square(notch * sqrt(2), center = true);
        }
        ycyl(0, axis_z, disc_y1 + horn_t, horn_t + 0.01, horn_d + 0.4);   // horn recess
        ycyl(0, axis_z, disc_y0 + 0.01, disc_t + 0.02, 6);                 // access to the horn screw
        for (a = [45 : 90 : 315])                                          // pilot holes, M2 self-tapping
            ycyl(horn_hole_r * cos(a), axis_z + horn_hole_r * sin(a), disc_y0 + 0.01, disc_t + 0.02, 1.6);
    }
}

// ── cup: side wall and a thick back wall with a pocket for the servo ──
module cup() {
    back_t = cup_yb - tab_y;
    difference() {
        union() {
            ycyl(0, axis_z, cup_y0, cup_y0 - cup_yb, 2 * cup_ro);
            yext(cup_yb, back_t) hull() {
                translate([0, axis_z]) circle(r = cup_ro);
                for (x = servo_holes) translate([x, axis_z]) circle(r = 3.5);
            }
            // detent boss, run back to the back wall as a rib so that it prints without support
            hull() for (y = [disc_y0 - disc_t / 2, cup_yb - 1])
                translate([0, y, axis_z + cup_ri - 1]) cylinder(d = boss_d, h = cup_ro - cup_ri + boss_h + 1);
        }
        ycyl(0, axis_z, cup_y0 + 0.01, cup_y0 - cup_yb + 0.01, 2 * cup_ri);
        // pocket for the part of the servo case above its tabs
        translate([servo_cx - servo_l / 2 - 0.3, tab_y - 0.01, axis_z - servo_w / 2 - 0.3])
            cube([servo_l + 0.6, servo_top_y - tab_y + 0.01, servo_w + 0.6]);
        // shaft and boss
        translate([0, cup_yb + 0.01, 0]) rotate([90, 0, 0])
            linear_extrude(cup_yb - servo_top_y + 0.02)
                hull() for (x = [0, 5]) translate([x, axis_z]) circle(d = servo_boss_d + 0.6);
        for (x = servo_holes) ycyl(x, axis_z, tab_y + 6, 6.01, 1.8);   // M2 self-tapping, 6 deep
        // detent bore: ball and spring, closed by an M3 grub screw threaded into Ø2.5
        translate([0, disc_y0 - disc_t / 2, axis_z + cup_ri - 2]) {
            cylinder(d = ball_d + 0.2, h = 2 + (cup_ro - cup_ri) + boss_h - 5);
            cylinder(d = 2.5, h = 40);
        }
        // wire exit, high on one side and away from the light path: seal it after wiring
        translate([-cup_ro - 1, cup_yb + 3, axis_z + 6]) rotate([0, 90, 0]) cylinder(d = 4, h = 6);
    }
}

module spacer() {
    difference() {
        ycyl(0, led_z, face_y + spacer_t, spacer_t, cb_d - 2 * fit);
        ycyl(0, led_z, face_y + spacer_t + 0.01, spacer_t + 0.02, channel_d);
    }
}
module diffuser() { ycyl(0, led_z, face_y + cb_depth - washer_t, diff_t, cb_d - 2 * fit); }
module washer() {
    difference() {
        ycyl(0, led_z, face_y + cb_depth, washer_t, cb_d - 2 * fit);
        ycyl(0, led_z, face_y + cb_depth + 0.01, washer_t + 0.02, ap_d);
    }
}

// ── rough servo and LEDs, for the assembly preview only ──
module servo_dummy() {
    color("steelblue") {
        translate([servo_cx - servo_l / 2, servo_top_y - 22.5, axis_z - servo_w / 2]) cube([servo_l, 22.5, servo_w]);
        translate([servo_cx - 16.25, tab_y - 2.5, axis_z - servo_w / 2]) cube([32.5, 2.5, servo_w]);
    }
}
module leds_dummy() {
    cols = ["red", "orange", "green", "blue"];
    for (k = [0 : n_led - 1]) {
        a = led_angle(k) - turn * pitch;
        color(cols[k]) ycyl(R * cos(a), axis_z + R * sin(a), disc_y0 - 0.2, 8.4, 5);
    }
}
module turned() { translate([0, 0, axis_z]) rotate([0, turn * pitch, 0]) translate([0, 0, -axis_z]) children(); }

// print orientation: y = y_bed goes on the bed, the part grows along +z
module lay_down(y_bed, toward_minus_y = true) {
    if (toward_minus_y) translate([0, 0, y_bed]) rotate([-90, 0, 0]) children();
    else translate([0, 0, -y_bed]) rotate([90, 0, 0]) children();
}

if (part == "assembly") {
    color("gainsboro") import("../photometer-body.stl.stl");
    color("#555") front_plate();
    color("#222") { spacer(); washer(); }
    color("white") diffuser();
    color("#444") turned() disc();
    leds_dummy();
    %cup();
    servo_dummy();
} else if (part == "front_plate") lay_down(face_y) front_plate();
else if (part == "cup")      lay_down(tab_y, false) cup();
else if (part == "disc")     lay_down(disc_y0) disc();
else if (part == "spacer")   lay_down(face_y + spacer_t) spacer();
else if (part == "washer")   lay_down(face_y + cb_depth) washer();
else if (part == "diffuser") lay_down(face_y + cb_depth - washer_t) diffuser();
