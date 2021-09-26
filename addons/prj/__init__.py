bl_info = {
    "name": "Prj",
    "blender": (2, 90, 0),
    "category": "3D View",
}

import bpy
import os, pathlib
import copy
from prj.drawing_context import get_drawing_context, is_renderables
from prj.drawing_style import create_drawing_styles
from prj.main import draw_subjects, rewrite_svgs, get_svg_composition
from prj.utils import flatten, reverse_camera
from prj.working_scene import get_working_scene
import time

STRING_NUMBERS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
DIGITS = {'NUMPAD_0', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3', 'NUMPAD_4', 
        'NUMPAD_5', 'NUMPAD_6', 'NUMPAD_7', 'NUMPAD_8', 'NUMPAD_9', 
        'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT',
        'NINE', 'ZERO', 'NUMPAD_SLASH', 'NUMPAD_PERIOD', 'SLASH', 'PERIOD', 
        'SEMI_COLON', 'COMMA'}
FLAGS = {
        'A': {'caption':'select all', 'status': 'OFF', 'exclude': ['B']},
        'X': {'caption':'x-ray', 'status': 'OFF', 'exclude': []},
        'B': {'caption':'back', 'status': 'OFF', 'exclude': ['A']},
        'O': {'caption':'outline', 'status': 'OFF', 'exclude': ['W']},
        'W': {'caption':'wireframe', 'status': 'OFF', 'exclude': ['O']}
        }
list_replace = lambda li, old, new: [new if v == old else v for v in li]

def remove_list_dupli(li: list, element) -> None:
    """ Remove all duplicates of element from li and keep the first occurrence"""
    li.reverse()
    while li.count(element) > 1:
        li.remove(element)
    li.reverse()

def get_listed_digit(li_digits: list[str]) -> float:
    """ Convert li_digits (a list of digits) in a float """
    if not li_digits:
        return 0
    li_digits = list_replace(li_digits, ',', '.') 
    remove_list_dupli(li_digits, '.')
    if len(li_digits) == 1 and not li_digits[0]:
        li_digits[0] = '1'
    elif li_digits[0] == '.':
        return float('0' + ''.join(li_digits))
    value = float(''.join(li_digits))
    if value.is_integer():
        return int(value)
    return value

def get_scale_division(numerator: float, denominator: float) -> tuple:
    """ Get the value and the string representation of scale """
    if numerator == 0:
        numerator = 1
    if denominator == 0:
        denominator = 1
    return numerator/denominator, f'{numerator}:{denominator}'

def get_scale_repr(scale_digits) -> tuple:
    """ Convert scale_digits list in a tuple containing scale value and
        a string representation of scale value """
    scale_digits = list_replace(scale_digits, '/', ':') 
    remove_list_dupli(scale_digits, ':')
    if ':' in scale_digits:
        semicolon = scale_digits.index(':')
        numerator_list = scale_digits[:semicolon]
        numerator = get_listed_digit(numerator_list)
        denominator_list = scale_digits[semicolon+1:]
        denominator = get_listed_digit(denominator_list)
        scale_division = get_scale_division(numerator, denominator)
        return scale_division
    else:
        scale = get_listed_digit(scale_digits)
        return scale, str(scale)

