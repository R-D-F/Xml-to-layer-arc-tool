"""
Produce formatted layer for snow load quality control
"""

import arcpy
import os
import sys
import xml.etree.ElementTree as ET

if __name__ == "__main__" and __package__ is None:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)))))


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

def similarity_ratio(str1, str2):
    # Convert strings to sets of characters to find common characters
    set1 = set(str1)
    set2 = set(str2)
    
    # Calculate the intersection of characters
    common_chars = set1.intersection(set2)
    
    # Calculate similarity ratio
    similarity_ratio = len(common_chars) / (len(set1) + len(set2) - len(common_chars))
    
    return similarity_ratio

def pls_cadd_comparison_table(xml):
    input_feature_layer = arcpy.GetParameter(3)
    line_name = arcpy.GetParameter(4)
    standalone_table = arcpy.GetParameter(5)

    field = "LINE_NAME"
    where_clause = f"{arcpy.AddFieldDelimiters(input_feature_layer, field)} = '{line_name}'"
    arc_pro_list = []
    
    tree = ET.parse(xml)
    root = tree.getroot()

    section_sagging_data = root.findall('.//section_sagging_data')

    cable_file_name = root.findall('.//cable_file_name')
    from_str = root.findall('.//from_str')
    to_str = root.findall('.//to_str')

    pls_cadd_list = []
    for section in section_sagging_data:

        sec_no = section.findall('.//sec_no')
        cable_file_name = section.findall('.//cable_file_name')
        from_str = section.findall('.//from_str')
        to_str = section.findall('.//to_str')
        for sec in sec_no:
            temp_sec_no = sec.text
        for cable in cable_file_name:
            temp_cable = cable.text
        for str in to_str:
            temp_to_str = str.text
        for str in from_str:
            temp_from_str = str.text
        pls_cadd_list.append({
            "sec_no":temp_sec_no,
            "cable_file_name":temp_cable,
            "from_str":temp_from_str,
            "to_str":temp_to_str,
            "best_match":0
            
        })
    
    # Search cursor to find saps_func_location_number from input_feature_layer
    with arcpy.da.SearchCursor(input_feature_layer, "SAP_FUNC_L", where_clause) as cursor:
        for row in cursor:
            saps_func_location_number = row[0]
            

    # Check if saps_func_location_number was found
    if saps_func_location_number is not None:
        # Construct where_clause_2 using saps_func_location_number
        where_clause_2 = f"SAP_FUNC_LOC_NO = '{saps_func_location_number}'"
        
        # Search cursor to find related records in standalone_table
        with arcpy.da.SearchCursor(standalone_table, ["SAP_FUNC_LOC_NO", "CONDUCTOR_TYPE", "CONDUCTOR_SIZE", "CONDUCTOR_STRAND", "FROM_SAP_STRUCTURE_NO", "TO_SAP_STRUCTURE_NO"], where_clause_2) as cursor:
            for row in cursor:
                # Return all rows in standalone_table where SAP_FUNC_LOC_NO == saps_func_location_number
                arc_pro_list.append({
                    "SAP_FUNC_LOC_NO":f"{row[0]}",
                    "CONDUCTOR_TYPE":f"{row[1]}",
                    "CONDUCTOR_SIZE":f"{row[2]}",
                    "CONDUCTOR_STRAND":f"{row[3]}",
                    "FROM_SAP_STRUCTURE_NO":f"{row[4]}",
                    "TO_SAP_STRUCTURE_NO":f"{row[5]}",
                    })
    else:
        arcpy.AddMessage("No matching saps_func_location_number found.")

    for section_arc in arc_pro_list:
        for section_pls in pls_cadd_list:
            pass
            if similarity_ratio(section_pls["from_str"], section_arc["FROM_SAP_STRUCTURE_NO"]) > section_pls["best_match"]:
                arc_wire_type = f"{section_arc['CONDUCTOR_TYPE']} {section_arc['CONDUCTOR_SIZE']} {section_arc['CONDUCTOR_STRAND']}"
                section_pls.update({
                    "best_match": similarity_ratio(section_pls["from_str"], section_arc["FROM_SAP_STRUCTURE_NO"]),
                    "arc_wire_type": arc_wire_type,
                    "arc_from_str": section_arc["FROM_SAP_STRUCTURE_NO"],
                    "arc_to_str": section_arc["TO_SAP_STRUCTURE_NO"]
                })
                    
            

    for section_pls in pls_cadd_list:

        arc_from = section_pls["arc_from_str"]
        for section_pls_2 in pls_cadd_list:
            if section_pls_2["arc_from_str"] == arc_from and section_pls_2["best_match"] > section_pls["best_match"]:
                section_pls.update({"best_match":0, "arc_wire_type":"", "arc_from_str":"", "arc_to_str":""})
    return pls_cadd_list


