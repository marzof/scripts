#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]

get_xml_elements = lambda container, element: list(
        container.iterdescendants(element))

get_pl_points = lambda polylines: [tuple_points(pt.attrib['points']) 
        for pt in polylines]

point_from_camera = lambda v, cam: world_to_camera_view(bpy.context.scene, 
        cam, v)

## To develop 
def clip_cut(prj_layer, cut_layer):
    #clipper = Clipper()
    prj_points, cut_points = [], []

    prj_entities = list(prj_layer.entities.values())[0][0].entities
    for entity in prj_entities:
        if entity == 'path':
            for path in prj_entities[entity]:
                prj_points.append(path.points)

    cut_entities = list(cut_layer.entities.values())[0][0].entities
    for entity in cut_entities:
        if entity == 'path':
            for path in cut_entities[entity]:
                cut_points.append(path.points)

    #new_prj_points = clipper.clip(cut_points, prj_points)

def get_rect_dimensions(rect) -> tuple[tuple[float], list[float]]: 
    """ Get position and dimensions of polyline rect in svg """
    min_val, max_val = math.inf, 0.0
    polylines = get_xml_elements(rect.root, POLYLINE_TAG)
    points = get_pl_points(polylines)
    point_coords = [co for p in points for co in p]
    for co in point_coords:
        if sum(co) < min_val:
            min_val, origin = sum(co), co
        if sum(co) > max_val:
            max_val, extension = sum(co), co
    size = numpy.subtract(extension, origin)
    return origin, size 


def localize_obj(container: bpy.types.Object, 
        inner_obj: bpy.types.Object) -> bpy.types.Object:
    """ Make inner_obj located as if it was local based on container matrix """
    cnt_matrix = container.matrix_world.copy()
    cnt_instance_offset = container.instance_collection.instance_offset
    cnt_translated = cnt_matrix @ Matrix.Translation(-cnt_instance_offset)
    inner_obj.matrix_world = cnt_translated @ inner_obj.matrix_world
    return inner_obj

def put_in_dict(dic: dict, key: list, value) -> None:
    """ Check if key is in dic and append value to the list dic[key] """
    if key not in dic:
        dic[key] = [value]
    else:
        dic[key].append(value)

