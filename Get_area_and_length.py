import bpy
import bmesh

total_area = 0
total_length = 0
perimeter = 0
for obj in bpy.context.selected_objects:
    obj_area = 0
    obj_length = 0
    for face in obj.data.polygons:
        if face.select:
            obj_area += face.area
    bm = bmesh.from_edit_mesh(obj.data)
    for edge in bm.edges:
        if edge.select:
            print('edge', edge.index, edge.is_manifold)
            edge_length = edge.calc_length()
            print(edge.index, edge_length)
            obj_length += edge_length
            if not edge.is_manifold:
                perimeter += edge_length
    print(obj.name)
    total_area += obj_area
    total_length += obj_length
print('Total area', total_area)
print('Total length', total_length)
print('Perimeter', perimeter)