import arcpy
import csv
import os
import numpy as np
import pandas as pd
from collections import OrderedDict
from utils.geotagging import calc_geotag

try:
    import xml.etree.cElementTree as et
except ImportError:
    import xml.etree.ElementTree as et

arcpy.env.overwriteOutput = True

# Fields to be written
TOWER_REPORT_FIELDS = ['QSI_TOWER', 'STRUCTURE', 'X', 'Y', 'Z1', 'Z2', 'H',
                       'LATITUDE', 'LONGITUDE', 'STR_GEOTAG', 'STR_TYPE']

TOWER_REPORT_FIELD_TYPES = {'QSI_TOWER': 'LONG', 'X': 'DOUBLE', 'Y': 'DOUBLE',
                            'Z1': 'DOUBLE', 'Z2': 'DOUBLE', 'H': 'DOUBLE',
                            'LATITUDE': 'DOUBLE', 'LONGITUDE': 'DOUBLE',
                            'STATION': 'DOUBLE', 'OFFSET': 'DOUBLE'}

ATTACHMENT_FIELDS = ['STR_GEOTAG', 'SET_NO', 'PHASE', 'INS_TYPE', 'DEAD_END',
                     'LENGTH', 'COND_X', 'COND_Y', 'COND_Z', 'INS_X', 'INS_Y',
                     'INS_Z']
ATTACHMENT_FIELD_TYPES = {'SET_NO': 'LONG', 'PHASE': 'LONG',
                          'LENGTH': 'DOUBLE', 'COND_X': 'DOUBLE',
                          'COND_Y': 'DOUBLE', 'COND_Z': 'DOUBLE',
                          'INS_X': 'DOUBLE', 'INS_Y': 'DOUBLE',
                          'INS_Z': 'DOUBLE'}

ATTACHMENT_XML_FIELD_MAP = {'SECTION': 'section',
                            'SET_NO': 'set_no',
                            'PHASE': 'phase_no',
                            'LENGTH': 'length', 'COND_X': 'wire_attachment_x',
                            'COND_Y': 'wire_attachment_y',
                            'COND_Z': 'wire_attachment_z',
                            'INS_X': 'insulator_attachment_x',
                            'INS_Y': 'insulator_attachment_y',
                            'INS_Z': 'insulator_attachment_z'}

SPAN_FIELDS = ['SN', 'SECTION',
               'BST', 'BST_TAG', 'BST_ID', 'BST_STATION', 'BST_OFFSET',
               'AST', 'AST_TAG', 'AST_ID', 'AST_STATION', 'AST_OFFSET',
               'SPAN_TAG', 'SPAN_NAME', 'WIRES_PER_PHASE', 'PHASES',
               'WIRES_TOTAL', 'CABLE_FILE', 'SEC_NOTES', 'SHAPE@']

SPAN_FIELD_TYPES = {'SN': 'SHORT',
                    'SECTION': 'SHORT',
                    'SEC_NOTES': 'TEXT',
                    'BST': 'SHORT',
                    'BST_TAG': 'TEXT',
                    'BST_ID': 'TEXT',
                    'BST_STATION': 'DOUBLE',
                    'BST_OFFSET': 'DOUBLE',
                    'AST': 'SHORT',
                    'AST_TAG': 'TEXT',
                    'AST_ID': 'TEXT',
                    'AST_STATION': 'DOUBLE',
                    'AST_OFFSET': 'DOUBLE',
                    'SPAN_TAG': 'TEXT',
                    'SPAN_NAME': 'TEXT',
                    'WIRES_PER_PHASE': 'SHORT',
                    'PHASES': 'SHORT',
                    'WIRES_TOTAL': 'SHORT',
                    'CABLE_FILE': 'TEXT'}


def capitalize_dict_keys(_dict):
    upper_dict = {}
    for k, v in _dict.items():
        upper_dict[k.upper()] = v

    return upper_dict


def xml_header_info(xml_file, header_tag='creator'):
    tree = et.parse(xml_file)
    root = tree.getroot()

    headers = None
    for branch in root:
        if branch.tag == header_tag:
            headers = branch.attrib
            break

    return headers


