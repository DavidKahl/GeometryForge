# Office LED distribution hub — v2 reactor experiment

This independent variant preserves v1's internal layout, cover fasteners,
centre-insert interface, and 230 × 230 × 55 mm envelope. V1 remains available
under `projects/office_led_hub/` with its original outputs.

V2 adds wider stepped reactor arcs with inward spokes, machined edge chamfers,
four separate angular corner armor panels, perimeter grooves, and calibration
marks around the centre insert. The four armor pieces print face down in gray
PETG and attach with suitable adhesive dots, leaving their 9 mm openings aligned
over the original cover screws. They lift away with the cover. All v1 mounting
hardware and internal parts remain compatible.

230 × 230 × 55 mm wall enclosure with a reactor cover and interchangeable plain
and Flux-inspired centre inserts. All dimensions are millimeters. XY is the wall
plane, +Y points toward the wooden trim, and +Z points into the room.

The backplate surrounds a centered **100 × 100 mm R10 opening**. The PSU sits to
its left, the controller to its right, and six Wago holders below the controller.
The hole stays accessible when the cover is removed. Centering this enclosure
on the measured wall opening leaves 125 mm below the wooden trim.

## Build and inspect

```powershell
.venv/Scripts/python.exe -m geometryforge build office_led_hub_v2
.venv/Scripts/python.exe -m geometryforge verify office_led_hub_v2
```

`out/office_led_hub_v2/build.json` points to the latest attempt and its status.
Successful runs contain `models/model.blend`, individual STL and 3MF files under
`prints/`, section contact sheets under `previews/`, and measured checks under
`checks/`. The editable scene retains Boolean and seam-weld modifiers. Printable
objects use assembly coordinates; exports orient and centre each printed part.
The plain insert and coupons are parked aside and hidden in the default render.

For the additional presentation views:

```powershell
E:/Blender/blender.exe --background --python projects/office_led_hub_v2/tools/render_views.py -- --blend <run>/models/model.blend --out <run>/previews
.venv/Scripts/python.exe projects/office_led_hub_v2/tools/layout_diagram.py --run <run> --out <run>/previews
.venv/Scripts/python.exe projects/office_led_hub_v2/tools/package_release.py
```

See [assembly and hardware](docs/ASSEMBLY.md) and
[requirements and validation](docs/REQUIREMENTS.md). Parameters live in
`models/spec.py`. Save authored manual revisions under `blender/`; export them
using `python -m geometryforge export office_led_hub_v2 --blend <file>`.

The package command writes `out/office_led_hub_v2/office_led_hub_v2.zip` from the
latest successful run, including print files, the editable scene, previews,
reports, and project sources. See the [validation record](docs/VALIDATION.md).

## Print set

- Backplate, removable cover, three gray reactor-ring segments.
- Plain centre insert, or two-colour Flux insert (base plus Y motif in one 3MF).
- Controller cradle, six individual Wago holders, two cable-clamping bars.
- Supplementary mains-terminal guard.
- PSU-mount coupon, cover-post/corner coupon pair, and Wago-holder coupon.

Black PETG is the default body material; gray PETG is the reactor trim. The Flux
motif can use contrasting PETG or an appropriate separate cosmetic material.
The gray ring segments print separately and locate on small pegs; this keeps the
large cover flat on its front face during printing. The revised Flux disc prints front
face down, with a flush translucent through-inlay. Generic exports record
filament slots, not the contents of the printer's AMS.

## Installation revision

Primary wall slots now sit at X = +/-80, Y = +/-103 mm, outside the vertical
projection of the rear opening. Both strip exits and matching cover reliefs
are centered at X = +/-13 mm. Route bundles inward around the upper-right cover
post, across the top, then into the saddles. Previous generated runs are retained.
The mounting layout reads evaluated backplate geometry from the verified run.

The controller cradle has a 37.8 mm clear rail width after the reported tight
physical fit. Mounting holes stay unchanged. Print the new
`coupon_controller_cradle` cross-section before the replacement cradle.

## Revise only the Flux insert

```powershell
.venv/Scripts/python.exe -m geometryforge revise office_led_hub_v2 --run out/office_led_hub_v2/runs/20260911T132541-cdd7e33f --part insert_flux --recipe tools/revise_flux.py --check checks/verify_flux.py
```

The upright Y and black disc are separate closed solids in one 3MF. Assign black
PETG to material 1 and translucent PETG to material 2. Both touch the bed on their
visible face. The flat disc is 130 x 3 mm; no raised rim or screw pads remain.
Seat dimensions are 6.4 mm mouth, 3.4 mm neck, 1.6 mm depth; the check uses a
6.3/3.3 mm head gauge with 0.05 mm radial allowance. Confirm your actual screws.

`tools/flux_coupon.py` cuts a 22 x 30 mm two-material coupon from the saved revised
insert. `tools/flux_preview.py --run <revision>` produces installed-front and
through-section views. Test the coupon for head seating, bonding, and surface
finish before printing the insert. A slicer's top view shows the back because
the visible face is down; the installed-front preview shows the intended Y.


## Run as a standalone folder

Copy this complete folder anywhere, install GeometryForge with the required backend
extras, and open the folder in the browser UI. No Git account is required.
From inside the copied folder, use `geometryforge build .` and `geometryforge verify .`.
The named-project commands above are checkout conveniences. Generated files live
in this folder's `out/` when it is copied outside the framework checkout.
