def build(p,api):
    # Four separately printable display legs, laid out beside the assembly.
    for i in range(4):
        obj=api.box(f'leg_{i}',(4,6,p['leg_length']),(45+i*8,-40,p['leg_length']/2))
        foot=api.box(f'foot_{i}',(8,10,3),(45+i*8,-40,1.5))
        api.boolean(obj,foot,'UNION')
        api.finish(obj,bodies=4)
