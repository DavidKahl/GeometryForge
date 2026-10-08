# Hardware, print orientation, and assembly

## Hardware

| Use | Quantity | Fastener |
|---|---:|---|
| Cover to backplate columns | 4 | M3 × 10 socket-head screws, M3 hex nuts |
| PSU mounting ears | 2 | M3 × 10 screws, M3 washers, M3 hex nuts |
| Controller cradle | 2 | M3 × 10 screws, M3 hex nuts |
| Six Wago holders | 6 | M3 × 6 screws, M3 hex nuts |
| Two cable clamps | 4 | M3 × 12 screws, M3 hex nuts |
| Supplementary terminal guard | 2 | M3 × 10 screws, M3 hex nuts |
| Installed centre insert | 3 | M3 × 10 countersunk screws, M3 hex nuts |
| Wall attachment | 4 | Wall-appropriate screws/plugs; nominal 4 mm screws with washers |

Total: 23 M3 nuts, 10 ordinary M3 × 10 screws, 3 countersunk M3 × 10 screws,
6 M3 × 6 screws, 4 M3 × 12 screws, and 2 PSU washers. Spare nuts are useful.
Use the cover screw heads without additional washers in their 6.8 mm recesses.
Confirm screw-tip clearance against the actual PSU ears using the mounting coupon.

The six Wagos are assumed to be **221-413**. Each holder is individually removable.
Their holders locate the connector body while leaving the operating levers and
wire entries open. Pigtails turn upward over the preceding row of connectors;
the scene includes these rising service envelopes.

## Print first

1. Print `coupon_psu_mount`, `coupon_wago_holder`, `coupon_cover_post`, and
   `coupon_cover_corner`. The post and corner form a matched cover-fastening test.
2. Check M3 nut fit and screw seating. Test one real Wago in its holder. Check
   the PSU ear, washer, and adjustment slot before printing the complete backplate.
3. The PSU fixing centres start at X = −99.5 / −65.5 and Y = −81 / +81 relative
   to the enclosure centre. The long slots allow ±4 mm of screw travel in Y.
   If the actual diagonal mounting pattern differs in X, update `PSU_FIXINGS`
   in the spec and regenerate; the photographed slot locations were approximate.
4. Measure the actual cable jacket. `CABLE_DIAMETER = 7.0` is a placeholder with
   0.6 mm diametral clearance. Set it to the cable in use and test the small clamp
   pair. Do not rely on an oversized opening to grip a smaller cable; use the
   adjacent tie anchors or a correctly dimensioned liner/clamp.

## Orientations and materials

Use the exported STL/3MF orientations. Backplate lies rear face down. Cover lies
front face down. Reactor arcs lie visible face down, with locating pegs printing
upward. Both centre discs lie back face down. The terminal guard lies roof down,
and clamp bars lie flat face down. Cradle and connector holders lie floor down.

Use PETG with a 0.4 mm nozzle; 0.2 mm layers and at least four perimeters are a
starting point. Nut-pocket roofs have short bridges. The terminal-guard screw
ears may need localized support in the supplied roof-down orientation; inspect
the slicer preview there. Keep support out of small screw passages and pockets.
The model does not prescribe a printer-specific G-code job.

The cover, backplate, and main guard have measured structural wall samples of
at least 2.4 mm. Deliberately thinner details include the cradle's compliant
uprights, small connector lips, cosmetic relief, and backed screw-head seats.
Physical clips and the PSU mounting pattern must be validated with the coupons.

## Assembly order

1. Load the underside nuts for the PSU adjustment channels and Wago holders
   before mounting the backplate. Turn the PSU nuts with their flats across the
   narrow sliding channels. Load the side-entry nuts for cover columns, cradle,
   guard, and cable saddles. The cable-saddle nut mouths face inward, toward −Y.
2. Offer the backplate over the opening and select wall fixings from the known
   cable routes. Primary slots are at X = +/-80, Y = +/-103. Alternative blind pilot
   marks are at X = ±104, Y = ±60; they are not pre-drilled holes. The schematic
   is not a cable-location guarantee or a scale drilling template.
3. Mount the PSU with its mains end downward and 24 V end upward. Its supports
   provide approximately 5 mm behind the metal case above the 4 mm plate.
   Do not cover the PSU's existing ventilation holes with extra padding.
4. Screw down the controller cradle. Its open ends expose both terminals; the
   small side lips provide loose retention. Avoid forcing the controller past
   the lips if the real case differs from its reserved envelope.
5. Attach the six Wago holders. Their channel order is V+, R, G, B, CW, WW in
   reading order, two columns by three rows. These are six independent
   distribution points, one per conductor, for two synchronously controlled
   strips. Final electrical connections follow the actual equipment labeling.
6. Keep mains routing in the lower-left corridor behind the supplementary guard;
   low-voltage bundles run in the upper/right areas. Use the tie anchors and leave
   service slack so releasing the decorative cover cannot pull terminals.
7. Fit the two top cable-clamping bars. The cover has an open-bottom relief around
   both saddles, so the cables remain fixed as the cover lifts into the room.
8. Locate the three reactor arcs on their pegs. Retain them with small suitable
   adhesive dots; the pegs locate the parts but are not snap fasteners.
9. Install either centre disc with its three countersunk screws and nuts from
   inside the cover. For the Flux version, print its grouped 3MF with contrasting
   material in slot 2. No light source or additional electronics are required.
10. Fit the cover and its four recessed screws. Tighten gently against the
    supporting columns. Removing these four screws releases the cover assembly;
    equipment, Wagos, guard, and cable clamps remain mounted.

Cable length includes the internal path and service slack in addition to the
distance toward the trim. The specified 240 mm is hole-centre-to-trim distance;
the enclosure top is only 125 mm below the trim.

This is a printed mechanical enclosure design, not a certified electrical or
fire enclosure. The supplementary printed guard does not confer certification.
Mechanical checks do not establish operating temperature; assess the assembled
installation's temperature and material suitability before continuous use.

## Centered cable exit revision

Wall slot centers are X = -80/+80, Y = -103/+103 mm (160 by 206 mm).
Install wall screws and 10 mm washers before the PSU and terminal guard.
The bottom-left screw is accessed with the guard removed. Slot edges sit
27.4 mm outside the vertical projection of the rear opening; confirm the actual
concealed cable route before drilling.

Both cable saddles and the matching cover relief now sit at X = -13/+13 mm.
Route strip bundles up the right side and across the top, then down into the
saddles at Z = 16 mm. Keep rear access clear. The external cable trunking is
centered on X = 0; it is an installation reference, not an added printed part.
Top vents move outboard to leave the centered lift-off relief unobstructed.
Cable/clamp diameters and hardware fits are unchanged.

The upper/right route reserves 7 mm width by 16 mm depth for two 7 mm jackets
stacked away from the wall; separate them before the centered saddles.
Confirm bend radius and grip with the real cable. Reprint both backplate and
cover for this revision: the previous cover has its cable relief on the right.

## Controller cradle physical-fit revision

The clear rail spacing is now 37.8 mm (previously 35.8 mm). The cradle grows
2 mm toward the center of the enclosure, retaining both mounting screw centers
and the right-side cable corridor. The nominal controller sits at X = 81 mm.
Print `coupon_controller_cradle` first: it is a 14 mm-long cross-section cut
from the real cradle, including the rails and retaining uprights/lips. Test the
widest part of the actual controller; no measured case width was supplied.
Slide the controller in through an open end rather than forcing the retaining
lips apart. The coupon verifies width/retention, not full-length screw access.
