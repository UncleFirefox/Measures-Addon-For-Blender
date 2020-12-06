from .measures_panel import MEASURES_PT_MAINPANEL

classes = [MEASURES_PT_MAINPANEL]


def register_panels():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister_panels():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)