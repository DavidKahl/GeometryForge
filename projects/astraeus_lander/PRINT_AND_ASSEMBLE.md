# Astraeus Heavy Lander — 480 mm display model

Designed for your stated **Bambu X2D, 0.4 mm nozzle, 256 mm bed**. Nominal scale is 1:150. Hull diameter is 56.67 mm; assembled height is 480 mm. This is a detailed printable interpretation of your concept image.

## Files and colors

The release contains 27 model pieces plus two fit-coupon rings. STL files use millimeters. Each part's 3MF retains its intended print orientation; it is a geometry file, not a preapproved printer job. Use either the STL set or the 3MF set, not both.

| Pieces | Quantity | Suggested finish | Print position |
|---|---:|---|---|
| `aft_hull`, `tank_lower`, `tank_upper`, `cargo` | 4 | Silver / metallic gray | Upright, open end on plate |
| `nose` | 1 | Silver / metallic gray | Broad end down |
| `nose_tip` | 1 | Black | Socket end down |
| `thermal_band` | 1 | Black / dark gray | Upright sleeve |
| `aft_fin_1`–`aft_fin_4` | 4 | Dark gray | Flat back down; relief up |
| `canard_1`–`canard_4` | 4 | Dark gray | Flat back down; relief up |
| `leg_1`–`leg_4` | 4 | Dark gray, optional silver piston paint | Sideways as exported; supports needed |
| `engine_mount` | 1 | Dark gray | Broad circular face down; support socket ceilings if needed |
| `engines_1`–`engines_7` | 7 | Dark metallic gray | Bell opening down |
| `coupon_1`, `coupon_2` | 2 | Any intended hull filament | Upright rings |

Numbered duplicate fins/canards/legs are separate positions in the assembly. Print one of every delivered filename. The seven bell STLs are positioned as a cluster in their shared coordinate system; auto-arrange them as separate objects if importing the STLs. The engine 3MF already contains all seven bells. The coupon 3MF contains both rings.

## Slicing and first print

1. Open the coupon in Bambu Studio. Choose the installed **Bambu Lab X2D 0.4 nozzle** preset and your actual filament and build plate.
2. Start with **0.16 mm High Quality**, three walls, and 15% gyroid. The engraved seams and 1.3 mm recessed fasteners benefit from 0.12 mm layers; this is an optional finish improvement. Keep model scale at 100%.
3. Print and test the coupon. The intended radial clearance is **0.30 mm per side**, equivalent to 0.60 mm diameter difference. It should slide without forcing. Printer calibration, filament and first-layer expansion affect the result.
4. If necessary, change `clearance_mm` through the agent and regenerate both backends. Global XY scaling would also change the visual dimensions and unrelated interfaces.
5. Print the hull sections upright. Collars have internal lead-in slopes; inspect the sliced collar transitions and small window/tab-pocket bridges. Avoid filling the long hollow bodies with unnecessary automatic support.
6. Fins and canards have a flat back and relief on their upper print face. Legs retain wider feet and projecting piston detail: enable supports **from the build plate** for their undersides and inspect the support preview. Their actual layer orientation is sideways, not standing on the deployed foot.
7. Use a brim for small engine-bell rims and tall narrow shells if your bed adhesion needs it. Check the first layers of the bells and sleeve in the slicer. Use support under the bulkhead's blind socket ceilings if bridging that diameter is unreliable with your material.

The local slicing evidence uses Generic PLA and a textured PEI plate as stated assumptions. It does not know the filament currently loaded in your printer. Review your own settings before printing. No print is started by the project tools.

## Assembly order

1. Remove supports, deburr tab edges and lightly clean any elephant's foot from mating rings. Test-fit before applying glue.
2. Stack `aft_hull` → `tank_lower` → `tank_upper` → `cargo` → `nose`. The collar projects upward from each lower section. Rotate the lower two hull sections so their four fin sockets align. These main collars are circular slip fits; the fin tabs establish angular alignment.
3. Slide the black `thermal_band` over the top of `tank_upper` onto its recessed shoulder **before attaching cargo**. It cannot pass over the full-diameter hull below that shoulder.
4. Fit the four aft fins into both sets of sockets across `aft_hull` and `tank_lower`. The relief faces outward/tangentially as shown in the native assembly. Glue after confirming both tabs are seated.
5. Fit the four canards into the lower nose sockets. Their curved roots follow the ogive with a clearance gap; only the keyed rectangular tab enters the hull.
6. Fit the separate dark nose tip onto the nose's upper peg.
7. Seat seven engine pegs in the underside of `engine_mount`. The cluster is one center bell plus six around it. Fix the mounting plate inside the bottom of `aft_hull`, with bell mouths pointing down. The plate is a glue fit; it is not a snap latch.
8. Attach the four landing legs to the angled sockets between the aft fins. All four feet should meet a level surface. The legs are static display parts, not retractable joints.
9. Use small amounts of a filament-compatible adhesive after dry assembly. A dark wash in the recessed hatches, weld seams, fasteners and hex-tile seams will bring out the modeled details.

## Validation and editing

The run manifest records evaluated mesh validity, positive volumes, disconnected-body expectations, bed fit, STL/3MF round trips, measured mating clearances and solid-intersection checks. The two native backends are compared by part bounds and volume. These are digital checks, not a physical test-print guarantee or a load-rating for the landing gear.

`native/astraeus.blend` contains editable objects and Boolean construction modifiers. `native/astraeus.hipnc` uses native profile/revolve, curve/extrude, Boolean and attribute nodes. The `.hipnc` extension reflects the locally detected Houdini Apprentice license; the toolkit's MIT license does not change SideFX's application/license restrictions.

Working geometry lives in this project, independently of GeometryForge's toolkit code. Start a revision with `geometryforge context .`, inspect `geometryforge plan .`, then run through the agent. Save native application edits before requesting a new run. Install `requirements-checks.txt` in the toolkit's Python environment to run this project's additional solid-interference checks.
