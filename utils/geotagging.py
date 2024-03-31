import itertools


def calc_geotag(lat, lon, dec_dig=5):
    """Return geotag using specified precision

    Args:
        lat (float): latitude
        lon (float): longitude
        dec_dig (int): number of decimal places to consider   

    """

    # Ensure floating so decimal-dependent string operations function
    lat, lon = float(lat), float(lon)

    if lat < 0:
        lat_prefix = 'S'
        s_lat = str(lat).split('.')[0].zfill(3) + '.' + \
                str(lat).split('.')[1] + '00000000'
    else:
        lat_prefix = 'N'
        s_lat = str(lat).split('.')[0].zfill(2) + '.' + \
                str(lat).split('.')[1] + '00000000'

    if lon < 0:
        lon_prefix = 'W'
        s_lon = str(lon).split('.')[0].zfill(4) + '.' + \
                str(lon).split('.')[1] + '00000000'
    else:
        lon_prefix = 'E'
        s_lon = str(lon).split('.')[0].zfill(3) + '.' + \
                str(lon).split('.')[1] + '00000000'

    return '{}{}{}{}'.format(lon_prefix, ''.join(
            [i for i in str(s_lon) if i not in '-.'])[:(3 + dec_dig)],
                             lat_prefix, ''.join(
                    [i for i in str(s_lat) if i not in '-.'])[:(2 + dec_dig)])


def surrounding_geotags(geotag, n=1, **kwargs):
    """Function Create List of Tags Created by Altering Last Value"""
    if 'N' in geotag:
        suffix = 'N'
    elif 'S' in geotag:
        suffix = 'S'
    else:
        raise KeyError('Invalid latitude suffix')

    if 'W' in geotag:
        prefix = 'W'
    elif 'E' in geotag:
        prefix = 'E'
    else:
        raise KeyError('Invalid longitude prefix')

    p_dig = int(geotag.split(suffix)[0][1:])
    s_dig = int(geotag.split(suffix)[1][:])
    geotags = ['{}{}{}{}'.format(prefix, str(p_dig + i[0]).zfill(8), suffix,
                                 str(s_dig + i[1]).zfill(7)) for i in
               set(itertools.permutations(2 * list(range(-n, n + 1)), 2))]

    return geotags


def geotag_round_errors(tags, n=3):
    """Function To Identify Tags Which, within input, are within +/- n 
    integer values of each other"""
    conflicts = {}

    for cnt, tag in enumerate(tags):
        for g in surrounding_geotags(tag, n):
            if g in tags and g != tag:
                conflicts[tag] = g

    return conflicts, tags


def surrounding_span_ids(span_id, nbr_delim='+', str_delim='-', n=4,
                         union=True):
    line_nbr, span_tag = span_id.split(nbr_delim)
    bst_tag, ast_tag = span_tag.split(str_delim)

    potential_bst = surrounding_geotags(bst_tag, n)
    potential_ast = surrounding_geotags(ast_tag, n)

    span_ids = set('{}+{}-{}'.format(line_nbr, i[0], i[1]) for i in
                   set(itertools.product(potential_bst, potential_ast)))
    flipped = set('{}+{}-{}'.format(line_nbr, i[0], i[1]) for i in
                  set(itertools.product(potential_ast, potential_bst)))

    if union:
        return span_ids.union(flipped)
    else:
        return span_ids, flipped


def surrounding_span_tags(span_tag, str_delim='-', n=1, union=True):
    bst_tag, ast_tag = span_tag.split(str_delim)

    potential_bst = surrounding_geotags(bst_tag, n)
    potential_ast = surrounding_geotags(ast_tag, n)

    span_tags = set('{}-{}'.format(i[0], i[1]) for i in
                   set(itertools.product(potential_bst, potential_ast)))
    flipped = set('{}-{}'.format(i[0], i[1]) for i in
                  set(itertools.product(potential_ast, potential_bst)))

    if union:
        return span_tags.union(flipped)
    else:
        return span_tags, flipped
