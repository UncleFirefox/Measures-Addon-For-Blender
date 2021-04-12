from ..register.dependency_handling import \
    import_dependencies, \
    set_dependency_installed_flag


def register_addon():

    set_dependency_installed_flag(False)

    # Preferences
    from ..preferences import register_preferences
    register_preferences()

    try:
        import_dependencies()
        set_dependency_installed_flag(True)
    except ModuleNotFoundError:
        print("Dependencies were not installed...")

    # Menus
    # from ..menu import register_menus
    # register_menus()

    # Panels
    from ..panel import register_panels
    register_panels()

    # Operators
    from ..operator import register_operators
    register_operators()

    # Keymaps
    # from .keymap import register_keymap
    # register_keymap()


def unregister_addon():

    # Preferences
    from ..preferences import unregister_preferences
    unregister_preferences()

    # Menus
    # from ..menu import unregister_menus
    # unregister_menus()

    # Panels
    from ..panel import unregister_panels
    unregister_panels()

    # Operators
    from ..operator import unregister_operators
    unregister_operators()

    # Keymaps
    # from .keymap import unregister_keymap
    # unregister_keymap()
