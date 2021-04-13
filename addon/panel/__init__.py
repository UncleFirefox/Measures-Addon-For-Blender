from .measures_geodesic_panel import MEASURES_PT_GEODESIC_PANEL
from .measures_main_panel import MEASURES_PT_MAINPANEL
from .measures_circular_panel import MEASURES_PT_CIRCULAR_PANEL

classes = [
    MEASURES_PT_CIRCULAR_PANEL,
    MEASURES_PT_GEODESIC_PANEL
]


def register_main_panel():
    from bpy.utils import register_class
    register_class(MEASURES_PT_MAINPANEL)


def register_panels():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister_panels():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


def unregister_main_panel():
    from bpy.utils import unregister_class
    unregister_class(MEASURES_PT_MAINPANEL)
