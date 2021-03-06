import bpy
import mathutils
from mathutils import Vector
from mathutils import Quaternion
import time
import svgutils



obj_names = ['Cube', 'Sphere', 'Torus', 'Wall_cut']
objs = [bpy.data.objects[obj] for obj in obj_names]
render_path = bpy.context.scene.render.filepath
lineart = bpy.data.objects['Line_Art']
camera = bpy.context.object
camera.rotation_mode = 'QUATERNION'
RENDER_ROTATION = .000001

# scale factor: 46.875

def set_view():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    space = area.spaces[0]
                    context_override = bpy.context.copy()
                    context_override['area'] = area
                    context_override['region'] = region
                    context_override['space_data'] = space
                    r3d = space.region_3d
                    r3d.view_perspective = "ORTHO"
                    r3d.view_rotation = camera.rotation_quaternion
                    r3d.view_location = camera.location
                    r3d.view_distance = camera.data.ortho_scale
                    break
            break
    bpy.context.scene.camera = camera
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def make_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    

def main():
    set_view()
    make_active(lineart)
    for obj in objs:
        ## Rotate object to avoid rendering glitches
        actual_obj_rotation = obj.rotation_euler.copy()
        for i, angle in enumerate(obj.rotation_euler):
            obj.rotation_euler[i] = angle + RENDER_ROTATION
        ## Link object to rendering collection, export svg and unlink it
        bpy.data.collections['render'].objects.link(obj)
        bpy.ops.wm.gpencil_export_svg(filepath=render_path + obj.name + '.svg',
            selected_object_type='VISIBLE')
        bpy.data.collections['render'].objects.unlink(obj)
        ## Restore object previous rotation
        obj.rotation_euler = actual_obj_rotation
        
        #svg = svgutils.transform.fromfile(render_path + obj.name + '.svg')
        #originalSVG = svgutils.compose.SVG(render_path + obj.name + '.svg')
        #print(svg)
        #svg.scale(6.450377448)
        
main()