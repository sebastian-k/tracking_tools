bl_info = {
    "name": "Tracking Tools",
    "author": "Sebastian Koenig",
    "version": (1, 0),
    "blender": (3, 3, 0),
    "location": "Clip Editor",
    "description": "A variety of tracking related tools",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Clip Editor"
}

import bpy
from mathutils import Vector


def get_track_empties(context, tracks):
    # the selected empties are assumed to be the linked tracks
    # these ones will be the parents
    for e in context.selected_objects:
        if e.type != "EMPTY":
            continue
        tracks.append(e)
        e.empty_draw_size = 0.05
        e.layers = [False] + [True] + [False] * 18


def create_hook_empties(context, tracks, hooks):
    # create the actual hooks at the same position as the tracks
    scene = context.scene
    for track in tracks:
        # create a new empty, assign name and location
        hook = bpy.data.objects.new("CTRL_" + track.name, None)
        hook.location = track.matrix_world.to_translation()
        hook.empty_draw_size = 0.015
        hook.empty_draw_type = "CUBE"
        # link it to the scene
        scene.objects.link(hook)
        # add the new empty to the list of parents
        hooks.append(hook)
        # make the hook empty a child of the parent
        bpy.ops.object.select_all(action='DESELECT')
        track.select = True
        hook.select = True
        scene.objects.active = track
        bpy.ops.object.parent_set()
    bpy.ops.object.select_all(action='DESELECT')


def get_location(hooks):
    coords = []
    for h in hooks:
        coords.append(h.location * h.matrix_world)
    return coords


def create_canvas_object(context, name, hooks, cleanobject, cams):
    scene = context.scene
    from bpy_extras.io_utils import unpack_list
    # get all locations of the hooks in the list
    coords = get_location(hooks)
    # create the vertices of the cleanplate mesh
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(coords))
    me.vertices.foreach_set("co", unpack_list(coords))
    # create the object which is using the mesh
    ob = bpy.data.objects.new(name, me)
    ob.location = (0, 0, 0)
    # link it to the scene and make it active
    scene.objects.link(ob)
    scene.objects.active = ob
    ob.layers = [True] + [False] * 19
    # go into edit mode, select all vertices and create the face
    if not context.object.mode == "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.edge_face_add()
    bpy.ops.object.mode_set(mode="OBJECT")

    cleanobject.append(ob)

    bpy.ops.object.select_all(action='DESELECT')
    camera = cams[0]
    ob.select = True
    context.scene.objects.active = camera
    bpy.ops.object.parent_set()
    camera.select = False


def hook_em_up(hooks, ob):
    # create an yet unassigned hook modifier for each hook in the list
    modlist = []
    for hook in hooks:
        modname = "Hook_" + hook.name
        modlist.append(modname)
        mod = ob.modifiers.new(name=modname, type="HOOK")
        mod.object = hook
    # now for each vertex go to edit mode, select the vertex and assign the modifier
    verts = ob.data.vertices
    for i in range(len(verts)):
        # Deselect Everything in Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        ob.data.vertices[i].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.object.hook_assign(modifier=modlist[i])

    bpy.ops.object.mode_set(mode='OBJECT')


def hooker_cam(context, cams):
    for ob in bpy.data.objects:
        if ob.type == "CAMERA":
            cams.append(ob)
    camera = cams[0]
    camera.rotation_euler = (1.570796251296997, -0.0, 0.0)
    camera.location = (0, -8, 2.2)


def setup_scene(context):
    scene = context.scene
    scene.active_clip = context.space_data.clip


####### TEXTURE PROJECTION FUNCTIONS ###########


