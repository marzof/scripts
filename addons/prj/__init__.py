bl_info = {
    "name": "Prj",
    "blender": (2, 90, 0),
    "category": "3D View",
}

import bpy
import os, pathlib
from prj.drawing_context import Drawing_context, is_renderables
from prj.drawing_maker import Drawing_maker
from prj.main import draw_subjects, rewrite_svgs, get_svg_composition

# TODO add type hints
class Prj(bpy.types.Operator):
    """Set view to camera to export svg from grease pencil"""
    bl_idname = "prj.modal_operator"
    bl_label = "Set 3d view as selected camera and launch prj"
    bl_options = {'REGISTER', 'UNDO'}

    def get_objects(self, selection):
        ''' Get objects based on selection '''
        objs = [obj.name.replace(';', '_') for obj in selection 
                if is_renderables(obj)]
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
        bpy.ops.view3d.view_camera()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def execute(self, context):
        ## TODO fix composition filepath (now it's on application directory)
        ##      and add a debug funtionality to allow
        ##      testing timing for every single isolated object in frame
        bpy.ops.wm.save_mainfile()
        objs = ';'.join(self.get_objects(self.selection) + [self.camera.name])
        args = self.key.split() + [objs]
        draw_context = Drawing_context(args, context)
        draw_maker = Drawing_maker(draw_context)
        draw_subjects(draw_context, draw_maker)
        rewrite_svgs(draw_context)
        get_svg_composition(draw_context)
        self.reset_scene(context)

    def modal(self, context, event):
        context.area.header_text_set("Type Enter to create drawing, " + \
                "H for hiddden, B for back, ESC for exit")
        if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'}:
            self.key = '-cp -a -r 80cm'
            #self.key = '-cp'
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

        self._initial_scene_camera = bpy.context.scene.camera
        bpy.context.scene.camera = self.camera
        bpy.ops.view3d.view_camera()

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(Prj)

def unregister():
    bpy.utils.unregister_class(Prj)

if __name__ == "__main__":
    register()
