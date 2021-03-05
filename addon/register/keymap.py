# import bpy

# TODO: Register keymaps here when necessary, left an example just in case

# keys = []

# def register_keymap():

#     wm = bpy.context.window_manager
#     addon_keyconfig = wm.keyconfigs.addon
#     kc = addon_keyconfig

#     km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
#     kmi = km.keymap_items.new("wm.call_menu", "F", "PRESS", ctrl=True, shift=True)
#     kmi.properties.name = "GEM_MT_Main_Menu"
#     keys.append((km, kmi))


# def unregister_keymap():

#     for km, kmi in keys:
#         km.keymap_items.remove(kmi)

#     keys.clear()
