# Requirements and verification

## Accepted installation inputs

- 230 × 230 mm maximum model footprint; 55 mm wall-to-front envelope.
- 100 × 100 mm rear opening, 10 mm corner radii, centered on the backplate.
- Opening centre 240 mm below the wooden trim.
- PSU reserve 178 × 50 × 25 mm: conservative combination of the supplied
  178 × 50 × 24 mm product drawing and user's 175 × 50 × 25 mm measurements.
- MiBoxer FUT039S controller reserve 75 × 35 × 25 mm.
- Six Wago 221-413 three-conductor connectors, nominal envelope 18.8 × 18.6 × 8.4 mm.
- Two strips operated together; their ratings/electrical sizing are accepted as
  supplied. This project does not perform a strip-load audit.
- Black/gray PETG housing and trim; optional contrasting cosmetic Flux motif.
- PSU slot centres are approximate. A Y-adjustable mount and coupon precede
  the full print; transverse location is a spec parameter.
- Cable jacket diameter is an explicit fitting parameter, not inferred from
  conductor cross-section. The initial 7 mm value requires checking on the cable.

## Automated evidence

`checks/verify_hub.py` measures evaluated Blender geometry, including:

- Component envelopes against the backplate, cradle, holders, guard, and cover.
- Independent printed-part interference and clear rear access.
- Cover removal at installed, +1, +8, +24, and +60 mm positions with screws removed.
- Connector-lever, rising wire, controller-terminal, PSU-terminal, and cable-bundle
  service volumes. Construction envelopes are never exported as printable objects.
- PSU adjustment-slot travel, mounting-shaft paths, ring-pin registration,
  and centre-insert fit.
- Coupon parity against fresh sections of the actual modeled interfaces.
- Ray-measured wall thickness samples and the installation/depth envelope.

The shared build pipeline checks each print mesh for manifold closure, winding,
positive volume, expected shell count, material slots, and bed fit, then reads
STL and 3MF files back against the validated dimensions and volume. Boolean seam
vertices are merged by an editable 0.00005 mm Weld modifier, below fitting tolerances.

The Flux insert is a two-body 3MF: one black base and one contrasting connected
Y motif. Reactor arcs are separate gray parts. Keeping these arcs separate avoids
printing the large cover suspended above its raised decoration.

Physical validation remains necessary for the approximate PSU mounting pattern,
printed clip/nut fit, actual cable-clamp grip, and assembled operating temperature.
Ventilation is provided in upper, lower, and side edges; no thermal simulation,
electrical certification, or completed physical print is claimed.

## Revised mounting and cable routing

- Four primary slots: X = +/-80, Y = +/-103 mm; former center slots closed.
- Paired strip exit centers: X = +/-13 mm, aligned with centered external trunking.
- Validate wall-shaft travel, 10 mm washer space, full cable bores and a continuous
  upper/right routing reserve against evaluated printable geometry.
