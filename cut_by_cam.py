import bpy
from mathutils import Vector

current_scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()
camera = bpy.context.object
scene = bpy.data.scenes.new(name='CUT')
cut_plane_collection = bpy.data.collections.new("CUT_PLANES")
scene.collection.children.link(cut_plane_collection)

def cut_object(obj, plane_co, plane_no, use_fill: bool = False,
        clear_inner: bool = False, clear_outer: bool = False):
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bisect(plane_co=plane_co, plane_no=plane_no,
        use_fill=use_fill, clear_inner=clear_inner, clear_outer=clear_outer)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = None
    obj.select_set(False)  

def get_cam_data(cam):
    cam_direction = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    cam_local_frame = [v * Vector((1,1,cam.data.clip_start)) 
                for v in cam.data.view_frame(scene=current_scene)]
    cut_local_location = cam_local_frame[2]
    cut_location = cam.matrix_world @ cut_local_location
    return cut_location, cam_direction

def get_obj_from_obj(ref_obj, obj_name: str):
    mesh = bpy.data.meshes.new_from_object(ref_obj)
    matrix_w=ref_obj.matrix_world.copy().freeze()
    matrix_l=ref_obj.matrix_local.copy().freeze()
    obj = bpy.data.objects.new(name=obj_name, object_data=mesh)
    obj.matrix_local = matrix_l
    obj.matrix_world = matrix_w
    return obj

plane_co, plane_no = get_cam_data(camera)

for obj_inst in depsgraph.object_instances:

    try:
        check = obj_inst.object.type
    except:
        print('ATTRIBUTE ERROR', obj_inst.object)
        continue
    if obj_inst.object.type == 'CAMERA':
        continue
    if obj_inst.object.type == 'EMPTY':
        continue
    if obj_inst.object.type == 'ARMATURE':
        continue
    if obj_inst.object.type != 'MESH':
        continue
    print('Process', obj_inst.object.name)

    cut_obj = get_obj_from_obj(obj_inst.object, obj_inst.object.name)
    current_scene.collection.objects.link(cut_obj)
    cut_object(cut_obj, plane_co, plane_no, clear_inner = True)
    scene.collection.objects.link(cut_obj)
    current_scene.collection.objects.unlink(cut_obj)
    
    
    cut_plane_obj = get_obj_from_obj(obj_inst.object,
                        obj_inst.object.name + '_cut_plane')
    current_scene.collection.objects.link(cut_plane_obj)
    cut_object(cut_plane_obj, plane_co, plane_no, use_fill = True,
                        clear_inner = True, clear_outer = True)
    cut_plane_collection.objects.link(cut_plane_obj)
    current_scene.collection.objects.unlink(cut_plane_obj)


    print('done')
print('completed')