def get_xml_tables(xml_file):
    tree = et.parse(xml_file)
    root = tree.getroot()
    tables = {branch.get('tagname'): branch for branch in root
              if branch.tag == 'table' and int(branch.get('nrows'))}

    return tables


def xml_table_element_dict(table, tags=None, as_list=False):
    """Converts XML Table Element to Python Dictionary
       table is element where element.tag=='table'
       if tags=None, return all tags. Else, return only Tags.
    """
    output = {}
    if as_list:
        output = []

    for row in table:
        row_num = int(row.get('rownum'))
        row_dict = {}

        for col in row:
            if (tags and (col.tag not in tags)) or col.tag == 'rowtext':
                continue
            row_dict[col.tag] = col.text

        if as_list:
            output.append(row_dict)
        else:
            output[row_num] = row_dict

    return output


def xml_to_tower_report(xml_file, output=None, comments=None):
    """

    Args:
        xml_file:
        output:
        comments: tuple of ints, comment numbers (2, 3, 6)

    Returns:

    """
    # Default output
    if comments and isinstance(comments, (float, int)):
        comments = [int(comments)]

    if not output:
        output = os.path.splitext(xml_file)[0] + '_XML_TOWER_REPORT.csv'
        output = output.upper()

    tree = et.parse(xml_file)
    root = tree.getroot()

    tables = {branch.get('tagname'): branch for branch in root if
              branch.tag == 'table' and int(branch.get('nrows'))}

    # Parse Necessary Tables
    if 'construction_staking_report' in tables:
        structure_dict = xml_table_element_dict(
            tables['construction_staking_report'], as_list=False)

        # Remove non C/L Hub entries
        to_remove = {i for i in structure_dict if
                     structure_dict[i]['stake_description'] != 'Structure Hub'}
        for i in to_remove:
            structure_dict.pop(i)

    else:
        if comments:
            arcpy.AddWarning('\n    - WARNING: Construction staking report '
                             'not available, cannot add comments')

        structure_dict = xml_table_element_dict(
            tables['structure_coordinates_report'],
            as_list=False)
        lat_lon_height_dict = xml_table_element_dict(
            tables['structure_longitude_latitude_and_height'],
            as_list=False)

        # Combine attributes from two tables
        for i in lat_lon_height_dict:
            if i in structure_dict:
                for k, v in lat_lon_height_dict[i].items():
                    structure_dict[i][k] = v

                structure_dict[i]['structure_comment_1'] = \
                    structure_dict[i]['structure_number']

    # Get dead end status
    try:
        section_xml_dict = xml_table_element_dict(
            tables['section_geometry_data'])
        dead_ends = {int(r['from_str']) for
                     _, r in section_xml_dict.items()}.union(
            {int(r['to_str']) for _, r in section_xml_dict.items()})
    except (KeyError, ValueError):
        arcpy.AddWarning('\n    - WARNING: Could not determine dead end '
                         'status, true structure numbers required')
        dead_ends = None

    # Build Report Dict to Write to CSV, Add Geotag and Rename Fields
    r_dict = {}
    for cnt, i in enumerate(sorted(structure_dict)):
        r_dict[cnt] = {}
        rec = structure_dict[i]

        r_dict[cnt]['QSI_TOWER'] = cnt + 1
        r_dict[cnt]['STRUCTURE'] = rec['structure_comment_1']

        # X and Y tags differ based on parsed tables
        r_dict[cnt]['X'] = float(rec.get('x_easting', rec.get('x', None)))
        r_dict[cnt]['Y'] = float(rec.get('y_northing', rec.get('y', None)))
        r_dict[cnt]['H'] = float(rec.get('structure_height_or_pole_length',
                                         rec.get('structure_height', None)))
        r_dict[cnt]['Z1'] = float(rec.get('z_elevation', rec.get('z', None)))
        r_dict[cnt]['Z2'] = round(r_dict[cnt]['Z1'] + r_dict[cnt]['H'], 2)
        r_dict[cnt]['LATITUDE'] = float(rec['latitude'])
        r_dict[cnt]['LONGITUDE'] = float(rec['longitude'])
        r_dict[cnt]['STR_GEOTAG'] = calc_geotag(lat=r_dict[cnt]['LATITUDE'],
                                                lon=r_dict[cnt]['LONGITUDE'])

        if dead_ends is not None:
            r_dict[cnt]['STR_TYPE'] = 'Dead End' if (cnt + 1) in dead_ends \
                else 'Tangent'
        else:
            r_dict[cnt]['STR_TYPE'] = 'Unknown'

        if comments:
            for i in comments:
                comment_field = 'COMMENT_{:02d}'.format(i)
                if comment_field not in TOWER_REPORT_FIELDS:
                    TOWER_REPORT_FIELDS.append(comment_field)

                r_dict[cnt][comment_field] = \
                    rec['structure_comment_{}'.format(int(i))]

    # Write Report, switched to pandas here because csv encoding was gross
    df = pd.DataFrame(columns=TOWER_REPORT_FIELDS)

    # Add rows to the DataFrame
    for k, v in sorted(r_dict.items()):
        row = {k: v for k, v in v.items()}
        df = df.append(row, ignore_index=True)

    # Save the DataFrame to a CSV file
    df.to_csv(output, index=False, quoting=1, quotechar='"', line_terminator='\n', encoding='utf-8')

    return output


