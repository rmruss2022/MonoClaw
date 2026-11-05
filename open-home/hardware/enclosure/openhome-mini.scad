// openhome mini — 3D-printable enclosure (parametric)
// Two printed parts: SHELL (upper body + top ring) and BASE (bottom plate + foot).
// Units: millimeters. Designed for FDM, PETG, 0.2 mm layers, 3-4 walls.
// Render one part at a time: set part = "shell" or "base" and F6/export STL.
//
//   Fits: Raspberry Pi 4, ReSpeaker Mic Array v2.0 (63 mm disc) on top,
//         3" driver + MAX98357A, 12-LED ring under a frosted diffuser insert.

part = "shell";          // "shell" | "base" | "preview"
$fn = 160;

// ---- master dimensions ----
outer_d      = 110;      // outer diameter
wall         = 2.4;      // shell wall thickness (3 perimeters @ 0.4 nozzle + skin)
height       = 128;      // total pod height
base_h       = 12;       // printed base plate height
grille_top   = 46;       // grille window starts this far below the top
grille_h     = 58;       // grille window height (fabric glued behind)
diffuser_d   = 90;       // frosted diffuser ring insert diameter
diffuser_recess = 3;     // depth the diffuser sits into the top
mic_ring_d   = 34;       // pitch circle for the 5 mic pinholes
mic_hole_d   = 2.2;
button_d     = 12;
usb_w        = 12;       // rear USB-C passthrough
usb_h        = 7;
boss_d       = 6.2;      // M2.5 heat-set insert boss OD (insert ~3.5 mm)
boss_id      = 3.4;      // insert pilot hole
inner_d      = outer_d - 2*wall;

// ---------- helpers ----------
module tube(h, od, id) difference(){ cylinder(h=h, d=od); translate([0,0,-1]) cylinder(h=h+2, d=id); }

module mic_holes(z){
  for (a=[0:72:359])
    rotate([0,0,a]) translate([mic_ring_d/2,0,z-1]) cylinder(h=wall+2, d=mic_hole_d);
  translate([0,0,z-1]) cylinder(h=wall+2, d=mic_hole_d);   // center port
}

module grille_window(){
  // vertical slots around the belly (fabric grille glued to the inside)
  slot_w = 3; gap = 3.4;
  circ = PI*(outer_d-2);
  n = floor(circ/(slot_w+gap));
  for (i=[0:n-1])
    rotate([0,0,i*360/n])
      translate([0,0,height-grille_top-grille_h])
        translate([(outer_d/2)-wall-1,-slot_w/2,0])
          cube([wall+2, slot_w, grille_h]);
}

module insert_boss(z){
  translate([0,0,z]) difference(){
    cylinder(h=height-z-wall, d=boss_d);
    translate([0,0,-1]) cylinder(h=height, d=boss_id);
  }
}

// ---------- SHELL (upper body) ----------
module shell(){
  difference(){
    union(){
      // body wall
      tube(height, outer_d, inner_d);
      // solid top dome plate
      translate([0,0,height-wall]) cylinder(h=wall, d=outer_d);
    }
    // diffuser recess in the top
    translate([0,0,height-diffuser_recess]) cylinder(h=diffuser_recess+1, d=diffuser_d);
    // mic pinholes + center
    mic_holes(height);
    // button hole
    translate([0, mic_ring_d, height-1]) cylinder(h=wall+2, d=button_d);
    // belly grille
    grille_window();
    // rear USB-C passthrough
    translate([outer_d/2-wall-1, -usb_w/2, base_h+6]) cube([wall+2, usb_w, usb_h]);
  }
  // 3x insert bosses to bolt the base up into the shell
  for (a=[0:120:359]) rotate([0,0,a]) translate([inner_d/2-boss_d/2-0.6,0,0]) insert_boss(0);
}

// ---------- BASE (bottom plate + foot) ----------
module base(){
  difference(){
    union(){
      cylinder(h=base_h, d=outer_d);
      // locating lip that nests inside the shell
      translate([0,0,base_h]) tube(4, inner_d-0.4, inner_d-2*wall);
    }
    // recess for a stick-on rubber ring foot
    translate([0,0,-1]) cylinder(h=2.4, d=outer_d-8);
    // 3x clearance holes for M2.5 screws up into the bosses
    for (a=[0:120:359]) rotate([0,0,a]) translate([inner_d/2-boss_d/2-0.6,0,-1]) cylinder(h=base_h+2, d=2.9);
    // vent slots for the Pi fan
    for (a=[0:30:359]) rotate([0,0,a]) translate([18,-1.4,-1]) cube([16,2.8,2.6]);
  }
}

if (part=="shell") shell();
else if (part=="base") base();
else { shell(); translate([0,0,-base_h-6]) base(); }   // exploded preview