class Prj(bpy.types.Operator):
    """Set view to camera to export svg from grease pencil"""
    initial_scene: bpy.types.Scene
    initial_scene_camera: bpy.types.Object
    drawing_context: 'Drawing_context'
    flag_keys: list[str] = []
    scale_digits: list[str] = []
    scale: tuple
    selected_objects_names: list[str]
    selected_camera: bpy.types.Object

    DEFAULT_SCALE = .01, '1:100'
    bl_idname = "prj.modal_operator"
    bl_label = "Set 3d view as selected camera and launch prj"
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self):
        self.scale = self.DEFAULT_SCALE
        self.flag_dict = copy.deepcopy(FLAGS)   
        self.drawing_context = None

    def __del__(self):
        print('End')

    def update_flags(self, flag: str, remove: bool) -> None:
        """ Update self.flag_keys and self.flag_dict by adding or 
            removing flag """
        if remove:
            self.flag_keys.remove(flag)
        else:
            self.flag_keys.append(flag)
            exclude = self.flag_dict[flag]['exclude']
            for excl_flag in exclude:
                if excl_flag in self.flag_keys:
                    self.flag_keys.remove(excl_flag)
        for f in self.flag_dict:
            self.flag_dict[f]['status'] = 'ON' if f in self.flag_keys else 'OFF'

    def get_camera(self, selection: list[bpy.types.Object]) -> bpy.types.Object:
        ''' Get selected camera '''
        cams = [obj for obj in selection if obj.type == 'CAMERA']
        if len(cams) != 1:
            self.report({'WARNING'}, "Just one camera has to be selected")
            return None
        return cams[0]

    def reset_scene(self, reverse_cam: bool) -> set[str]:
        """ Reset scene as it was before launching Prj """
        if self.drawing_context:
            self.drawing_context.remove()
            del self.drawing_context
        if reverse_cam:
            reverse_camera(self.selected_camera)
        self.flag_keys.clear()
        self.scale_digits.clear()
        self.flag_dict = copy.deepcopy(FLAGS)   
        r3d = bpy.context.space_data.region_3d
        bpy.context.window.scene = self.initial_scene
        bpy.context.scene.camera = self.initial_scene_camera
        r3d.view_perspective = self.initial_view_perspective
        bpy.context.area.header_text_set(None)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.area.type == 'VIEW_3D'

    def execute(self, context):
        print('Start now')
        start_time = time.time()
        bpy.context.space_data.region_3d.view_perspective = "CAMERA"

        scale = ['-s', str(self.scale[0])]
        keys = ['-' + flag.lower() for flag in self.flag_keys]
        objs = [';'.join(self.selected_objects_names + \
                [self.selected_camera.name])]
        args = scale + keys + objs
        print('args', args)

        create_drawing_styles()
        self.drawing_context = get_drawing_context(args)
        all_subjects = list(set(flatten(self.drawing_context.subjects.values())))
        working_scene = get_working_scene().scene
        bpy.context.window.scene = working_scene
        depsgraph = bpy.context.evaluated_depsgraph_get()
        draw_subjects(all_subjects, working_scene) 

        rewrite_svgs(all_subjects)
        get_svg_composition(all_subjects)
        self.reset_scene(reverse_cam = 'B' in self.flag_keys)
        print(f"\n--- Completed in {time.time() - start_time} seconds ---\n\n")

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) \
            -> set[str]:
        """ Set flags and scale by user input """
        context.area.header_text_set("Type Enter to create drawing, " + \
                "A=drawing all, X=x-ray, B=back, O=outline, W=wireframe")
        ## UI TODO allow set key by UI
        if event.type == 'ESC': 
            context.area.header_text_set(None)
            self.reset_scene(reverse_cam=False)
            return {'CANCELLED'}
        elif event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'}:
            context.area.header_text_set(None)
            if 'B' in self.flag_keys and not self.selected_objects_names:
                self.report({'WARNING'}, 
                        "Back drawings need one or more objects selected")
                return {'CANCELLED'}
            if 'B' in self.flag_keys:
                reverse_camera(self.selected_camera)
            self.execute(context)
            return {'FINISHED'}
        else:
            if event.type in self.flag_dict and event.unicode:
                flag = event.unicode.upper()
                self.update_flags(flag, remove=flag in self.flag_keys)
            elif event.type in DIGITS:
                digit = event.unicode
                self.scale_digits.append(digit)
                self.scale = get_scale_repr(self.scale_digits) \
                        if self.scale_digits else self.DEFAULT_SCALE
            elif event.type == 'BACK_SPACE' and self.scale_digits:
                self.scale_digits.pop()
                self.scale = get_scale_repr(self.scale_digits) \
                        if self.scale_digits else self.DEFAULT_SCALE

            headers = []
            for f in self.flag_dict:
                header = f"{f}: {self.flag_dict[f]['caption']} "
                header += f"({self.flag_dict[f]['status']})"
                headers.append(header)
            #print(', '.join(headers))
            #print('flag', self.flag_keys)

            context.area.header_text_set(
                    'Scale: ' + self.scale[1] + ', ' + ', '.join(headers))
            return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) \
            -> set[str]:

        r3d = context.space_data.region_3d
        self.initial_scene = bpy.context.scene
        self.initial_scene_camera = bpy.context.scene.camera
        self.initial_view_perspective = r3d.view_perspective
        # In order to avoid drawing error need not to be in camera view
        if r3d.view_perspective == 'CAMERA':
            r3d.view_perspective = 'PERSP'

        selection = bpy.context.selected_objects
        self.selected_objects_names = [obj.name for obj in selection 
                if is_renderables(obj)]
        self.selected_camera = self.get_camera(selection)
        if not self.selected_camera:
            return {'CANCELLED'}

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(Prj)

def unregister():
    bpy.utils.unregister_class(Prj)

if __name__ == "__main__":
    register()
