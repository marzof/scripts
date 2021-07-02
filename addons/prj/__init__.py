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
import time

class Prj(bpy.types.Operator):
    """Set view to camera to export svg from grease pencil"""
    initial_scene_camera: bpy.types.Object
    draw_context: Drawing_context
    draw_maker: Drawing_maker
    key: str
    selected_objects_names: list[str]
    selected_camera: bpy.types.Object

    bl_idname = "prj.modal_operator"
    bl_label = "Set 3d view as selected camera and launch prj"
    bl_options = {'REGISTER', 'UNDO'}

    def get_camera(self, selection: list[bpy.types.Object]) -> bpy.types.Object:
        ''' Get selected camera '''
        cams = [obj for obj in selection if obj.type == 'CAMERA']
        if len(cams) != 1:
            self.report({'WARNING'}, "Just one camera has to be selected")
            return None
        return cams[0]

    def reset_scene(self, context: bpy.types.Context) -> set[str]:
        bpy.context.scene.camera = self.initial_scene_camera
        bpy.ops.view3d.view_camera()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.area.type == 'VIEW_3D'

    def execute(self, context: bpy.types.Context):
        ## TODO fix composition filepath (now it's on application directory)
        rewrite_svgs(self.draw_context)
        get_svg_composition(self.draw_context)

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) \
            -> set[str]:
        self.key = None
        context.area.header_text_set("Type Enter to create drawing, " + \
                "H for hiddden, B for back, ESC for exit")
        ## TODO allow set key by UI
        if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'}:
            #self.key = '-cp -a -t -r 80cm'
            self.key = '-cp -a -r 80cm'
            #self.key = '-cp'
        elif event.type == 'H':
            self.key = '-h'
        elif event.type == 'B':
            self.key = '-b'
        elif event.type == 'ESC':
            self.reset_scene(context)
            return {'CANCELLED'}

        if self.key:
            print('Start now')
            start_time = time.time()
            objs = ';'.join(self.selected_objects_names + \
                    [self.selected_camera.name])
            args = self.key.split() + [objs]
            print('Set context now')
            self.draw_context = Drawing_context(args, context)
            print('Set context after', (time.time() - start_time))
            self.draw_maker = Drawing_maker(self.draw_context)
            print('Set maker after', (time.time() - start_time))
            draw_subjects(self.draw_context, self.draw_maker, 
                    self.draw_context.timing_test)
            self.reset_scene(context)
            self.execute(context)
            print("\n--- Completed in %s seconds ---\n\n" % 
                    (time.time() - start_time))
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) \
            -> set[str]:
        selection = bpy.context.selected_objects
        self.selected_objects_names = [obj.name for obj in selection 
                if is_renderables(obj)]
        self.selected_camera = self.get_camera(selection)
        if not self.selected_camera:
            return {'CANCELLED'}

        self.initial_scene_camera = bpy.context.scene.camera
        bpy.context.scene.camera = self.selected_camera
        bpy.ops.view3d.view_camera()

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(Prj)

def unregister():
    bpy.utils.unregister_class(Prj)

if __name__ == "__main__":
    register()
