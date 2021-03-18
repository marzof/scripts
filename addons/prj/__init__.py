bl_info = {
    "name": "Prj",
    "blender": (2, 90, 0),
    "category": "3D View",
}

import bpy
import subprocess, shlex
import os, pathlib

ADDONS_PATH = str(pathlib.Path(__file__).parent.absolute())
MAIN_PATH = 'main.py'
GREASE_PENCIL_PREFIX = 'prj_'
SVG_GROUP_PREFIX = 'blender_object_' + GREASE_PENCIL_PREFIX
prj_cmd = lambda flags, objects: [bpy.app.binary_path, "--background", bpy.data.filepath,
        "--python", ADDONS_PATH + "/" + MAIN_PATH, "--", flags, objects]
renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]

class Prj(bpy.types.Operator):
    """Set view to camera to export svg  from grease pencil"""
    bl_idname = "prj.modal_operator"
    bl_label = "Set 3d view as selected camera and launch prj"
    bl_options = {'REGISTER', 'UNDO'}

    def get_objects(self, selection):
        ''' Get objects based on selection '''
        objs = [obj.name.replace(';', '_') for obj in selection 
                if renderables(obj)]
        return objs

    def get_camera(self, selection):
        ''' Get selected camera '''
        cams = [obj for obj in selection if obj.type == 'CAMERA']
        if len(cams) != 1:
            self.report({'WARNING'}, "Just one camera has to be selected")
            return None
        return cams[0]

    def reset_scene(self, context):
        v3d = context.space_data
        rv3d = v3d.region_3d
        bpy.context.scene.camera = self._initial_scene_camera
        self.camera.rotation_mode = self._initial_cam_rotation_mode
        rv3d.view_perspective = self._initial_perspective
        rv3d.view_rotation = self._initial_rotation
        rv3d.view_location = self._initial_location
        rv3d.view_distance = self._initial_distance
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def execute(self, context):
        bpy.ops.wm.save_mainfile()
        objs = ';'.join(self.get_objects(self.selection) + [self.camera.name])
        subprocess.run(prj_cmd(self.key, objs))
        self.reset_scene(context)


    def modal(self, context, event):
        context.area.header_text_set("Type Enter to create drawing, " + \
                "H for hiddden, B for back, ESC for exit")
        if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'}:
            self.key = '-cp'
            self.execute(context)
            return {'FINISHED'}
        elif event.type == 'H':
            self.key = '-h'
            self.execute(context)
            return {'FINISHED'}
        elif event.type == 'B':
            self.key = '-b'
            self.execute(context)
            return {'FINISHED'}
        elif event.type == 'ESC':
            self.reset_scene(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):

        self.selection = bpy.context.selected_objects
        self.objects = self.get_objects(self.selection)
        self.camera = self.get_camera(self.selection)
        if not self.camera:
            return {'CANCELLED'}
        v3d = context.space_data
        rv3d = v3d.region_3d
        
        self._initial_perspective = rv3d.view_perspective
        self._initial_matrix = rv3d.view_matrix.copy()
        self._initial_rotation = rv3d.view_rotation.copy()
        self._initial_location = rv3d.view_location.copy()
        self._initial_distance = rv3d.view_distance
        self._initial_scene_camera = bpy.context.scene.camera
        self._initial_cam_rotation_mode = self.camera.rotation_mode

        bpy.context.scene.camera = self.camera
        self.camera.rotation_mode = 'QUATERNION'

        rv3d.view_perspective = self.camera.data.type
        rv3d.view_rotation = self.camera.rotation_quaternion
        rv3d.view_location = self.camera.location
        rv3d.view_distance = self.camera.data.ortho_scale

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(Prj)


def unregister():
    bpy.utils.unregister_class(Prj)


if __name__ == "__main__":
    register()
