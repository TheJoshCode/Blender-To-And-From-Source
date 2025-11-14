bl_info = {
    "name": "CS2 Asset Exporter",
    "author": "JoshMakesStuff",
    "version": (1, 5, 3),
    "blender": (3, 0, 0),
    "location": "File > Export > CS2 Asset Exporter",
    "description": "Exports meshes and materials to Counter-Strike 2 compatible format with smart texture detection and heuristics (with recursive node group search)",
    "category": "Import-Export"
}

import bpy
import re
import difflib
from pathlib import Path
from datetime import datetime

# ---------------------------- CONSTANTS ----------------------------

SURFACE_TYPES = {
    'alienflesh', 'armorflesh', 'asphalt', 'audioblocker', 'balloon', 'beans', 'blockbullets',
    'bloodyflesh', 'boulder', 'brakingrubbertire', 'brass_bell_large', 'brass_bell_medium',
    'brass_bell_small', 'brass_bell_smallest', 'brick', 'canister', 'cardboard', 'carpet',
    'chain', 'chainlink', 'clay', 'cloth', 'computer', 'concrete', 'default', 'defuser', 'dirt',
    'flesh', 'foliage', 'fruit', 'glass', 'grass', 'grate', 'gravel', 'ice', 'item', 'ladder',
    'metal', 'metal_barrel', 'metal_box', 'metalgrate', 'metalpanel', 'mud', 'paintcan', 'paper',
    'plaster', 'plastic', 'player', 'popcan', 'porcelain', 'rock', 'rubber', 'sand', 'slime',
    'snow', 'tile', 'upholstery', 'water', 'weapon', 'wet', 'wood', 'wood_box', 'wood_crate'
}

TEXTURE_KEYWORDS = {
    'color': ['base color','albedo','diffuse','diff','col','diff_col','diffuse_col','diffusecolor','albedomap','diffusemap'],
    'normal': ['normal','nmap','bump','nm','normalmap','bumpmap','n','normal_tex','normal_texture','map_normal'],
    'rough': ['roughness','rough','gloss','glossiness','roughmap','rough_tex','rough_texture','roughness_map','r','gloss_map']
}

# ---------------------------- UTILITIES ----------------------------

