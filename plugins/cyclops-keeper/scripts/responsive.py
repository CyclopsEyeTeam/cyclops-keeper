"""Geometry-driven presentation policy; never changes activity or attachment."""
CODEX_FLOOR = (48, 12)


def allocate(mode, columns, rows, codex_floor=CODEX_FLOOR):
    """Reserve Codex's usable area before choosing a proportional companion."""
    floor_columns, floor_rows = codex_floor
    if columns < floor_columns or rows < floor_rows:
        return 0
    if mode == 'side':
        room = columns - floor_columns - 1
        return min(max(3, (columns - 1) * 3 // 10), room) if room >= 3 else 0
    if mode == 'top':
        room = rows - floor_rows - 1
        return min(max(1, (rows + 1) // 3), room) if room >= 1 else 0
    raise ValueError('Keeper layout must be side or top.')


def detail(columns, rows):
    """Bands follow aperture resolution in the existing 610×430 subcell form."""
    if columns < 2 or rows < 1:
        return 'insufficient'
    aperture = 68 * min(columns * 2 / 610, max(0, rows - 1) * 4 / 430) * .74
    if aperture >= 12:
        return 'full'
    if aperture >= 6:
        return 'compact'
    if aperture >= 3:
        return 'small'
    return 'micro'


class PresenceGate:
    """Collapse immediately; restore only after stable space with a spare margin."""
    def __init__(self):
        self.visible = False
        self.available_since = None

    def update(self, mode, columns, rows, now, codex_floor=CODEX_FLOOR):
        desired = allocate(mode, columns, rows, codex_floor)
        if self.visible:
            if desired == 0:
                self.visible = False
                self.available_since = None
            return desired
        spare = allocate(mode, columns - (2 if mode == 'side' else 0),
                         rows - (1 if mode == 'top' else 0), codex_floor)
        if not spare:
            self.available_since = None
            return 0
        if self.available_since is None:
            self.available_since = now
        if now - self.available_since < .3:
            return 0
        self.visible = True
        return desired
