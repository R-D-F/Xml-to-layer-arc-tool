"""
Produce formatted layer for snow load quality control
"""

import arcpy
import os
import sys

# if __name__ == "__main__" and __package__ is None:
#     sys.path.append(
#         os.path.dirname(
#             os.path.dirname(
#                 os.path.dirname(
#                     os.path.abspath(__file__)))))


from utils.messages import add_message, add_warning
from utils.misc import safe_name
from utils.plscadd_xml import xml_to_spans, xml_to_tower_report
from modeling.xml_to_tower_report import tower_report_to_shape

arcpy.env.overwriteOutput = True

FIELD_SECTION = 'SECTION'
FIELD_SNOWLOAD = 'SNOWLOAD'
FIELD_CABLE = 'CABLE_FILE'
EXT_WIRE = '.wir'


def prep_for_qc(spans, sections):
    """

    Dissolves input layer by CABLE_FILE attribute, then adds
    a SNOWLOAD attribute based on cable file name. All results are in-memory and
    will be overwritten on subsequent runs and be lost when a map is closed.

    Args:
        lyr: layer from active map
        sym: optional symbology file to apply to output

    """
    arcpy.Dissolve_management(spans, sections, [FIELD_SECTION, FIELD_CABLE])
    arcpy.AddField_management(sections, FIELD_SNOWLOAD, 'TEXT')
    with arcpy.da.UpdateCursor(sections,
                               (FIELD_CABLE, FIELD_SNOWLOAD)) as cursor:
        for row in cursor:
            row[1] = row[0].split('-')[-1].replace(EXT_WIRE, '')
            cursor.updateRow(row)



def main():
    # Inputs
    xml_file = arcpy.GetParameterAsText(0)
    xml_sr = arcpy.GetParameter(1)
    dst_dir = arcpy.GetParameterAsText(2)
    sym_sec = arcpy.GetParameterAsText(3)
    sym_str = arcpy.GetParameterAsText(4)

    # Output geodatabase
    dst_name = safe_name(
        os.path.basename(xml_file).replace('.xml', '')) + '_Snowload'
    dst_gdb = os.path.join(dst_dir, dst_name + '.gdb')
    dst_spans = os.path.join(dst_gdb, 'Spans')
    dst_structures = os.path.join(dst_gdb, 'Structures')
    dst_sections = os.path.join(dst_gdb, 'Sections')
    dst_report = os.path.join(dst_gdb, 'Tower_Report.csv')

    dst_str_lyr = os.path.join(dst_dir, dst_name + '_Structures.lyr')
    dst_sec_lyr = os.path.join(dst_dir, dst_name + '_Sections.lyr')

    add_message('\n 1. Creating outputs\n')
    if not arcpy.Exists(dst_gdb):
        add_message('    - Processing geodatabase')
        arcpy.CreateFileGDB_management(os.path.dirname(dst_gdb),
                                       os.path.basename(dst_gdb))

    # Create spans and structure using xml
    add_message('    - Spans')
    xml_to_spans(xml_file, dst_spans, dst_structures)
    arcpy.DefineProjection_management(dst_spans, xml_sr)

    add_message('    - Structures')
    xml_to_tower_report(xml_file=xml_file, output=dst_report)
    tower_report_to_shape(dst_report, dst_structures)
    arcpy.DefineProjection_management(dst_structures, xml_sr)

    add_message('    - Sections')
    prep_for_qc(dst_spans, dst_sections)

    # Format layers
    add_message('\n 2. Formatting for Map')
    mxd = arcpy.mapping.MapDocument('CURRENT')
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    arcpy.RefreshActiveView()
    arcpy.RefreshTOC()

    add_message('\n    - Sections')
    lyr_sec = arcpy.mapping.Layer(dst_sections)
    arcpy.ApplySymbologyFromLayer_management(lyr_sec, sym_sec)
    lyr_sec.showLabels = True
    if lyr_sec.supports('LABELCLASSES'):
        for label in lyr_sec.labelClasses:
            label.expression = "[{}]".format('SNOWLOAD')

    # Structure layer, filtered to dead ends
    add_message('    - Dead-end Structures')
    lyr_str = arcpy.mapping.Layer(dst_structures)
    arcpy.ApplySymbologyFromLayer_management(lyr_str, sym_str)
    lyr_str.definitionQuery = "STR_TYPE = 'Dead End'"

    arcpy.mapping.AddLayer(df, lyr_str, 'BOTTOM')
    arcpy.mapping.AddLayer(df, lyr_sec, 'TOP')

    # Save and export kmz
    arcpy.RefreshActiveView()
    arcpy.RefreshTOC()

    # Save layer files
    add_message('\n 2. Saving layer files')
    add_message('\n    - Structures')
    arcpy.SaveToLayerFile_management(lyr_str, dst_str_lyr)
    add_message('    - Sections')
    arcpy.SaveToLayerFile_management(lyr_sec, dst_sec_lyr)


if __name__ == '__main__':
    main()
