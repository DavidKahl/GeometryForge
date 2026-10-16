# Clean reference sets

A clean reference set is six orthographic views of one object (front, back, left, right, top, bottom) under neutral studio light on a plain background. It is the first step of every reference-driven project, before coverage review, calibration or geometry.

Concept art, mood renders and perspective shots stay in the project as *identity* references. They decide what the object is. Lighting, perspective, reflections and environment hide plates, seams, vents and modules, so geometry is never traced from them.

## Why it matters

A model can only be as detailed as what the references show. A gated build that followed generated mood shots produced the right form and clean surfaces but lost almost all detail. The panel lines, plate layers and belly modules were hidden in glare and shadow, and no check noticed. Six clean views show every surface directly and make orthographic calibration exact.

## Producing the set

Most users generate the set with a hosted image model (for example Nano Banana or GPT-Image) from their concept image. Give them one prompt per view, each with the concept image attached:

```text
Orthographic <VIEW> view of exactly this vehicle/object from the attached image.
Same design, proportions, colours, markings and every detail: panel lines, plates,
bolts, vents, lights, mechanical parts. True orthographic projection, no perspective,
camera centred on the object and looking straight along the <AXIS> axis.
Neutral even studio lighting, no dramatic shadows or reflections, no glow bloom.
Plain uniform light grey (or transparent) background, no floor, no environment,
no motion, no text. The whole object fully in frame with a margin on every side.
```

Fill in the view and axis:

| `<VIEW>` | `<AXIS>` | Screen orientation |
|---|---|---|
| front | longitudinal, from the front | object's left on the image right |
| back | longitudinal, from behind | object's left on the image left |
| left | lateral, from the object's left | nose on the image left |
| right | lateral, from the object's right | nose on the image right |
| top | vertical, from above | nose at the top of the image |
| bottom | vertical, from below | nose at the top of the image |

Generate all six from the same concept in one session where the tool allows it. Ask for square images at the same resolution.

## Checklist before accepting the set

- [ ] Same design in every view: the same parts, counts and markings. Left and right may mirror each other.
- [ ] No perspective: parallel edges stay parallel, and no faces show that the view direction should hide.
- [ ] Neutral light: no strong shadows, specular blowouts or bloom hiding detail.
- [ ] A plain or transparent background that separates cleanly from the object, with nothing cropped at the edges.
- [ ] Proportions agree. Run `geometryforge references check` (below).

## Toolkit steps

1. Copy the views to `references/clean/` and map them in `references/clean_set.json`:
   ```json
   {"version": 1, "views": {"front": "references/clean/front.png", "back": "references/clean/back.png",
     "left": "references/clean/left.png", "right": "references/clean/right.png",
     "top": "references/clean/top.png", "bottom": "references/clean/bottom.png"}}
   ```
2. `geometryforge references masks <project>` writes `references/mask_<view>.png` from alpha, or from the border colour of an opaque image. Inspect them.
3. `geometryforge references check <project>` measures each silhouette's extent and compares:
   - length/height between left and right;
   - width/height between front and back;
   - length/width between top and bottom;
   - side length/height against top × front.

   It writes `references/clean_check.json`. Disagreement above `gf_thresholds.references.view_disagreement_pct` (default 3%) marks the set `candidate`.
4. Calibrate every view as an orthographic camera. In `references/correspondences.json` give each camera `"projection": "orthographic"`, a `"view"` and three or more datums. `geometryforge calibrate` fits scale, offset and roll per view. Each view then gets its own silhouette score, overlay and review camera (`camera.ref`).

## When views disagree

Generated views are produced independently and drift: a part drawn larger in one view, a pad that sticks out in the bottom view but not the top. Do not average them silently. Either:
- regenerate the outlier view with a sharper prompt, naming the part that disagrees; or
- record an authority rule with the user, for example "left/right govern length and height, top governs width; front and back are used for feature placement only". Record it in `decisions.reference_review.clean_set` with the measured disagreements and the user's acceptance.

Measured silhouettes come from generated images: they are interpretations, not measurements of a real object. State that whenever you quote them.
