from .measures_geodesic_operator import MEASURES_GEODESIC_OT
from .measures_circular_operator import MEASURES_CIRCULAR_OT

classes = (
    MEASURES_CIRCULAR_OT,
    MEASURES_GEODESIC_OT
)


def register_operators():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister_operators():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