def main():
    # Inputs
    xml_file = arcpy.GetParameterAsText(0)
    xml_sr = arcpy.GetParameter(1)
    dst_dir = arcpy.GetParameterAsText(2)
    xml_file_structure_comment_1 = arcpy.GetParameterAsText(6)



    # Output geodatabase
    dst_name = safe_name(
        os.path.basename(xml_file).replace('.xml', '')) + '_Shapes'
    dst_gdb = os.path.join(dst_dir, dst_name + '.gdb')
    dst_spans = os.path.join(dst_gdb, 'Spans')
    dst_structures = os.path.join(dst_gdb, 'Structures')
    dst_sections = os.path.join(dst_gdb, 'Sections')
    dst_report = os.path.join(dst_gdb, 'Tower_Report.csv')



    add_message('\n 1. Creating outputs\n')
    if not arcpy.Exists(dst_gdb):
        add_message('    - Processing geodatabase')
        arcpy.CreateFileGDB_management(os.path.dirname(dst_gdb),
                                       os.path.basename(dst_gdb))

    # Create spans and structure using xml
    add_message('    - Spans')
    add_message("testing")
    add_message(f"{xml_sr}")
    xml_to_spans(xml_file, dst_spans, dst_structures, sr=xml_sr)
    arcpy.DefineProjection_management(dst_spans, xml_sr)

    add_message('    - Structures')
    xml_to_tower_report(xml_file=xml_file, output=dst_report)
    tower_report_to_shape(dst_report, dst_structures)
    arcpy.DefineProjection_management(dst_structures, xml_sr)

    add_message('    - Sections')
    prep_for_qc(dst_spans, dst_sections)

    pls_cadd_list = pls_cadd_comparison_table(xml_file_structure_comment_1)

    unique_keys = list(pls_cadd_list[0].keys())
    unique_keys = unique_keys[1:]
    
    # removes "sec_no"
    
    unique_keys.insert(0, "BST_ID")
    add_message(str(unique_keys))
    for key in pls_cadd_list[0].keys():
        # Exclude the 'sec_no' key as it's not needed as a field
        if key != 'sec_no':
            arcpy.AddField_management(dst_spans, key, 'TEXT')
    
    with arcpy.da.UpdateCursor(dst_spans, unique_keys) as cursor:
        for row in cursor:
        # Get the value of the first field in the current row
            current_from_str = row[0]
            add_message(f"bst_id{current_from_str}")
            
            # Search for a matching dictionary in pls_cadd_list based on current_from_str
            matching_dict = next((item for item in pls_cadd_list if (item["from_str"]) == current_from_str), None)
            if matching_dict:
                add_message(f"Matching Dictionary: {matching_dict}")
            # If a matching dictionary is found, update the second field of the current row
            if matching_dict:
                row[1] = matching_dict["cable_file_name"]
                row[2] = matching_dict["from_str"]
                row[3] = matching_dict["to_str"]
                row[4] = matching_dict["best_match"]
                row[5] = matching_dict["arc_wire_type"]
                row[6] = matching_dict["arc_from_str"]
                row[7] = matching_dict["arc_to_str"]


    # #need to get the plscadd list into the span attributes table
    # with arcpy.da.UpdateCursor(dst_spans, unique_keys) as cursor:
    #     for row in cursor:
    #         for item in pls_cadd_list:
    #             add_message(f"bst_id{str(row[0])}")
    #             add_message(f"plscadd{str(item["from_str"])}")
    #             if row[0] == item["from_str"]:
    #                 row[1] = item["cable_file_name"]


                cursor.updateRow(row)

if __name__ == '__main__':
    main()
