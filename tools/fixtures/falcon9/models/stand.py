def build(p,api):
    r=p['radius'];c=p['clearance']
    obj=api.cylinder('base',r+13,0,5,center=(65,0))
    ring=api.cylinder('cradle',r+4,4,12,center=(65,0))
    api.boolean(obj,ring,'UNION')
    socket=api.cylinder('rocket_socket',r+c,5,12,center=(65,0))
    api.boolean(obj,socket,'DIFFERENCE')
    api.finish(obj)
