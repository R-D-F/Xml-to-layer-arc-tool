"""
Purpose: Create QSI Tower Report and Features using PLS-CADD XML
"""

import arcpy
import csv
import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__))))

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__" and __package__ is None:
    sys.path.append(root)
from reload_modules import reload_modules
reload_modules(root)


from utils.messages import add_message, add_warning, add_error
from utils.plscadd_xml import (xml_to_tower_report, xml_to_spans,
                               TOWER_REPORT_FIELDS, TOWER_REPORT_FIELD_TYPES)
from utils.settings import Settings


def tower_report_to_shape(tower_report_csv, out_shp=None, out_sr=None):
    """Creates a shapefile from csv of tower report"""

    if not out_shp:
        out_shp = os.path.splitext(tower_report_csv)[0] + '.shp'

    arcpy.CreateFeatureclass_management(out_path=os.path.dirname(out_shp),
                                        out_name=os.path.basename(out_shp),
                                        geometry_type='POINT')
    if out_sr:
        arcpy.DefineProjection_management(out_shp, out_sr)

    # Add fields to output shapefile
    for field in TOWER_REPORT_FIELDS:
        arcpy.AddField_management(out_shp, field,
                                  TOWER_REPORT_FIELD_TYPES.get(field, 'TEXT'))

    with arcpy.da.InsertCursor(
            out_shp, TOWER_REPORT_FIELDS + ['SHAPE@X', 'SHAPE@Y']) as icurs:
        with open(tower_report_csv, 'r') as rf:
            csv_r = csv.DictReader(rf)
            for cnt, row in enumerate(csv_r):
                irow = [row[f] for f in TOWER_REPORT_FIELDS] + \
                       [float(row['X']), float(row['Y'])]
                icurs.insertRow(irow)

    return out_shp


def tower_report_to_span_shp(tower_report_shp, spans, sr=None):
    """Draw spans using tower report, assumes spans follow tower order"""
    # Create span feature, assuming structure order
    arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(spans),
        out_name=os.path.basename(spans),
        geometry_type='POLYLINE',
        spatial_reference=sr)

    arcpy.DefineProjection_management(spans, sr)

    # Add required fields
    span_fields = ['SN', 'BST', 'BST_TAG', 'BST_ID', 'AST', 'AST_TAG',
                   'AST_ID', 'SPAN_TAG', 'SPAN_NAME']

    span_field_types = {'SN': 'LONG', 'BST': 'LONG', 'BST_TAG': 'TEXT',
                        'BST_ID': 'TEXT', 'AST': 'LONG', 'AST_TAG': 'TEXT',
                        'AST_ID': 'TEXT', 'SPAN_TAG': 'TEXT',
                        'SPAN_NAME': 'TEXT'}

    for field in span_fields:
        if field != 'SHAPE@':
            arcpy.AddField_management(spans, field, span_field_types[field])

    # Draw spans but connecting structures in order
    s_fields = TOWER_REPORT_FIELDS + ['SHAPE@']
    i_fields = span_fields + ['SHAPE@']
    with arcpy.da.InsertCursor(spans, i_fields) as icurs:

        # Initialize 'from attributes'
        from_geotag, from_structure, from_qsi = None, None, None
        from_geom = None

        for cnt, row in enumerate(
                arcpy.da.SearchCursor(tower_report_shp, s_fields)):

            # Assign 'to' attributes
            to_geotag = row[s_fields.index('STR_GEOTAG')]
            to_structure = row[s_fields.index('STRUCTURE')]
            to_qsi = row[s_fields.index('QSI_TOWER')]
            to_geom = row[s_fields.index('SHAPE@')].firstPoint

            if cnt > 0:
                # Draw spans assuming order better insert handling
                span_cnt = cnt
                span_tag = '{}-{}'.format(from_geotag, to_geotag)
                span_name = '{}-{}'.format(from_structure, to_structure)
                geom = arcpy.Polyline(arcpy.Array([from_geom, to_geom]))

                # TODO handle better
                irow = [span_cnt, from_qsi, from_geotag, from_structure,
                        to_qsi, to_geotag, to_structure, span_tag, span_name,
                        geom]

                icurs.insertRow(irow)

            # Update 'from' attributes for next span
            from_geotag = to_geotag
            from_structure = to_structure
            from_qsi = to_qsi
            from_geom = to_geom

    return spans



def main():
    # Inputs
    xml_files = arcpy.GetParameterAsText(0).split(';')
    dst_dir = arcpy.GetParameterAsText(1)
    export_shapes = arcpy.GetParameter(2)
    keep_comments = arcpy.GetParameter(3)
    spatial_reference = arcpy.GetParameterAsText(4)

    # Convert xml files to tower reports
    add_message('\n 1. Processing {} input xml files'.format(
        len(xml_files)))

    arcpy.SetProgressor('step', 'Processing xmls...', 0, len(xml_files), 1)
    for cnt, xml_file in enumerate(sorted(xml_files)):
        arcpy.SetProgressorPosition(cnt + 1)
        add_message('\n    - {}'.format(os.path.basename(xml_file)))

        # Determine output file path
        dst = None
        if dst_dir:
            dst = os.path.join(dst_dir, os.path.splitext(
                os.path.basename(xml_file))[0] +
                               '_XML_TOWER_REPORT.csv').upper()

        try:
            tower_report = xml_to_tower_report(xml_file, dst, comments=keep_comments)


            if export_shapes:
                tower_report_shp = os.path.splitext(tower_report)[0] + '.shp'
                span_shp = os.path.splitext(tower_report)[0] + '_SPANS.shp'

                tower_report_to_shape(tower_report, out_sr=spatial_reference)

                try:
                    xml_to_spans(xml_file, span_shp, sr=spatial_reference)
                except ValueError:
                    add_warning('    - WARNING: Attempting to create spans '
                                'assuming structure order is followed exactly, '
                                'qc closely')
                    tower_report_to_span_shp(tower_report_shp, span_shp, sr=spatial_reference)

        except Exception as e:
            add_error('\n      - ERROR: Could not process, {}'.format(e))

    return len(xml_files)


if __name__ == '__main__':
    log = main()
    log.report['Size'] = log.ret
    log.submit_log()
