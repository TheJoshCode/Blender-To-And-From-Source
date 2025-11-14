# Blender-To-And-From-Source

## A SourceIO Fork with Export Support for Source 2 (Counter-Strike 2)

Now includes CS2 Asset Export in the export options.

---

# Features

### Smart Material & Texture Export

The exporter scans a material's full node graph, including recursively nested node groups. to identify texture types using:

- **Fuzzy name matching** (albedo, diffuse, normalmap, etc.)
- **Automatic heuristics:**
  - Basecolor detection
  - Roughness recognition from grayscale
  - Normal map detection via blue-channel dominance
- Full texture saving pipeline with auto-resizing to multiple-of-4 dimensions for Source 2 support
- Automatic fallback textures if missing or not valid

Exports materials to VMAT using `csgo_complex` and generates:

- Basecolor (`*_color.tga`)
- Roughness (`*_rough.tga`)
- Normal (`*_normal.tga`)
- AO default map
- Metalness parameter

### Mesh Export

- Exports each mesh object individually and exports a full-scene FBX
- Supports mesh modifiers
- Disables leaf bones
- Uses correct axis settings for Source 2

### Folder & File Structure

The exporter auto-generates:

```bash
export_folder/
    materials/
        material_name.vmat
        material_name_color.tga
        material_name_rough.tga
        material_name_normal.tga
    models/
        meshobject1.fbx
        meshobject2.fbx
    scene.fbx
```

### Automatic Physics Surface Detection

Material names are scanned for Source surface keywords (e.g., metal, concrete, wood), generating proper:

```bash
PhysicsSurfaceProperties "wood"
```

### Automatic Material Renaming

All Blender materials are auto-normalized to the format:

```
materials/<material_name>
```

Ensuring VMAT outputs always reference the correct directory structure.

---

## Credits

- **SourceIO** by REDxEYE: original import pipeline and foundational structure

## License

This project follows the same license as the original SourceIO repository.  
See LICENSE for details.