def sanitize_name(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name or 'material'

def fuzzy_match_score(text, keywords):
    """Return best similarity score between text and any keyword."""
    text_words = re.split(r'[\s_-]+', text.lower())
    camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', text).lower().split()
    text_words += camel_split

    best_score = 0.0
    for kw in keywords:
        for word in text_words:
            score = difflib.SequenceMatcher(None, word, kw.lower()).ratio()
            if score > best_score:
                best_score = score
    return best_score

def resize_image_to_multiple_of_4(image):
    width = max(4, image.size[0] - (image.size[0] % 4))
    height = max(4, image.size[1] - (image.size[1] % 4))
    if image.size != (width, height):
        print(f"[DEBUG] Resizing image {image.name} from {image.size} to ({width}, {height})")
        image.scale(width, height)

def save_image(image, filepath):
    resize_image_to_multiple_of_4(image)
    image.filepath_raw = str(filepath)
    image.file_format = 'TARGA'
    image.save()
    print(f"[DEBUG] Saved texture {filepath}")

# ---------------------------- NODE RECURSION ----------------------------

def get_all_nodes_recursive(node_tree, visited=None):
    """Recursively yield all nodes from the given node_tree, including nested node groups."""
    if node_tree is None:
        return
    if visited is None:
        visited = set()
    if node_tree in visited:
        return
    visited.add(node_tree)

    for node in node_tree.nodes:
        yield node
        # Recursively search into node groups
        if isinstance(node, bpy.types.ShaderNodeGroup) and node.node_tree:
            yield from get_all_nodes_recursive(node.node_tree, visited)

# ---------------------------- IMAGE ANALYSIS ----------------------------

def is_grayscale(image):
    """Estimate if image is grayscale based on sampled pixels."""
    if not image.has_data:
        return False
    pixels = list(image.pixels)
    if len(pixels) < 12:
        return False
    stride = max(1, len(pixels) // 500)
    color_diff_sum = 0
    count = 0
    for i in range(0, len(pixels) - 3, stride * 4):
        r, g, b = pixels[i:i+3]
        color_diff_sum += abs(r - g) + abs(g - b) + abs(b - r)
        count += 1
    avg_diff = color_diff_sum / count if count else 1
    return avg_diff < 0.02

def looks_like_normal_map(image):
    """Heuristic: bluish dominant and not grayscale."""
    if not image.has_data:
        return False
    pixels = list(image.pixels)
    if len(pixels) < 12:
        return False
    stride = max(1, len(pixels) // 500)
    blue_dominance = 0
    count = 0
    for i in range(0, len(pixels) - 3, stride * 4):
        r, g, b = pixels[i:i+3]
        if b > r and b > g:
            blue_dominance += 1
        count += 1
    return (blue_dominance / count) > 0.6

# ---------------------------- TEXTURE GETTERS ----------------------------

def get_texture(material, tex_type, materials_dir, used_images):
    best_image = None
    best_score = 0.0

    # Step 1: Try fuzzy match on node/image names
    for node in get_all_nodes_recursive(material.node_tree):
        if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image and node.image not in used_images:
            score = max(
                fuzzy_match_score(node.name, TEXTURE_KEYWORDS[tex_type]),
                fuzzy_match_score(node.image.name, TEXTURE_KEYWORDS[tex_type])
            )
            print(f"[DEBUG] {tex_type.capitalize()} score {score:.2f} for {node.image.name}")
            if score > best_score:
                best_score = score
                best_image = node.image

    # Step 2: Heuristic fallback based on texture properties
    if (not best_image or best_score < 0.4):
        for node in get_all_nodes_recursive(material.node_tree):
            if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image and node.image not in used_images:
                img = node.image
                if tex_type == "color" and not is_grayscale(img) and not looks_like_normal_map(img):
                    print(f"[DEBUG] Heuristic basecolor candidate: {img.name}")
                    best_image = img
                    break
                elif tex_type == "rough" and is_grayscale(img):
                    print(f"[DEBUG] Heuristic roughness candidate: {img.name}")
                    best_image = img
                    break
                elif tex_type == "normal" and looks_like_normal_map(img):
                    print(f"[DEBUG] Heuristic normal candidate: {img.name}")
                    best_image = img
                    break

    # Step 3: Save or use default
    if best_image:
        tex_name = f"{sanitize_name(material.name.split('/')[-1])}_{tex_type}.tga"
        tex_path = materials_dir / tex_name
        save_image(best_image, tex_path)
        used_images.add(best_image)
        return f"materials/{tex_name}", best_image

    print(f"[DEBUG] Using default {tex_type} for {material.name}")
    return f"materials/default/default_{'rough' if tex_type=='rough' else tex_type}.tga", None

# ---------------------------- EXPORT PIPELINE ----------------------------

def get_surface_type(material_name):
    surface = next((s for s in SURFACE_TYPES if s in material_name.lower()), 'default')
    print(f"[DEBUG] Surface type for {material_name} is {surface}")
    return surface

def export_material(material, materials_dir):
    mat_name = sanitize_name(material.name.split('/')[-1])
    vmat_path = materials_dir / f"{mat_name}.vmat"

    print(f"[DEBUG] Exporting material {material.name} as VMAT {vmat_path.name}")

    used_images = set()

    color_path, color_img = get_texture(material, 'color', materials_dir, used_images)
    rough_path, rough_img = get_texture(material, 'rough', materials_dir, used_images)
    normal_path, normal_img = get_texture(material, 'normal', materials_dir, used_images)

    # Intelligent fallback: if no normal map but basecolor looks like one
    if (normal_img is None) and (color_img is not None) and looks_like_normal_map(color_img):
        print(f"[DEBUG] Basecolor {color_img.name} looks like a normal map — reassigning")
        normal_img = color_img
        normal_name = f"{sanitize_name(material.name.split('/')[-1])}_normal.tga"
        normal_path = f"materials/{normal_name}"
        save_image(normal_img, materials_dir / normal_name)
        used_images.add(normal_img)
        color_path = "materials/default/default_color.tga"

    textures = {
        'color': color_path,
        'rough': rough_path,
        'normal': normal_path,
        'ao': 'materials/default/default_ao.tga',
        'metalness': 0.0
    }

    surface_type = get_surface_type(material.name)

    vmat_content = f"""// Auto-generated VMAT file
Layer0
{{
    shader "csgo_complex.vfx"
    TextureColor "{textures['color']}"
    TextureNormal "{textures['normal']}"
    TextureRoughness "{textures['rough']}"
    TextureAmbientOcclusion "{textures['ao']}"
    g_flMetalness "{textures['metalness']:.3f}"
    g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
    SystemAttributes
    {{
        PhysicsSurfaceProperties "{surface_type}"
    }}
}}"""
    vmat_path.write_text(vmat_content)
    print(f"[DEBUG] VMAT file saved: {vmat_path}")

def export_fbx(objects, fbx_path):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True, apply_scale_options='FBX_SCALE_UNITS',
                             object_types={'MESH'}, bake_space_transform=True,
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             use_mesh_modifiers=True, add_leaf_bones=False, path_mode='AUTO')
    bpy.ops.object.select_all(action='DESELECT')
    print(f"[DEBUG] FBX exported: {fbx_path}")

def export_assets(context, export_dir):
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    materials_dir = export_path / 'materials'
    models_dir = export_path / 'models'
    materials_dir.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    print(f"[DEBUG] Starting export to {export_path}")

    for mat in bpy.data.materials:
        if not mat.name.startswith('materials/'):
            mat.name = f'materials/{mat.name}'
            print(f"[DEBUG] Renamed Blender material to {mat.name}")

    for mat in bpy.data.materials:
        export_material(mat, materials_dir)

    mesh_objs = [obj for obj in context.scene.objects if obj.type == 'MESH']
    for obj in mesh_objs:
        export_fbx([obj], models_dir / f"{obj.name}.fbx")

    export_fbx(mesh_objs, export_path / 'scene.fbx')
    print(f"[DEBUG] Asset export complete")

# ---------------------------- BLENDER UI ----------------------------

class ExportCS2(bpy.types.Operator):
    bl_idname = "export_scene.cs2_export"
    bl_label = "Export to CS2 Format"
    bl_options = {'REGISTER', 'UNDO'}

    directory: bpy.props.StringProperty = bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        try:
            export_assets(context, self.directory)
            self.report({'INFO'}, f"Successfully exported CS2 assets to {self.directory}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def menu_func_export(self, context):
    self.layout.operator(ExportCS2.bl_idname, text="CS2 Asset Exporter", icon='EXPORT')

def register():
    bpy.utils.register_class(ExportCS2)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ExportCS2)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
