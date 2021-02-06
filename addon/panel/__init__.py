from .measures_main_panel import MEASURES_PT_MAINPANEL
from .measures_circular_panel import MEASURES_PT_CIRCULAR_PANEL

classes = [MEASURES_PT_MAINPANEL, MEASURES_PT_CIRCULAR_PANEL]


def register_panels():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister_panels():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)