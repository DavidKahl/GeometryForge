def build(p, api):
    count, w, d, h, wall, floor = [p[k] for k in ('count','width','depth','height','wall','floor')]
    if type(count) is not int or not 1 <= count <= 12 or min(wall,floor)<1.2 or h<=floor or d<=2*wall or w<=(count+1)*wall:
        raise ValueError('Dimensions leave no printable cavity or walls')
    obj=api.box('body',(w,d,h),(0,0,h/2))
    cavity=(w-(count+1)*wall)/count
    for i in range(count):
        x=-w/2+wall+cavity/2+i*(cavity+wall)
        tool=api.box(f'cavity_{i+1}',(cavity,d-2*wall,h),(x,0,floor+h/2))
        api.boolean(obj,tool,'DIFFERENCE')
    api.finish(obj)
