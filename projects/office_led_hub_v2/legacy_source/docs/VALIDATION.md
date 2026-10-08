# V2 validation

Run `20260907T134330-dc9ab742`: 88 project checks passed. Seventeen unchanged
STLs are byte-identical to v1, including the backplate, internal mounts,
clamps, guard, and both inserts. The cover-corner coupon reflects the revised
surface engraving. Detailed parity evidence is in `checks/v1_parity.json`.

The independent v2 build runs the original mounting, clearance, screw passage,
coupon, and wall-sample checks plus collision checks among new trim, cover,
and Flux insert. Armor is part of the removable cover assembly.

Generated evidence lives in the successful run's checks folder. Generic checks
include mesh integrity, print-bed fit, and STL/3MF readback parity.
Presentation views omit screws and wiring; component proxies are envelopes.

V1 physical-fit limitations still apply: print PSU, Wago, and cover-fastener
coupons first, and match the default 7 mm cable diameter to the actual jacket.
This experiment does not establish electrical certification or thermal behavior.

## 2026-09-11 mounting, cable exit, and cradle revision

Run `20260911T132541-cdd7e33f`: 123/123 model checks passed. Wall slots
are now +/-80 mm from center; the former center slots are closed. Both cable
exits are centered at +/-13 mm, and upper vents avoid the new cover relief.
A 7 by 16 mm upper/right route reserve clears equipment and printed parts,
turning inward around the upper-right cover column.

After the reported tight physical fit, the cradle opening was widened by the
requested 2 mm. Ray measurement on evaluated geometry gives 37.8 mm clear
width; the original screw centers remain aligned. A 37.6 mm body gauge fits
below the retaining lips. The new cradle coupon is cut from and checked against
the actual cradle. Its physical fit has not yet been tested.

Earlier v1 parity results above describe the September 7 run only. The backplate,
cover and cradle intentionally differ in this revision. Prior runs and release
archives are preserved. Cable routing overlays are schematic, not electrical
connection diagrams or measured bend-radius validation.
