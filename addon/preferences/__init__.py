from ..preferences.install_dependencies_operator import \
    MEASURES_OT_Install_Dependencies

from .addon import MEASURES_Props
from .color import MEASURES_Color
from .settings import MEASURES_Settings


classes = (
    MEASURES_Color,
    MEASURES_Settings,
    MEASURES_Props,
    MEASURES_OT_Install_Dependencies
)


def register_preferences():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister_preferences():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
