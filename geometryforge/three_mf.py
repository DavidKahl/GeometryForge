"""Write millimeter 3MF assemblies with material metadata and shared mesh bodies."""

from __future__ import annotations

import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import quoteattr


@dataclass(frozen=True)
class MeshSolid:
    """Backend-neutral mesh adapter; coordinates and volume are in millimeters."""
    vertices: object
    triangles: object
    volume: float


def mesh_body(name, vertices, triangles, volume, filament=1):
    return Body(name, MeshSolid(vertices, triangles, volume), filament)

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BBS_NS = "http://schemas.bambulab.com/package/2021"

IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model"/>
</Relationships>
"""


@dataclass(frozen=True)
class Body:
    """One filament's worth of a part.

    `filament` is 1-based and is what the slicer calls an extruder - filament 1
    is the main colour, 2 the accent. It is deliberately a plain number rather
    than a colour: the file says which SLOT, and which spool is in that slot is
    the printer's business, not the model's.
    """

    name: str
    solid: object
    filament: int = 1


def _mesh_xml(solid, tolerance: float, angular_tolerance: float) -> tuple[str, int, int]:
    if isinstance(solid, MeshSolid):
        vertices, triangles = solid.vertices, solid.triangles
        coordinates = vertices
    else:
        vertices, triangles = solid.tessellate(tolerance, angular_tolerance)
        coordinates = [(v.X, v.Y, v.Z) for v in vertices]
    parts = ["<mesh><vertices>"]
    parts += [
        f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in coordinates
    ]
    parts.append("</vertices><triangles>")
    parts += [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in triangles]
    parts.append("</triangles></mesh>")
    return "".join(parts), len(vertices), len(triangles)


def _model_xml(objects: dict[str, Sequence[Body]], tolerance: float,
               angular_tolerance: float
               ) -> tuple[str, dict[str, tuple[int, list[int]]], int]:
    """The 3MF itself, plus the ids it handed out: {name: (container, parts)}.

    The ids are RETURNED rather than recomputed by the config writer. They were
    recomputed once - the container is the id after the last body - and that is
    an arithmetic relationship between two files that both have to be right,
    which is the one failure this format has that a mesh error would not make
    obvious: it slices, it just slices in the wrong colours. `verify_mm` checks
    the two agree; not giving them the chance to disagree is better.
    """
    resources: list[str] = []
    items: list[str] = []
    ids_out: dict[str, tuple[int, list[int]]] = {}
    triangles = 0
    next_id = 1

    for obj_name, bodies in objects.items():
        ids: list[int] = []
        for body in bodies:
            if not isinstance(body.filament, int) or body.filament < 1:
                raise ValueError("filament slots must be positive integers")
            mesh, _, n_tri = _mesh_xml(body.solid, tolerance, angular_tolerance)
            triangles += n_tri
            resources.append(
                f'<object id="{next_id}" type="model" p:UUID="{uuid.uuid4()}"'
                f" partnumber={quoteattr(body.name)}>{mesh}</object>"
            )
            ids.append(next_id)
            next_id += 1

        container = next_id
        next_id += 1
        components = "".join(
            f'<component objectid="{i}" transform="{IDENTITY}"/>' for i in ids
        )
        resources.append(
            f'<object id="{container}" type="model" p:UUID="{uuid.uuid4()}"'
            f" partnumber={quoteattr(obj_name)}>"
            f"<components>{components}</components></object>"
        )
        items.append(
            f'<item objectid="{container}" transform="{IDENTITY}" '
            f'printable="1" p:UUID="{uuid.uuid4()}"/>'
        )
        ids_out[obj_name] = (container, ids)

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}" '
        f'xmlns:p="{PROD_NS}" xmlns:BambuStudio="{BBS_NS}">'
        '<metadata name="Application">GeometryForge</metadata>'
        "<resources>" + "".join(resources) + "</resources>"
        f'<build p:UUID="{uuid.uuid4()}">' + "".join(items) + "</build>"
        "</model>"
    )
    return model, ids_out, triangles


def _config_xml(objects: dict[str, Sequence[Body]],
                ids: dict[str, tuple[int, list[int]]]) -> str:
    """Which filament each part prints in, keyed by the ids just written.

    The object carries the first body's filament as its default. That is not
    decoration: a slicer that drops a per-part setting falls back to the
    object's, and falling back to the MAIN colour leaves a part that is merely
    unaccented rather than one printed entirely in the accent.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for obj_name, bodies in objects.items():
        container, part_ids = ids[obj_name]
        lines.append(f' <object id="{container}">')
        lines.append(f'  <metadata key="name" value={quoteattr(obj_name)}/>')
        lines.append(f'  <metadata key="extruder" value="{bodies[0].filament}"/>')
        for body, pid in zip(bodies, part_ids):
            lines.append(f'  <part id="{pid}" subtype="normal_part">')
            lines.append(f'   <metadata key="name" value={quoteattr(body.name)}/>')
            lines.append('   <metadata key="matrix" '
                         'value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>')
            lines.append(f'   <metadata key="extruder" value="{body.filament}"/>')
            lines.append("  </part>")
        lines.append(" </object>")
    lines.append("</config>")
    return "\n".join(lines) + "\n"


def write(objects: dict[str, Sequence[Body]], path: Path,
          tolerance: float = 0.01, angular_tolerance: float = 0.1) -> str:
    """Write one 3MF. `objects` maps a part name to the bodies it is made of.

    A one-body entry is legal and useful - it is a single-filament part that
    still wants to travel with its siblings - but the file is meant for parts
    whose bodies differ in filament.
    """
    if not objects:
        raise ValueError("nothing to write")
    for name, bodies in objects.items():
        if not bodies:
            raise ValueError(f"{name!r} has no bodies")
        for body in bodies:
            if body.solid is None or body.solid.volume <= 0.0:
                raise ValueError(
                    f"{name}/{body.name} is empty - an accent that came out with "
                    f"no volume means the split region missed the part, which "
                    f"exports and slices perfectly as a part with no accent"
                )

    model, ids, triangles = _model_xml(objects, tolerance, angular_tolerance)
    config = _config_xml(objects, ids)

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/model_settings.config", config)

    n_bodies = sum(len(b) for b in objects.values())
    return (
        f"{len(objects)} object(s), {n_bodies} part(s), "
        f"{triangles} triangles, {path.stat().st_size / 1e6:.1f} MB"
    )


def filaments(objects: dict[str, Sequence[Body]]) -> str:
    """What the file asks the printer for, said out loud."""
    used = sorted({b.filament for bodies in objects.values() for b in bodies})
    return f"filament {' and '.join(str(f) for f in used)}"
