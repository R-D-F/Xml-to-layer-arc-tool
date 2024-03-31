import arcpy
import os
import time
import re


class Timer:
    def __init__(self):
        pass

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        s = time.time() - self.start
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        arcpy.AddMessage(
            '\n    - {0:.0f}:{1:02.0f}:{2:02.0f} elapsed'.format(h, m, s))


# String operations
def ensure_iterable(v):
    if v is None:
        return []
    elif not isinstance(v, (tuple, list, dict, set)):
        return [v]
    else:
        return v


def safe_name(s, upper=True):
    s = re.sub('[^a-z,0-9]', '_', s, flags=re.IGNORECASE)
    s = re.sub('_{2,}', '_', s)
    if upper:
        return s.upper()
    return s

# File/folder functions
def find_files(search_directory, search_str=None, ext=None, recursive=True):
    if not recursive:
        _files = [os.path.join(search_directory, _file)
                  for _file in os.listdir(search_directory)
                  if search_str.lower() in _file.lower()]

        if ext:
            _files = [f for f in _files if f.endswith(ext)]

        return _files

    file_list = []
    if os.path.exists(search_directory):
        for root, dirs, files in os.walk(search_directory):
            for _file in files:
                if search_str and search_str.lower() not in _file.lower():
                    continue

                if ext and os.path.splitext(_file)[1].replace('.', '') \
                        != ext.replace('.', ''):
                    continue

                file_list.append(os.path.join(root, _file))

    return file_list


def find_dirs(search_directory, search_str):
    dir_list = []
    if os.path.exists(search_directory):
        for root, dirs, files in os.walk(search_directory):
            for _dir in dirs:
                if search_str.lower() in _dir.lower():
                    dir_list.append(os.path.join(root, _dir))
    return dir_list


def count_records(fc_or_lyr):
    return int(arcpy.GetCount_management(fc_or_lyr)[0])


def approximate_match_value(key, dict1, dict2, margin=0.05, abs_val=1):
    """Determine Whether or Not Value Associated with Key Approximately Match:
    margin: relative percent change allowed (0.05 = 5%)
    abs_val: absolute magnitude of change allowed"""

    d1 = float(dict1[key])
    d2 = float(dict2[key])

    diff = abs(d2 - d1)

    # not Different
    if diff == 0:
        return True
    # Exceeds allowed value
    elif diff > abs_val:
        return False
    # Does not exceed allowed value and margin range is less than allowed value
    elif diff < abs_val and abs(margin * d1) < abs_val \
            and abs(margin * d2) < abs_val:
        return True
    # Difference exceeds allowable margin and is greater than allowed value
    elif diff > abs(margin * d1) or diff > abs(margin * d2):
        return False
    elif diff < abs_val:
        return True
    else:
        return False


# DXF
DXF_UNITS = """\
$INSUNITS
 70
     1
  9
"""


def munge_units(out_dxf):
    # munge on output to unset default drawing units
    with open(out_dxf, 'r+') as f:
        dxf_str = f.read()
        dxf_str = dxf_str.replace(DXF_UNITS, '')
        f.seek(0)
        f.write(dxf_str)
        f.truncate()


def export_colored_dxf(src, dst, re_color=False, cad_type=None,
                       seed=None):
    if 'Color'.lower() not in [i.name.lower() for i in arcpy.ListFields(src)]:
        re_color = True
        arcpy.AddField_management(src, 'Color', 'LONG')

    if 'Layer'.lower() not in [i.name.lower() for i in arcpy.ListFields(src)]:
        arcpy.AddField_management(src, 'Layer', 'TEXT')

    if cad_type:
        assert cad_type in ['3D Polyline', 'Polyline Z', 'Point']
        if 'CADType' not in [i.name.lower() for i in arcpy.ListFields(src)]:
            arcpy.AddField_management(src, 'CADType', 'TEXT')

        with arcpy.da.UpdateCursor(src, 'CADType') as cursor:
            for row in cursor:
                row[0] = cad_type
                cursor.updateRow(row)

    if re_color is True:
        with arcpy.da.UpdateCursor(src, ('Layer', 'Color')) as cursor:
            layer_colors, _color = {}, 0
            for row in cursor:
                row[0] = row[0].replace('//', '_')  # Not allowed in dxf
                if row[0] not in layer_colors:
                    _color += 1
                    layer_colors[row[0]] = _color
                row[1] = layer_colors[row[0]]
                cursor.updateRow(row)

    arcpy.ExportCAD_conversion(in_features=src,
                               Output_Type='DXF_R2013',
                               Output_File=dst,
                               Seed_File=seed)
    munge_units(dst)

