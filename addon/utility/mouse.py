
PADDING = 80

def mouse_warp(context, event):
    '''Warp the mouse in the screen region.'''

    mouse_pos = (event.mouse_region_x, event.mouse_region_y)
    x_pos = mouse_pos[0]
    y_pos = mouse_pos[1]

    # X Warp
    if mouse_pos[0] + PADDING > context.area.width:
        x_pos = PADDING + 5
    elif mouse_pos[0] - PADDING < 0:
        x_pos = context.area.width - (PADDING + 5)

    # Y Warp
    if mouse_pos[1] + PADDING > context.area.height:
        y_pos = PADDING + 5
    elif mouse_pos[1] - PADDING < 0:
        y_pos = context.area.height - (PADDING + 5)

    if x_pos != mouse_pos[0] or y_pos != mouse_pos[1]:
        x_pos += context.area.x
        y_pos += context.area.y
        context.window.cursor_warp(x_pos, y_pos)