def mesh_by_verts(obj_name: str, verts: list[Vector]) -> bpy.types.Object:
    """ Create a mesh object from verts """
    mesh = bpy.data.meshes.new(obj_name)
    obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bm.from_object(obj, bpy.context.view_layer.depsgraph)
    for v in verts:
        bm.verts.new(v)

    bmesh.ops.contextual_create(bm, geom=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    return obj

def in_frame(cam: bpy.types.Object, 
        obj: bpy.types.Object) -> dict[str, bool]:
    """ Get visibility relation between cam and obj """

    BOUNDING_BOX_EDGES = ((0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (2, 3), 
                        (2, 6), (3, 7), (4, 5), (4, 7), (5, 6), (6, 7))
    BOUNDING_BOX_FACES = ((0, 1, 2, 3), (2, 3, 7, 6), (6, 7, 4, 5),
                       (4, 5, 1, 0), (0, 4, 7, 3), (1, 5, 6, 2)) 
    FRAME_EDGES = (Vector((0,0)), Vector((1,0)), Vector((1,1)), Vector((0,1)))

    box = [(obj.matrix_world @ Vector(v)) for v in obj.bound_box]
    #print('ref_offset', ref_offset)
    #print('box', box)

    frontal = False
    behind = False
    framed = False
    
    bound_box_verts_from_cam = []
    ## If a vertex of bounding box is in camera_view then object is in
    for v in box:
        x, y, z = point_from_camera(v, cam)
        bound_box_verts_from_cam.append((x, y, z))

        if z >= cam.data.clip_start or z == 0.0:
            frontal = True
        else:
            behind = True
        if 1 >= x >= 0 and 1 >= y >= 0:
            #print(obj.name, "is FRAMED! (in vertex", v, ")")
            framed = True
    if framed:
        return {'framed': framed, 'frontal': frontal, 'behind': behind}
    else:
        ## Check if obect is bigger than frame
        for face in BOUNDING_BOX_FACES:
            face_verts = [bound_box_verts_from_cam[v] for v in face]
            if __point_in_quad(Vector((.5,.5,.0)), face_verts):
                framed = True
                return {'framed': framed, 'frontal': frontal, 'behind': behind}

        ## If an edge intersects camera frame then obj is in
        for e in BOUNDING_BOX_EDGES:
            print(box[e[0]][:2])
            box_edge = [Vector(point_from_camera(box[e[0]][:2], cam)),
                Vector(point_from_camera(box[e[1]][:2], cam))]
            for i in range(4):
                if __lines_intersect(box_edge[0], box_edge[1], 
                        FRAME_EDGES[i], FRAME_EDGES[(i+1)%4]):
                    framed = True
                    return {'framed': framed, 'frontal': frontal, 'behind': behind}

    #print(obj.name, "is NOT FRAMED!")
    frontal = False
    behind = False
    return {'framed': framed, 'frontal': frontal, 'behind': behind}

def __point_in_quad(point: Vector, quad_vert: list[Vector]) -> bool:
    """ Check if point is inside quad (2d only) """
    intersect_point = geometry.intersect_point_quad_2d(point,
            quad_vert[0], quad_vert[1], quad_vert[2], quad_vert[3])
    if not intersect_point:
        return False
    return True

def __lines_intersect(a_0: Vector, a_1: Vector, b_0: Vector, b_1: Vector) -> bool:
    """ Check if lines a and b intersects (2d only) """
    intersect_point = geometry.intersect_line_line_2d(a_0, a_1, b_0, b_1)
    if not intersect_point:
        return False
    return True


def move_to_last(item, l: list) -> list:
    ''' Move item to the last element of l and return the edited list '''
    if item not in l:
        return l
    to_last = l.pop(l.index(item))
    l.append(to_last)
    return l

def apply_mod(obj, mod_type: list[str] = []) -> None:
    ''' Apply modifier of mod_type or all modifiers '''

    make_active(obj)
    bpy.ops.object.mode_set(mode = 'OBJECT')

    ## Remove shape keys
    ## TO_DO apply the active shape key after the other to keep the shape
    if obj.data.shape_keys:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shape_key_remove(all=True)
        print('remove shape_key', obj.data.shape_keys)

    mods = obj.modifiers
    if mod_type:
        mods = [mod for mod in obj.modifiers if mod.type in mod_type 
                and mod.show_render]
    for mod in mods:
        bpy.ops.object.modifier_apply(modifier=mod.name)

def make_local_collection(instancer: bpy.types.Object) -> bpy.types.Collection:
    ''' Convert linked collection in instancer (empty) to local collection '''
    linked_coll = instancer.instance_collection

    ## -> get_data_from_collection(linked_coll)
    coll_path = linked_coll.library.filepath
    linked_coll_name = linked_coll.name
    instancer_matrix = instancer.matrix_world.copy()
    coll_instance_offset = linked_coll.instance_offset
    coll_translated = instancer_matrix @ Matrix.Translation(-coll_instance_offset)
    
    ## -> remove_obj_and_mesh()
    linked_objs = linked_coll.all_objects
    linked_meshes = [obj.data for obj in linked_coll.all_objects]
    for obj in linked_objs:
        bpy.data.objects.remove(obj)
    for mesh in linked_meshes:
        bpy.data.meshes.remove(mesh)
    bpy.data.collections.remove(linked_coll, do_unlink=True)

    with bpy.data.libraries.load(coll_path, relative=False) as (
            data_from, data_to):
        data_to.collections.append(linked_coll_name)
    new_collection = bpy.data.collections[linked_coll_name]
    new_collection.name = instancer.name
    scene = bpy.context.scene
    scene.collection.children.link(new_collection)
    for obj in new_collection.all_objects:
        obj.matrix_world = coll_translated @ obj.matrix_world
    return new_collection

def cut_object(obj: bpy.types.Object, 
        cut_plane: dict[str,Vector]) -> bpy.types.Object:
    ''' Duplicate obj, bisect it by cut_plane and return the new cut object '''
    make_active(obj)
    bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
    cut_obj = bpy.context.object
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
            
    bpy.ops.mesh.bisect(plane_co=cut_plane['location'], 
            plane_no=cut_plane['direction'], use_fill=True, clear_inner=True, 
            clear_outer=True)

    bpy.ops.object.mode_set(mode = 'OBJECT')
    return cut_obj

