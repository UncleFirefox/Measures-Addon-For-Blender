import subprocess
from ..register.dependency_handling import \
    are_dependencies_installed, get_dependencies,\
    install_and_import_module, install_pip, set_dependency_installed_flag

from ..register import register_dependent_objects

import bpy


class MEASURES_OT_Install_Dependencies(bpy.types.Operator):
    bl_idname = "measures.install_dependencies"
    bl_label = "Install dependencies"
    bl_description = ("Downloads and installs the required python packages for this add-on. "
                      "Internet connection is required. Blender may have to be started with "
                      "elevated permissions in order to install the package")
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context):
        # Deactivate when dependencies have been installed
        return not are_dependencies_installed()

    def execute(self, context):
        try:
            install_pip()
            for dependency in get_dependencies():
                install_and_import_module(module_name=dependency.module,
                                          package_name=dependency.package,
                                          global_name=dependency.name)
        except (subprocess.CalledProcessError, ImportError) as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}

        set_dependency_installed_flag(True)

        # Register the panels, operators, etc. since dependencies are installed
        register_dependent_objects()

        return {"FINISHED"}
