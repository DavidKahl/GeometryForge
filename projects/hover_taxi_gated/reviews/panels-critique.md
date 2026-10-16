# Gate 2 panels: blind critique

Written from the blind sheets of review 20261016T115408Z-b9d22a08 (identical geometry re-rendered as 20261016T122223Z-f2bcd992 for the final safe point), before reading report.json. Earlier rounds: 20261016T085244Z-19d395a5 (oval openings) and 20261016T094742Z-8d08f8fc.

## Iterations

1. **First build: all openings came out as ovals.** Side windows read as portholes and headlamps as round holes, the reference's rectangular glass and lamp clusters lost. Openings sliced from one or two master faces have four rim corners, and subdivision turns that into an ellipse. Support cuts beside opening corners (`tighten_opening`) fixed it; windows use 160 mm, because tighter cuts folded the 4 mm shell.
2. **Seams opened toward their ends** because sparse panel corners subdivided round. Support cuts beside outer panel corners fixed it (`tighten_panel_corners`). A vertex crease was tried first and flipped the shell.
3. **Panels drifted off sharp master edges** because sliced panels had lost the master's creases; panels now keep them.

## Current state

- **Surface continuity:** zebra stripes run continuously across doors, fenders, hood, roof and greenhouse. Panel gaps are fine hairlines; the panels read as one surface split into parts.
- **Openings:** the large side windows read as rectangular glazing apertures between pillars. The headlamps and tail lights are rectangular slots, and the windshield is a framed trapezoid.
- **Still rounded:**
  - The rear-quarter window (220 mm wide; every corner cut folded the shell).
  - The nacelle socket, round by choice.
- **Skirt:** the chrome skirt sits flush with the painted body. In the reference it is a thick band stepping out. The user decided to keep it flush for now; changing it needs the master.
- **Nacelles:** chamfered armour with recessed exhausts and hubs. They still float behind the body until Gate 3 binds them to the sockets.
- **Socket (superseded):** its rear edge sat where the rear quarter wraps strongly toward the back, so the return met an already inclined surface. A 45 mm design fillet measured 2.24 mm there; the user accepted 2 mm for the socket. The Gate 1 reopen moved the sockets, and that limit no longer applies.

## Re-acceptance after the Gate 1 reopen (review 20261016T133823Z-ecc5ec9d)

Written from the blind sheets, before reading report.json.

- **Sockets moved:** the nacelle sockets now open in the rear face of the body (`Rear panel`), facing the nacelle hubs instead of the sides of the rear quarter. In the close rear view they read as rounded painted returns behind the hubs. Their returns measure 21.6 mm against the default 5 mm minimum, so the 2 mm socket limit was dropped.
- **Proud vertices fixed in the toolkit:** the first rebuild left 90 vertices up to 0.64 mm proud at the sockets' lower outer corners. They were subdivided vertices between the locked rim and the first pocket ring, only partly shrinkwrapped. Every pocket now carries a `Pocket guard` Shrinkwrap (INSIDE) after the master lock (toolkit commit ca31b3a); worst protrusion is 0.011 mm.
- **Everything else unchanged:** seams 1.8-4.1 mm (skirt 5.4-7.0 mm), steps at most 0.009 mm, coverage 8.84 mm body and 7.60 mm nacelles. The other pockets pass under the thresholds accepted for Gate 2. The nacelles still float behind the body until Gate 3 binds them to the sockets.
