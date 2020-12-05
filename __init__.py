bl_info = {
    "name": "Measures Library",
    "author": "Albert Rodriguez",
    "description": "Tools to take measures for Avatar",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "View3D > Toolshelf",
    "warning": "",
    "category": "Add measures",
    "wiki_url": ""
}


def register():
    from .addon.register import register_addon
    register_addon()


def unregister():
    from .addon.register import unregister_addon
    unregister_addon()
