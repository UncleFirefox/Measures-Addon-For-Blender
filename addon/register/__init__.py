def register_addon():

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