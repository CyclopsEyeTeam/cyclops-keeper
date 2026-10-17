"""Per-attachment painting preference. Contains only a fixed choice and binding."""
from pathlib import Path
from expression import identity,read_file
from launcher_link import atomic,read_attachment
FILENAME='.keeper-painting-choice.json'

def read(path,expected):
    try:
        value=read_file(Path(path).parent/FILENAME)
        if value.get('binding')==expected and value.get('mode') in ('free','work'):
            return value['mode']
    except (OSError,ValueError,TypeError):pass
    return 'free'

def write(path,expected,mode):
    if mode not in ('free','work'):raise ValueError('Invalid painting choice')
    if identity(read_attachment(path))!=expected:raise ValueError('Attachment changed')
    atomic(Path(path).parent/FILENAME,{'binding':expected,'mode':mode})
