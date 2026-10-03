"""Project-local native profiles, extrusions and surface detailing; never mesh imports."""
import math
from math import sin,cos,pi

class Shapes:
    def __init__(self,api,p):
        self.api=api;self.p=p;self.blender=api.__class__.__name__=='Blender'
    def begin(self,part):
        print('Astraeus: building '+part,flush=True)
        self.api.begin(part)
    def lathe(self,name,profile,closed=True,center=(0,0),segments=192):
        profile=[point for i,point in enumerate(profile) if i==0 or point!=profile[i-1]]
        if self.blender:
            import bpy
            verts=[(center[0]+r*cos(i*2*pi/segments),center[1]+r*sin(i*2*pi/segments),z) for r,z in profile for i in range(segments)]
            faces=[];rows=len(profile)
            for j in range(rows if closed else rows-1):
                k=(j+1)%rows
                for i in range(segments):
                    n=(i+1)%segments
                    faces.append((j*segments+i,j*segments+n,k*segments+n,k*segments+i))
            if not closed:
                faces.extend([tuple(reversed(range(segments))),tuple((rows-1)*segments+i for i in range(segments))])
            mesh=bpy.data.meshes.new(name+'_profile_mesh');mesh.from_pydata(verts,[],faces);mesh.update()
            obj=bpy.data.objects.new(self.api.part+'_'+name,mesh);bpy.data.collections['Construction'].objects.link(obj)
            self.api.mark(obj);obj['profile_radius_height_mm']=[v for pair in profile for v in pair]
            obj['profile_segments']=segments
            obj.hide_render=True;obj.hide_set(True)
            return obj
        from geometryforge import houdini_scene as h
        geo=h.new_geo(self.api.part+'_'+name)
        curve=geo.createNode('curve','editable_radius_height_profile',exact_type_name=True)
        curve.setParms({'type':0,'close':int(closed),'coords':' '.join(f'{r},0,{z}' for r,z in profile)})
        rev=geo.createNode('revolve','revolved_shell')
        rev.setInput(0,curve);rev.setParms({'dirx':0,'diry':0,'dirz':1,'divs':segments,'cap':int(not closed),'primtype':1})
        outward=geo.createNode('reverse','outward_profile_winding');outward.setInput(0,rev)
        obj=h.Part(name,geo,outward,'Construction');obj.location=(center[0],center[1],0)
        return self.api.mark(obj)
    def prism(self,name,points,thickness,angle=0,tangent=0):
        """Extrude a radius/Z polygon along the tangential axis, then rotate in Z."""
        a=math.radians(angle)
        def xyz(r,t,z): return (r*cos(a)-t*sin(a),r*sin(a)+t*cos(a),z)
        # XZ polygon orientation is made CCW in radius/height, whose normal is -Y.
        area=sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
        if area<0:points=list(reversed(points))
        if self.blender:
            import bpy
            n=len(points);v=[xyz(r,tangent+t,z) for t in (-thickness/2,thickness/2) for r,z in points]
            faces=[tuple(range(n)),tuple(reversed(range(n,n*2)))]
            faces += [(i,n+i,n+(i+1)%n,(i+1)%n) for i in range(n)]
            m=bpy.data.meshes.new(name);m.from_pydata(v,[],faces);m.update()
            obj=bpy.data.objects.new(self.api.part+'_'+name,m);bpy.data.collections['Construction'].objects.link(obj)
            self.api.mark(obj);obj.hide_render=True;obj.hide_set(True);return obj
        from geometryforge import houdini_scene as h
        geo=h.new_geo(self.api.part+'_'+name)
        curve=geo.createNode('curve','editable_outline',exact_type_name=True)
        # Houdini's polygon convention extrudes this order in -Y; start at +t/2.
        curve.setParms({'type':0,'close':1,'coords':' '.join(f'{r},{tangent+thickness/2},{z}' for r,z in reversed(points))})
        ext=geo.createNode('polyextrude','printable_thickness');ext.setInput(0,curve);ext.setParms({'dist':thickness,'outputback':1})
        obj=h.Part(name,geo,ext,'Construction');obj.transform.parm('rz').set(angle)
        return self.api.mark(obj)
    def radial_box(self,name,r,z,width,height,depth,angle):
        if self.blender:
            # Direct data creation avoids forcing a full assembly dependency update
            # for every decorative Boolean operand.
            return self.prism(name,[(r-depth/2,z-height/2),(r+depth/2,z-height/2),
                                    (r+depth/2,z+height/2),(r-depth/2,z+height/2)],width,angle)
        obj=self.api.box(name,(depth,width,height),(r,0,z))
        if self.blender:
            a=math.radians(angle);obj.location.x=r*cos(a);obj.location.y=r*sin(a);obj.rotation_euler.z=a
        else:
            a=math.radians(angle);obj.location=(r*cos(a),r*sin(a),z);obj.transform.parm('rz').set(angle)
        return obj
    def radial_cylinder(self,name,r,z,radius,depth,angle):
        obj=self.lathe(name,[(radius,-depth/2),(radius,depth/2)],closed=False,segments=64) if self.blender else self.api.cylinder(name,radius,-depth/2,depth)
        self.api.rotate(obj,(0,90,angle))
        a=math.radians(angle);obj.location=(r*cos(a),r*sin(a),z)
        return obj
    def union(self,obj,tool):return self.api.boolean(obj,tool,'UNION')
    def cut(self,obj,tool):return self.api.boolean(obj,tool,'DIFFERENCE')
    def finish(self,obj,color='silver',rotation=(0,0,0),bodies=1):
        self.api.finish(obj,bodies=bodies,rotation=rotation)
        colors={'silver':(.52,.59,.64),'dark':(.025,.039,.055),'engine':(.12,.16,.19),'piston':(.7,.73,.76),'accent':(.38,.25,.10)}
        rgb=colors[color]
        if self.blender:
            import bpy
            mat=bpy.data.materials.get('Astraeus_'+color) or bpy.data.materials.new('Astraeus_'+color)
            mat.diffuse_color=(*rgb,1);mat.use_nodes=True
            bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(*rgb,1)
            bsdf.inputs['Metallic'].default_value=.72 if color=='silver' else .25
            bsdf.inputs['Roughness'].default_value=.33 if color=='silver' else .52
            obj.data.materials.clear();obj.data.materials.append(mat)
        else:
            import hou
            obj.geo.setColor(hou.Color(rgb))
        return obj
    def hex_surface(self,obj,r,z0,height,cell=2.0):
        """Raised cells separated by printable recessed seams on an integral sleeve."""
        count=round(2*pi*r/(math.sqrt(3)*cell));pitch=2*pi*r/count;side=pitch/math.sqrt(3)
        def relief(x,y,z):
            if math.hypot(x,y)<r-.05 or not z0+.8<z<z0+height-.8:return 0
            u=(math.atan2(y,x)%(2*pi))*r;v=z-z0;row=math.floor(v/(1.5*side));best=-100
            for j in range(row-1,row+2):
                offset=(j%2)*pitch/2;col=round((u-offset)/pitch)
                du=abs(u-(col*pitch+offset));dv=abs(v-j*1.5*side)
                best=max(best,min(.866025403784*side-du,.866025403784*side-(.5*du+.866025403784*dv)))
            return .5*max(0,min(1,(best-.18)/.18))
        if self.blender:
            for v in obj.data.vertices:
                x,y,z=v.co;d=relief(x,y,z)
                radius=math.hypot(x,y)
                if d and radius:v.co.x*=1+d/radius;v.co.y*=1+d/radius
            obj.data.update();obj['hex_cell_side_mm']=side;return
        node=obj.geo.createNode('attribwrangle','editable_hex_thermal_tiles')
        node.setInput(0,obj.output.input(0))
        code=f'''float R={r};float Z={z0};float H={height};float pitch={pitch};float side={side};
float rad=length(set(@P.x,@P.y,0));
if(rad>R-0.05 && @P.z>Z+0.8 && @P.z<Z+H-0.8){{
float a=atan2(@P.y,@P.x);if(a<0)a+=2*M_PI;float u=a*R;float v=@P.z-Z;
int row=int(floor(v/(1.5*side)));float best=-100;
for(int j=row-1;j<=row+1;j++){{float off=((j%2+2)%2)*pitch/2;float col=floor((u-off)/pitch+0.5);float du=abs(u-col*pitch-off);float dv=abs(v-j*1.5*side);best=max(best,min(0.866025403784*side-du,0.866025403784*side-(0.5*du+0.866025403784*dv)));}}
float d=0.5*clamp((best-0.18)/0.18,0,1);@P.x*=1+d/rad;@P.y*=1+d/rad;
}}'''
        node.parm('snippet').set(code);obj.output.setInput(0,node)

def flat_rotation(angle):
    # Rx(90) @ Rz(-angle): the same local back face rests on the plate for every copy.
    a=math.radians(angle);negative=cos(a)<-1e-6
    return (-90 if negative else 90,math.degrees(math.asin(sin(a))),180 if negative else 0)
