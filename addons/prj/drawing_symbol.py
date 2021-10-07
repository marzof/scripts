#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, geometry
from prj.drawing_subject import Drawing_subject, drawing_subjects
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import get_working_scene
from prj.utils import create_line_mesh_obj, add_modifier

CAM_FRAME_COORDS = [Vector((0,0)), Vector((1,0)), Vector((1,1)), Vector((0,1))]

class Drawing_symbol(Drawing_subject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_stair_cut = self.symbol_type == 'stairs_cut'
        self.agent_obj = None
        self.parent_collection = [coll for coll in self.collections \
                if 'PARENT' in self.collections[coll]][0]

    def __repr__(self):
        return 'SYMBOL: ' + super().__repr__()

    def apply_stair_cut(self) -> None:
        """ Create a volume based on stair cut symbol and subtract it from the 
            stair elements """
        SAFETY_OFFSET = .1

        def extend_line_to_frame(camera: 'Drawing_camera', 
                obj_cam_verts: list[Vector]) -> list[Vector]:
            """ Get the intersections of symbol line with frame 
                and return their local coords """
            locations = []
            center_offset = camera.local_frame[0] ## x and y
            projected_frame_on_line = [geometry.intersect_point_line(f, 
                obj_cam_verts[0], obj_cam_verts[-1]) for f in CAM_FRAME_COORDS]
            fol = [v[0] for v in projected_frame_on_line]
            vec_dists = {(fol[0] - fol[2]).length: (fol[0], fol[2]),
                    (fol[1] - fol[3]).length: (fol[1], fol[3])}
            percent_points = vec_dists[max(vec_dists.keys())]
            for point in percent_points:
                local_x = ((camera.local_frame[1].x - camera.local_frame[2].x) \
                        * point.x) - center_offset.x
                local_y = ((camera.local_frame[3].y - camera.local_frame[2].y) \
                        * point.y) - center_offset.y
                local_z = center_offset.z + SAFETY_OFFSET
                locations.append(Vector((local_x, local_y, local_z)))
            return locations

        def get_modifiers_data(obj: bpy.types.Object, camera: 'Drawing_camera',
                obj_cam_verts: list[Vector]) -> dict[str,float]:
            """ Calculate the length of extrusions (both for screw and for 
                solidify modifier) and the side of solidify """
            obj_frame_distance = obj_cam_verts[0].z - camera.clip_start

            three_point_plane = [obj.data.vertices[0].co, 
                    obj.data.vertices[-1].co, 
                    obj.data.vertices[0].co + Vector((0,0,-1))]
            obj_plane = [obj.matrix_world @ v for v in three_point_plane]
            obj_normal = geometry.normal(obj_plane)
            ## The side to keep is the one where the origin of cut symbol is
            keep_side_distance = geometry.distance_point_to_plane(
                    self.obj.location, obj_plane[0], obj_normal)
            solidify_offset = round(-keep_side_distance/abs(keep_side_distance))
            ## The length of solidify extrusion is the maximum distance in frame
            cam_frame_diagonal = (camera.frame[0] - camera.frame[2]).length

            return {'extrude_length': obj_frame_distance,
                    'solidify_offset': solidify_offset,
                    'solidify_extrude': cam_frame_diagonal}

        def add_boolean_to_collection(obj: bpy.types.Object, 
                collection: bpy.types.Collection) -> None:
            """ Add a boolean modifier to all the objects 
                in obj collection to subtract obj """
            for subj in drawing_subjects:
                if subj.eval_obj not in list(collection.all_objects):
                    continue
                if subj.is_symbol:
                    continue
                add_modifier(subj.obj, 'prj_stair_cut_bool', 'BOOLEAN',
                        {'object': obj, 'operation': 'DIFFERENCE'})

        scene: bpy.types.Scene = self.working_scene.scene
        ## The symbol vertices in world coords
        obj_world_verts: list(Vector) = [self.matrix @ v.co \
                for v in self.obj.data.vertices]
        ## The symbol vertices in camera coords
        obj_cam_verts: list(Vector) = [world_to_camera_view(
            scene, self.drawing_camera.obj, v) for v in obj_world_verts]

        frame_intersections = extend_line_to_frame(self.drawing_camera,
                obj_cam_verts)
        obj = create_line_mesh_obj('Stair_mesh_bool', frame_intersections, 
                scene.collection)
        obj.matrix_world = self.drawing_camera.matrix
        mod_data = get_modifiers_data(obj, self.drawing_camera, obj_cam_verts)
        screw_mod = add_modifier(obj, 'Screw_extrude', 'SCREW', 
                {'angle': 0, 'steps': 1, 
                    'screw_offset': - mod_data['extrude_length'] - SAFETY_OFFSET, 
                    'use_smooth_shade': False})
        solid_mod = add_modifier(obj, 'Solidify_extrude', 'SOLIDIFY', 
                {'thickness': mod_data['solidify_extrude'], 
                    'offset': mod_data['solidify_offset']})
        add_boolean_to_collection(obj, self.parent_collection)
        obj.hide_viewport = True
