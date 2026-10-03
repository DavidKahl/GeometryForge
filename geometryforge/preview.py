"""Small offline assembly-space previews, without a rendering dependency."""
import numpy as np
from PIL import Image, ImageDraw

def preview(objects, path):
    image = Image.new("RGB", (640,480), "#111c29")
    draw = ImageDraw.Draw(image)
    polygons = []
    for obj in objects:
        v = np.asarray(obj["vertices"])
        projection = np.column_stack((.707*(v[:,0]-v[:,1]), .408*(v[:,0]+v[:,1])-.816*v[:,2]))
        for face in obj["faces"]:
            polygons.append((float(v[face].sum()), projection[face]))
    points = np.concatenate([p for _,p in polygons])
    low, high = points.min(0), points.max(0)
    scale = min(580/max(high[0]-low[0],1), 420/max(high[1]-low[1],1))
    for depth, polygon in sorted(polygons, key=lambda x:x[0]):
        coords = (polygon-(low+high)/2)*scale+[320,240]
        draw.polygon([tuple(c) for c in coords], fill="#80cbb6", outline="#4e8b83")
    image.save(path)