def prepare_mesh(context, ob, size, canvas, clip):
    me = ob.data
    # see if object is already prepared.das
    if not "is_prepared" in ob:
        # set Edit mode if needed
        if not context.object.mode == "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

        # make sure mesh is dense enough for projection
        if len(me.vertices) < 64:
            sub = ob.modifiers.new(name="Subsurf", type="SUBSURF")
            sub.subdivision_type = "SIMPLE"
            sub.levels = 4
            sub.render_levels = 4
            bpy.context.object.modifiers["Subsurf"].subdivision_type = 'SIMPLE'

        # unwrap and go back to object mode
        bpy.ops.uv.smart_project(island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")

        # make sure we have something to paint on
        if len(list(me.uv_layers)) > 0:
            if not me.uv_layers.get("projection"):
                me.uv_layers.new(name="projection")
        else:
            me.uv_layers.new(name="UVMap")
            me.uv_layers.new(name="projection")

        me.update()
        ob["is_prepared"] = True

        # create the uv-project modifier
        if ob.modifiers.get("UVProject"):
            print("Projector already setup")
            return
        projector = ob.modifiers.new(name="UVProject", type="UV_PROJECT")
        projector.uv_layer = "projection"
        projector.aspect_x = clip.size[0]
        projector.aspect_y = clip.size[1]
        projector.projectors[0].object = bpy.data.objects["Camera"]
        projector.uv_layer = "projection"


def change_viewport_background_for_painting(context, clip):
    # prepare the viewport for painting
    # if there is no image, create one
    # if there is one, change movieclip to images
    space = context.space_data
    scene = context.scene
    camera = scene.camera
    cam = camera.data
    cam.show_background_images = True

    # changing from movie to image will make it updates.
    bgpic = None

    if not cam.background_images:
        bgpic = cam.background_images.new()
    else:
        for img in cam.background_images:
            if img.source != 'MOVIE_CLIP':
                if img.image.filepath == clip.filepath:
                    bgpic = img
                else:
                    continue
            bgpic = img
            break

    bgpic.source = 'IMAGE'

    if bpy.data.images.get(clip.name):
        clipimage = bpy.data.images[clip.name]
    else:
        clipimage = bpy.data.images.load(path)

    bgpic.show_on_foreground = True
    bgpic.image = clipimage
    bgpic.image.filepath = clip.filepath
    bgpic.image_user.frame_start = clip.frame_start
    bgpic.image_user.frame_duration = clip.frame_duration
    bgpic.image_user.frame_offset = clip.frame_offset
    bgpic.image.colorspace_settings.name = clip.colorspace_settings.name


def set_cleanplate_brush(context, clip, canvas, ob):
    me = ob.data

    paint_settings = bpy.context.tool_settings.image_paint
    ps = paint_settings
    ps.brush = bpy.data.brushes['Clone']
    ps.brush.strength = 1
    ps.use_clone_layer = True
    ps.mode = "IMAGE"
    ps.clone_image = bpy.data.images[clip.name]
    me.uv_layer_clone = me.uv_layers.get("projection")
    ps.use_normal_falloff = False


def prepare_clean_bake_mat(context, ob, clip, size, movietype):
    data = bpy.data
    images = data.images
    projection_tex = "projected texture"
    projection_mat = "projected clip material"

    # create image if needed
    if clip.name in images:
        projection = images[clip.name]
    else:
        projection = data.images.new(clip.name, size, size)
    projection.filepath = clip.filepath
    projection.source = movietype
    projection.colorspace_settings.name = clip.colorspace_settings.name

    # create a material
    materials = data.materials
    if projection_mat in materials:
        mat = materials[projection_mat]
    else:
        mat = materials.new(projection_mat)
    mat.use_nodes = True
    tree = mat.node_tree
    links = tree.links
    nodes = tree.nodes

    # wipe tree
    for n in nodes:
        nodes.remove(n)

    image = tree.nodes.new(type='ShaderNodeTexImage')
    output = tree.nodes.new(type='ShaderNodeOutputMaterial')
    emit = tree.nodes.new(type='ShaderNodeEmission')
    uv = tree.nodes.new(type='ShaderNodeUVMap')

    image.image = projection
    image.image_user.use_auto_refresh = True
    image.image_user.frame_start = clip.frame_start
    image.image_user.frame_duration = clip.frame_duration

    links.new(uv.outputs[0], image.inputs[0])
    links.new(image.outputs[0], emit.inputs[0])
    links.new(emit.outputs[0], output.inputs[0])

    uv.location = image.location
    uv.location += Vector((-300.0, 0.0))
    emit.location = image.location
    emit.location += Vector((300.0, 0.0))
    output.location = emit.location
    output.location += Vector((300.0, 0.0))

    # assign the material to material slot 0 of ob
    if not len(list(ob.material_slots)) > 0:
        ob.data.materials.append(mat)
    else:
        ob.material_slots[0].material = mat


def ma_baker(context):
    render = context.scene.render
    # bpy.ops.object.bake_image()
    print("hello")


def setup_cleaned_material(context, ob, clip, canvas, movietype):
    materials = bpy.data.materials
    clean_mat = f'clean_material_{ob.name}'

    # create a material
    if clean_mat in materials:
        mat = materials.get(clean_mat)
    else:
        mat = materials.new(clean_mat)

    mat.use_nodes = True
    tree = mat.node_tree
    links = tree.links
    nodes = tree.nodes

    # wipe tree
    for n in nodes:
        nodes.remove(n)

    image = tree.nodes.new(type='ShaderNodeTexImage')
    output = tree.nodes.new(type='ShaderNodeOutputMaterial')
    emit = tree.nodes.new(type='ShaderNodeEmission')
    uv = tree.nodes.new(type='ShaderNodeUVMap')

    image.image = canvas
    uv.uv_map = "UVMap"

    links.new(uv.outputs[0], image.inputs[0])
    links.new(image.outputs[0], emit.inputs[0])
    links.new(emit.outputs[0], output.inputs[0])

    uv.location = image.location
    uv.location += Vector((-300.0, 0.0))
    emit.location = image.location
    emit.location += Vector((300.0, 0.0))
    output.location = emit.location
    output.location += Vector((300.0, 0.0))

    # assign the material to material slot 0 of ob
    if not len(list(ob.material_slots)) > 0:
        ob.data.materials.append(mat)
    else:
        ob.material_slots[0].material = mat


def setup_clean_renderlayer(context):
    # create override material for background layer (== Background)
    # create new renderlayer with object as shadeless (BI) or emit (cycles) (== Cleanplate)
    # create new Rlayer node mit Cleanplate
    # Alpha Over it over Movieclip, before Shadows
    pass


def prepare_for_cycles(context):
    context.scene.render.engine = "CYCLES"
    cleanobjects = []
    for ob in bpy.data.objects:
        if "is_prepared" in ob:
            cleanobjects.append(ob)
    for ob in cleanobjects:
        mat = ob.material_slots[0].material
        mat.use_nodes = True


######## CORNER PIN CLASSES ############


class VIEW3D_OT_track_hooker(bpy.types.Operator):
    bl_idname = "clip.track_hooker"
    bl_label = "John Lee Hooker"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'CLIP_EDITOR'

    def execute(self, context):

        name = "canvas"

        hooks = []
        tracks = []
        cleanobject = []
        cams = []

        setup_scene(context)
        # setup the camera
        hooker_cam(context, cams)

        # create the empties
        bpy.ops.clip.track_to_empty()

        # collect all empties that are selected (which is automatically the case after creating the track empties)
        get_track_empties(context, tracks)

        # create empties that will be the hooks and parent them to the tracks
        create_hook_empties(context, tracks, hooks)

        # get the position of the tracks, create a new object there and parent it to the camera
        create_canvas_object(context, name, hooks, cleanobject, cams)

        # make the cleaned object active via list, to avoid confusion
        ob = bpy.data.objects.get(cleanobject[0].name)
        context.scene.objects.active = ob

        #finally create the hooks
        hook_em_up(hooks, ob)

        return {'FINISHED'}


class CLIP_PT_corner_hooker(bpy.types.Panel):
    bl_idname = "clip.corner_hooker"
    bl_label = "Corner Hoocker"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Solve"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("clip.track_hooker")


################ TEXTURE PROJECT CLASSES ##########################


class VIEW3D_OT_texture_extraction_setup(bpy.types.Operator):
    bl_idname = "object.texture_extraction_setup"
    bl_label = "Texture Extractor"

    def execute(self, context):
        clip = context.scene.active_clip
        cleaned_object = context.active_object
        images = bpy.data.images

        clean_name = "cleanplate" + "_" + cleaned_object.name
        size = 2048
        movietype = clip.source

        # create a canvas to paint and bake on
        if clean_name not in images:
            canvas = images.new(clean_name, size, size)
        else:
            canvas = images[clean_name]

        prepare_mesh(context, cleaned_object, size, canvas, clip)

        prepare_clean_bake_mat(context, cleaned_object, clip, size, movietype)

        ma_baker(context)

        setup_cleaned_material(context, cleaned_object, clip, canvas, movietype)

        return {"FINISHED"}


class VIEW3D_OT_cleanplate_painter_setup(bpy.types.Operator):
    bl_idname = "object.cleanplate_painter_setup"
    bl_label = "Cleanplate Paint Setup"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'VIEW_3D'

    def execute(self, context):

        clip = context.scene.active_clip
        cleaned_object = context.active_object

        clean_name = "cleanplate" + "_" + cleaned_object.name
        size = 2048
        movietype = clip.source

        # create a canvas to paint and bake on
        images = bpy.data.images
        if not images.get(clean_name):
            canvas = images.new(clean_name, size, size)
        else:
            canvas = images[clean_name]

        prepare_mesh(context, cleaned_object, size, canvas, clip)
        setup_cleaned_material(context, cleaned_object, clip, canvas, movietype)
        change_viewport_background_for_painting(context, clip)
        set_cleanplate_brush(context, clip, canvas, cleaned_object)

        if not context.object.mode == "TEXTURE_PAINT":
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT")

        return {'FINISHED'}


class VIEW3D_OT_clean_render_switcher(bpy.types.Operator):
    bl_idname = "scene.clean_render_switcher"
    bl_label = "Switch Render Engine"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'VIEW_3D'

    def execute(self, context):
        prepare_for_cycles(context)

        return {'FINISHED'}


class VIEW3D_PT_cleanplate_creator(bpy.types.Panel):
    bl_idname = "object.cleanplate_creator_setup"
    bl_label = "Cleanplate Creator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator("object.texture_extraction_setup")
        col.operator("object.cleanplate_painter_setup")


def CLIP_spaces_walk(context, all_screens, tarea, tspace, callback, *args):
    screens = bpy.data.screens if all_screens else [context.screen]

    for screen in screens:
        for area in screen.areas:
            if area.type == tarea:
                for space in area.spaces:
                    if space.type == tspace:
                        callback(space, *args)


class CLIP_OT_PlaneTrackSetup(bpy.types.Operator):
    """Create a Plane Track Setup in the Compositor"""
    bl_idname = "clip.plane_track_setup"
    bl_label = "Plane Track Setup"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'CLIP_EDITOR'

    @staticmethod
    def _findNode(tree, type):
        for node in tree.nodes:
            if node.type == type:
                return node
        return None

    @staticmethod
    def _findOrCreateNode(tree, type):
        node = CLIP_OT_PlaneTrackSetup._findNode(tree, type)

        if not node:
            node = tree.nodes.new(type=type)
        return node

    def _setup_plane_track_nodes(self, tree, clip):

        #create image and planetrack node
        planetrack = tree.nodes.new(type='CompositorNodePlaneTrackDeform')
        image = tree.nodes.new(type='CompositorNodeImage')

        # set their properties
        planetrack.clip = clip
        planetrack.tracking_object = clip.tracking.objects.active.name
        planetrack.plane_track_name = clip.tracking.plane_tracks.active.name
        image.image = clip.tracking.plane_tracks.active.image

        # setup links
        tree.links.new(image.outputs[0], planetrack.inputs[0])

        # arrange nodes
        image.location = planetrack.location
        image.location += Vector((-400, 0.0))

        # return image and planetrack so we can use them in _setupNodes
        return (image, planetrack)

    def _setupNodes(self, context, clip):
        scene = context.scene
        scene.use_nodes = True
        tree = scene.node_tree

        # Enable backdrop for all compositor spaces
        def setup_space(space):
            space.show_backdrop = True

        CLIP_spaces_walk(context, True, 'NODE_EDITOR', 'NODE_EDITOR', setup_space)

        # create nodes
        composite = self._findOrCreateNode(tree, 'CompositorNodeComposite')
        viewer = tree.nodes.new(type='CompositorNodeViewer')
        # scale = tree.nodes.new(type='CompositorNodeScale')
        movieclip = tree.nodes.new(type='CompositorNodeMovieClip')
        alphaover = tree.nodes.new(type='CompositorNodeAlphaOver')

        # create planetrack nodes
        planetracknodes = self._setup_plane_track_nodes(tree, clip)
        image = planetracknodes[0]
        planetrack = planetracknodes[1]

        tree.links.new(movieclip.outputs["Image"], alphaover.inputs[1])
        tree.links.new(planetrack.outputs[0], alphaover.inputs[2])
        tree.links.new(alphaover.outputs[0], composite.inputs[0])
        tree.links.new(alphaover.outputs[0], viewer.inputs[0])

        movieclip.clip = clip

        alphaover.location = movieclip.location
        alphaover.location += Vector((300.0, 0.0))

        planetrack.location = movieclip.location
        planetrack.location += Vector((0.0, -400.0))

        composite.location = alphaover.location
        composite.location += Vector((800.0, 0.0))

        viewer.location = composite.location
        composite.location += Vector((0.0, 200.0))

    def execute(self, context):
        sc = context.space_data
        clip = sc.clip
        scene = context.scene
        tree = scene.node_tree

        if not tree or len(tree.nodes) == 0:
            # No compositor node tree found, time to create it!
            print(len(tree.nodes))
            self._setupNodes(context, clip)
        else:
            # see if there already is a planetrack setup
            planetracks = 0
            for node in tree.nodes:
                if node.type in {'PLANETRACKDEFORM'}:
                    planetracks += 1

            # no planetrack found, create image and planetrack
            if not planetracks:
                self._setup_plane_track_nodes(tree, clip)

        return {'FINISHED'}


########## REGISTER ############
classes = (
    VIEW3D_OT_clean_render_switcher,
    VIEW3D_OT_cleanplate_painter_setup,
    VIEW3D_OT_texture_extraction_setup,
    VIEW3D_OT_track_hooker,
    VIEW3D_PT_cleanplate_creator,
    CLIP_OT_PlaneTrackSetup,
    CLIP_PT_corner_hooker,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Clip', space_type='CLIP_EDITOR')
    kmi = km.keymap_items.new('clip.plane_track_setup', 'J', 'PRESS')


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