def xml_to_spans(xml_file, out_spans, out_structures=None,
                 out_attachments=None, out_wires=None, sr=None):
    # Get xml tables
    xml_tables = get_xml_tables(xml_file)

    structure_xml_dict = xml_table_element_dict(
        xml_tables['construction_staking_report'])

    # Structure level information
    structure_dict = {}
    for i in structure_xml_dict:
        row = structure_xml_dict[i]
        if row['stake_description'] == 'Structure Hub':  # or 'C/L Hub'
            structure_number = int(row['structure_number'])
            x = float(row['x_easting'])
            y = float(row['y_northing'])
            z = float(row['z_elevation'])
            longitude = float(row['longitude'])
            latitude = float(row['latitude'])
            station = float(row['station'])
            offset = float(row['offset'])
            str_name = row['structure_comment_1']
            str_geotag = calc_geotag(latitude, longitude)

            if not str_name:
                arcpy.AddWarning('    - WARNING: {} missing '
                                 'structure_comment_1'.format(str_geotag))

            structure_dict[structure_number] = [int(structure_number),
                                                str_geotag,
                                                x, y, z, latitude, longitude,
                                                station, offset, str_name]

    # Section level information
    section_xml_dict = xml_table_element_dict(
        xml_tables['section_geometry_data'])

    section_dict = {}
    for i in section_xml_dict:
        row = section_xml_dict[i]
        sec_no = row['sec_no']
        sec_notes = row['sec_notes']
        from_str = row['from_str']  # for QC
        to_str = row['to_str']  # for QC
        number_of_phases = row['number_of_phases']  # for wire/phase values
        wires_per_phase = row['wires_per_phase']  # for wire/phase values
        cable_file = row['cable_file_name']

        section_dict[sec_no] = [sec_no, from_str, to_str, number_of_phases,
                                wires_per_phase, cable_file, sec_notes]

    # Attachments dict
    _dict = xml_table_element_dict(
        xml_tables['structure_attachment_coordinates'])

    attachment_dict = OrderedDict()
    for _, rec in _dict.items():
        k = '{}|{}|{}'.format(
            rec['struct_number'], rec['set_no'], rec['phase_no'])

        # Add length attribute
        i_xyz = np.array([float(rec['insulator_attach_point_{}'.format(c)])
                          for c in ('x', 'y', 'z')])
        w_xyz = np.array([float(rec['wire_attach_point_{}'.format(c)])
                          for c in ('x', 'y', 'z')])

        rec['length'] = np.linalg.norm(i_xyz - w_xyz)
        rec['STR_GEOTAG'] = structure_dict[int(rec['struct_number'])][1]

        attachment_dict[k] = rec

    # Stringing dict
    string_xml_dict = xml_table_element_dict(
        xml_tables['section_stringing_data'])

    string_dict = {}  # section_number: [structure_numbers]
    for i in range(len(string_xml_dict)):
        row = string_xml_dict[i]
        section_number = row['section_number']
        structure_number = row['struct_number']
        set_no = row['set_number']
        phasing = row['phasing']
        attach_key = '{}|{}|{}'.format(structure_number, set_no, set_no)

        if section_number not in string_dict:
            string_dict[section_number] = []

        string_dict[section_number].append(structure_number)

    if out_attachments:
        arcpy.CreateFeatureclass_management(os.path.dirname(out_attachments),
                                            os.path.basename(out_attachments),
                                            geometry_type='POINT',
                                            has_z='ENABLED')
        for field in ATTACHMENT_FIELDS:
            arcpy.AddField_management(out_attachments, field,
                                      ATTACHMENT_FIELD_TYPES.get(field,
                                                                 'TEXT'))

        i_fields = ['SHAPE@XYZ'] + ATTACHMENT_FIELDS
        with arcpy.da.InsertCursor(out_attachments, i_fields) as i_curs:
            for _, rec in attachment_dict.items():
                geom = [tuple([float(rec['wire_attach_point_{}'.format(c)])
                               for c in ('x', 'y', 'z')])]
                i_row = geom + \
                        [rec.get(ATTACHMENT_XML_FIELD_MAP.get(f, f), None) for
                         f in ATTACHMENT_FIELDS]
                i_curs.insertRow(i_row)

    # Building geometries: Spans
    temp_spans = os.path.join('in_memory', 'temp_spans')
    arcpy.CreateFeatureclass_management('in_memory', 'temp_spans', 'Polyline',
                                        spatial_reference=sr)

    for f in SPAN_FIELDS:
        if f != 'SHAPE@':
            arcpy.AddField_management(temp_spans, f, SPAN_FIELD_TYPES[f])

    with arcpy.da.InsertCursor(temp_spans, SPAN_FIELDS) as icurs:
        sn = 0
        span_tags = {}
        span_tags_multiphase = []

        for sect in sorted([int(i) for i in string_dict.keys()]):

            # List of structures in section
            structures = string_dict[str(sect)]

            # [sec_no, from_str, to_str, number_of_phases, wires_per_phase]
            section_info = section_dict[str(sect)]
            for i in range(len(structures) - 1):
                bst, ast = structures[i], structures[i + 1]

                bst, bst_tag, bst_x, bst_y, bst_z, bst_lat, bst_lon, \
                bst_station, bst_offset, bst_num = structure_dict[int(bst)]

                ast, ast_tag, ast_x, ast_y, ast_z, ast_lat, ast_lon, \
                ast_station, ast_offset, ast_num = structure_dict[int(ast)]

                # Span level attributes
                span_tag = '{}-{}'.format(bst_tag, ast_tag)
                span_name = '-'.format(bst_num, ast_num)
                wires_per_phase = int(section_info[4])
                phases = int(section_info[3])
                total_wires = wires_per_phase * phases
                cable_file = section_info[5]
                sec_notes = section_info[6]

                # Check for multi strung spans
                # TODO Change to use dict rather than indexing
                if span_tag not in span_tags:
                    sn += 1
                    span_tags[span_tag] = [phases, total_wires]
                    icurs.insertRow(
                        [sn, sect,
                         bst, bst_tag, bst_num,
                         bst_station, bst_offset,
                         ast, ast_tag, ast_num,
                         ast_station, ast_offset,
                         span_tag, span_name,
                         wires_per_phase, phases, total_wires,
                         cable_file, sec_notes] +
                        [arcpy.Polyline(
                            arcpy.Array([arcpy.Point(bst_x, bst_y),
                                         arcpy.Point(ast_x, ast_y)]))])

                # If a span contains multiple sections
                else:
                    span_tags[span_tag][0] += phases
                    span_tags[span_tag][1] += total_wires
                    span_tags_multiphase.append(span_tag)

    if span_tags_multiphase:
        with arcpy.da.UpdateCursor(
                temp_spans, ('SPAN_TAG', 'PHASES', 'WIRES_TOTAL')) as cursor:
            for row in cursor:
                row[1], row[2] = span_tags[row[0]]
                cursor.updateRow(row)

    arcpy.CopyFeatures_management(temp_spans, out_spans)

    arcpy.DefineProjection_management(out_spans, sr)

    return out_spans
