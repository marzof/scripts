bl_info = {
    "name": "Prj",
    "blender": (2, 90, 0),
    "category": "3D View",
}

import bpy
import os, pathlib
from prj.drawing_context import get_drawing_context, is_renderables
from prj.drawing_subject import libraries
from prj.drawing_style import create_drawing_styles
from prj.main import draw_subjects, rewrite_svgs, get_svg_composition
from prj.utils import flatten
from prj.working_scene import get_working_scene
import time

class Prj(bpy.types.Operator):
    """Set view to camera to export svg from grease pencil"""
    initial_scene: bpy.types.Scene
    initial_scene_camera: bpy.types.Object
    drawing_context: 'Drawing_context'
    keys: list[str]
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

    def reset_scene(self) -> set[str]:
        bpy.context.window.scene = self.initial_scene

        ## TODO check if collecting libraries is still useful
        for library in libraries:
            try:
                library.reload()
            except ReferenceError:
                pass

        bpy.context.scene.camera = self.initial_scene_camera
        return {'FINISHED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.area.type == 'VIEW_3D'

    def execute(self, all_subjects: list['Drawing_subject']):
        rewrite_svgs(all_subjects)
        get_svg_composition(all_subjects)
        self.drawing_context.remove()
        del self.drawing_context
        self.reset_scene()

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) \
            -> set[str]:
        self.keys = []
        context.area.header_text_set("Type Enter to create drawing, " + \
                "A=drawing all, X=x-ray, B=back, O=outline, W=wireframe")
                ## TODO set scale too by typing
        ## UI TODO allow set key by UI
        if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'}:
            #self.keys += ['-a', '-s', '.05']
            self.keys += ['-s', '.05']
        elif event.type == 'A':
            self.keys.append('-a')
        elif event.type == 'X':
            self.keys.append('-x')
        elif event.type == 'B':
            #self.keys.append('-b')
            self.keys += ['-b', '-s', '.05']
        elif event.type == 'O':
            self.keys.append('-o')
        elif event.type == 'W':
            self.keys.append('-w')
        elif event.type == 'ESC':
            self.reset_scene()
            context.area.header_text_set(None)
            return {'CANCELLED'}

        if self.keys:
            print('Start now')
            start_time = time.time()
            objs = ';'.join(self.selected_objects_names + \
                    [self.selected_camera.name])
            print('keys', self.keys)
            args = self.keys + [objs]
            print('args', args)
            create_drawing_styles()
            print('Set context now')
            self.drawing_context = get_drawing_context(args)
            if self.drawing_context.back_drawing:
                self.drawing_context.drawing_camera.reverse_cam()
            print('Set context after', (time.time() - start_time))
            all_subjects = list(set(
                flatten(self.drawing_context.subjects.values())))
            working_scene = get_working_scene().scene
            bpy.context.window.scene = working_scene
            bpy.ops.view3d.view_camera()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            draw_subjects(all_subjects, working_scene) 
            self.execute(all_subjects)
            print("\n--- Completed in %s seconds ---\n\n" % 
                    (time.time() - start_time))
            context.area.header_text_set(None)
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

        self.initial_scene = bpy.context.scene
        self.initial_scene_camera = bpy.context.scene.camera

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(Prj)

def unregister():
    bpy.utils.unregister_class(Prj)

if __name__ == "__main__":
    register()
