bl_info = {
    "name": "Prj",
    "blender": (2, 90, 0),
    "category": "3D View",
}

import bpy
import subprocess, shlex
import os, pathlib

RENDERABLES = ['MESH', 'CURVE', 'EMPTY']
ADDONS_PATH = str(pathlib.Path(__file__).parent.absolute())
MAIN_PATH = 'main.py'
prj_cmd = lambda flags, assets: [bpy.app.binary_path, "--background", bpy.data.filepath,
        "--python", ADDONS_PATH + "/" + MAIN_PATH, "--", flags, assets]

def get_render_assets():
    ''' Get cameras and object based on args or selection '''
    selection = bpy.context.selected_objects
    cams = [obj for obj in selection if obj.type == 'CAMERA']
    objs = [obj for obj in selection if obj.type in RENDERABLES]
    return {'cams': cams, 'objs': objs}


class Prj(bpy.types.Operator):
    """Set view to camera to export svg  from grease pencil"""
    bl_idname = "prj.modal_operator"
    bl_label = "Set 3d view as selected camera and launch prj"
    bl_options = {'REGISTER', 'UNDO'}

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

    def execute(self, context):
        bpy.ops.wm.save_mainfile()
        subprocess.run(prj_cmd(self.key, str(self.render_assets_names)))
        self.reset_scene(context)


    def modal(self, context, event):
        context.area.header_text_set("Type Enter to create drawing, " + \
                "H for hiddden, B for back, ESC for exit")
        if event.type in {'RET', 'NUMPAD_ENTER'} or event.type == 'LEFTMOUSE':
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
        self.render_assets = get_render_assets()
        self.render_assets_names = {}
        for tp in self.render_assets:
            self.render_assets_names[tp] = [i.name 
                    for i in self.render_assets[tp]]

        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}
        
        if len(self.render_assets['cams']) == 0:
            self.report({'WARNING'}, "At least one camera has to be selectd")
            return {'CANCELLED'}

        v3d = context.space_data
        rv3d = v3d.region_3d
        
        self._initial_perspective = rv3d.view_perspective
        self._initial_matrix = rv3d.view_matrix.copy()
        self._initial_rotation = rv3d.view_rotation.copy()
        self._initial_location = rv3d.view_location.copy()
        self._initial_distance = rv3d.view_distance
        self._initial_scene_camera = bpy.context.scene.camera
        self.camera = get_render_assets()['cams'][0]
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
