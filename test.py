from academics.models import SchoolClass 



SEED_CLASSES = [
    # key        name                  level_type   order
    ('baby',    'Baby Class',         'nursery',   1),
    ('middle',  'Middle Class',       'nursery',   2),
    ('top',     'Top Class',          'nursery',   3),
    ('p1',      'Primary One',        'primary',   4),
    ('p2',      'Primary Two',        'primary',   5),
    ('p3',      'Primary Three',      'primary',   6),
    ('p4',      'Primary Four',       'primary',   7),
    ('p5',      'Primary Five',       'primary',   8),
    ('p6',      'Primary Six',        'primary',   9),
    ('p7',      'Primary Seven',      'primary',   10),
]

for key, name, level_type, order in SEED_CLASSES:
    SchoolClass.objects.get_or_create(
        key=key,
        defaults={'name': name, 'level_type': level_type, 'order': order}
    )