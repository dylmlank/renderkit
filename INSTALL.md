# RenderKit Installation & Setup

## Quick Start

RenderKit is a Blender add-on that lets you prompt Claude to model, light, and render directly in Blender.

### Prerequisites
- Blender 3.0+
- Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com/account/keys))

### Installation

1. **Clone or download renderkit to a known location** (e.g., `E:\renderkit`).

2. **In Blender:**
   - Go to `Edit > Preferences > Add-ons > Install...`
   - Browse to `renderkit/blender_addon/renderkit_panel.py` and select it
   - Search for "RenderKit Panel" in Add-ons and enable it
   - Click "RenderKit Panel" > Preferences
   - Paste your Anthropic API key
   - (Optional) Set the RenderKit folder path if it's not `E:\renderkit`

3. **Open the panel:**
   - Press `N` in the 3D viewport
   - Click the "RenderKit" tab on the right sidebar

### Usage

Type a prompt like:
- "a low-poly tree on a plane with soft studio lighting"
- "a metal sphere with a mirror-finish reflection on a black background"
- "an isometric architectural scene with a sunrise"

Click **Generate** and Claude will build it for you, calling tools to:
- Create primitives, add modifiers
- Set up materials and textures (PolyHaven PBR)
- Import HDRIs (PolyHaven free environments)
- Place lights and cameras
- Keyframe animations

Claude can also take screenshots to iterate and refine your scene.

### Troubleshooting

**No API key prompt?**
- Go to Edit > Preferences > Add-ons, search "RenderKit Panel", click it
- Click the Preferences button if you don't see it

**Generation fails with "Cannot connect"?**
- Verify your API key is valid at console.anthropic.com
- Check that renderkit folder path is correct in Preferences

**Tools not found?**
- Ensure the renderkit folder path points to the repo with `core/tools.py`
- Restart Blender if you recently changed the path

## How It Works

1. Your prompt goes to Claude via the Anthropic API
2. Claude calls RenderKit's 20+ tools (bpy wrapped)
3. Each tool executes directly in your Blender session (InProcessBridge)
4. Screenshots are sent back to Claude for feedback
5. Claude iterates until happy with the result

## Supported Tools

- **Modeling:** add_mesh_primitive, apply_modifier (subsurf, bevel, array, etc.)
- **Materials & Textures:** apply_texture (PolyHaven PBR), apply_material_preset
- **Lighting:** three_point_lighting, apply_light_preset
- **Environments:** set_hdri (PolyHaven free)
- **Cameras:** add_camera_and_track, keyframe_camera_move
- **Scene:** get_scene_info, get_object_info, screenshot, set_render_preview
- **Code:** run_blender_code (for advanced customization)

See `core/tools.py` for the full list and argument specs.

## Notes

- PolyHaven assets require internet access (they're downloaded on-demand, free)
- Rendering is preview-only; use Blender's normal render engine for final output
- Image generation (AI textures, backgrounds) is not yet supported; only PolyHaven assets
- The panel stores your API key in Blender's add-on preferences (not on disk)

## Need Help?

- Check `core/tools.py` for tool signatures and descriptions
- Read `blender_addon/renderkit_panel.py` to understand the UX flow
- Inspect `core/bridge.py` for the bpy command execution layer
