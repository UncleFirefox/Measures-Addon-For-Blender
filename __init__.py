bl_info = {
    "name": "Measures Library",
    "author": "Albert Rodriguez",
    "description": "Tools to take measures for Avatar",
    "blender": (2, 92, 0),
    "version": (0, 7, 0),
    "location": "View3D > Toolshelf",
    "warning": "This plugin is only compatible with Blender 2.92",
    "category": "Add measures",
    "wiki_url": "https://github.com/UncleFirefox/Measures-Addon-For-Blender/wiki",
    "support": "COMMUNITY",
    "tracker_url": "https://github.com/UncleFirefox/Measures-Addon-For-Blender/issues"
}


def register():
    from .addon.register import register_addon
    register_addon()


def unregister():
    from .addon.register import unregister_addon
    unregister_addon()
