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

#TODO:
# ✓ Create structures layer with only dead end towers from XML
# ✓ Create sections layer with from, to, wiretype.

# ✓ Create arc estimate structures layer with "dead end" towers
#Create arc estimate sections layer with from, to, wiretype

UNIQUE_RGB_VALUES = [
    [255, 0, 0],    # Red
    [0, 255, 0],    # Green
    [0, 0, 255],    # Blue
    [255, 255, 0],  # Yellow
    [255, 0, 255],  # Magenta
    [0, 255, 255],  # Cyan
    [128, 0, 0],    # Maroon
    [0, 128, 0],    # Dark Green
    [0, 0, 128],    # Navy
    [128, 128, 0],  # Olive
    [128, 0, 128],  # Purple
    [0, 128, 128],  # Teal
    [192, 192, 192],# Silver
    [128, 128, 128] # Gray
]

FIELD_SECTION = 'SECTION'
FIELD_SNOWLOAD = 'SNOWLOAD'
FIELD_CABLE = 'CABLE_FILE'
EXT_WIRE = '.wir'
FIELD_TO = 'TO_STR'
FIELD_FROM = 'FROM_STR'


def prep_for_qc(spans, sections):
    """
    Dissolves input layer by CABLE_FILE attribute, then adds
    a SNOWLOAD attribute based on cable file name. All results are in-memory and
    will be overwritten on subsequent runs and be lost when a map is closed.

    Args:
        lyr: layer from active map
        sym: optional symbology file to apply to output
    """
    #todo:
    # add back in "to" and "from" to sections feature class
    spans_feature_list = ["SECTION", "BST_ID", "AST_ID"]
    section_number = 1
    dead_end_from_list = []
    dead_end_to_list = []
    last_value = None
    sections_list = []

    arcpy.Dissolve_management(spans, sections, [FIELD_SECTION, FIELD_CABLE])
    arcpy.AddField_management(sections, FIELD_SNOWLOAD, 'TEXT')
    # Add from and to fields to sections
    arcpy.AddField_management(sections, FIELD_FROM, 'TEXT')
    arcpy.AddField_management(sections, FIELD_TO, 'TEXT')
    with arcpy.da.UpdateCursor(sections,
                               (FIELD_CABLE, FIELD_SNOWLOAD)) as cursor:
        for row in cursor:
            row[1] = row[0].split('-')[-1].replace(EXT_WIRE, '')
            cursor.updateRow(row)
    # Populate lis of "from" structures from the spans list
    with arcpy.da.SearchCursor(spans, spans_feature_list) as cursor:
        for row in cursor:
            if row[0] == section_number:
                dead_end_from_list.append(row[1])
                section_number += 1
    # Populate list of "to" Structures from the spans list (do it backwards because I need to find the last instance of the from stuctre per section)
    with arcpy.da.SearchCursor(spans, ["SECTION","AST_ID"], sql_clause=(None, "ORDER BY OBJECTID DESC")) as cursor:
        for row in cursor:
            if row[0] not in sections_list:
                dead_end_to_list.append(row[1])
                sections_list.append(row[0])

    # Add from list to sections feature
    de_list_from_counter = 0
    with arcpy.da.UpdateCursor(sections, FIELD_FROM) as cursor:
        for row in cursor:
            row[0] = dead_end_from_list[de_list_from_counter]
            de_list_from_counter += 1
            cursor.updateRow(row)
    # Add to list (reversed) to sections
    de_list_to_counter = 0
    dead_end_to_list.reverse()
    with arcpy.da.UpdateCursor(sections, FIELD_TO) as cursor:
        for row in cursor:
            row[0] = dead_end_to_list[de_list_to_counter]
            de_list_to_counter += 1
            cursor.updateRow(row)

def apply_unique_symbology_to_sections_layer(dst_gdb):
    '''This currently does not work.'''
    relpath = os.path.dirname(sys.argv[0])

    # This needs to be made universal
    p = arcpy.mp.ArcGISProject(relpath + r'\MyProject\MyProject.aprx')
    ##
    add_message(p)
    m = p.listMaps('Map')[0]
    l = m.listLayers('Sections*')[0]
    sym = l.symbology

    sym.updateRenderer('UniqueValueRenderer')
    sym.renderer.fields = ['CABLE_FILE']
    counter = 0
    for grp in sym.renderer.groups:
        for itm in grp.items:
            itm.symbol.color = {'RGB': [UNIQUE_RGB_VALUES[counter], 100]}
        counter += 1
            
    l.symbology = sym

    output_layer_path = os.path.join(dst_gdb + 'sections_unique')
    arcpy.management.SaveToLayerFile(l, output_layer_path)
    # https://pro.arcgis.com/en/pro-app/latest/arcpy/mapping/uniquevaluerenderer-class.htm
    # the example here saves the ouput as a new project which is not what I want. not sure how to just save as layer

    

def similarity_ratio(str1, str2):
    def string_sim():
        set1 = set(str1)
        set2 = set(str2)
        common_chars = set1.intersection(set2)
        if len(set1) == 0 and len(set2) == 0:
            return 0
        else:
            similarity_ratio = len(common_chars) / (len(set1) + len(set2) - len(common_chars))
            
            return similarity_ratio
    if str1 == str2:
        return 1.4
    elif str1 in str2 or str2 in str1:
        return 1.3
    elif "/" in str1 and "/" in str2:
        
        if str1.split("/")[1] == str2.split("/")[1]:
            
            return 1.2
        elif str1.split("/")[1] in str2.split("/")[1] or str2.split("/")[1] in str1.split("/")[1]:
            
            return 1.1
        else:
            return string_sim()
    else:    
        return string_sim()
            
def get_arc_pro_list():
    '''This function takes the OH-conductor info table (standalone table), and returns a list of dictionaries with 
    "SAP_FUNC_LOC_NO",
    "CONDUCTOR_TYPE",
    "CONDUCTOR_SIZE",
    "CONDUCTOR_STRAND",
    "FROM_SAP_STRUCTURE_NO",
    "TO_SAP_STRUCTURE_NO",
    and 
    "BEST_MATCH_QSI_TOWER",
    "BEST_MATCH_PERCENT",
    as 0 so they can be replaced later'''

    arcpy.AddMessage(f"getting arc pro list")
    input_feature_layer = arcpy.GetParameter(3)
    line_name = arcpy.GetParameter(4)
    standalone_table = arcpy.GetParameter(5)

    field = "LINE_NAME"
    where_clause = f"{arcpy.AddFieldDelimiters(input_feature_layer, field)} = '{line_name}'"
    arc_pro_list = []
    # Search cursor to find saps_func_location_number from input_feature_layer
    with arcpy.da.SearchCursor(input_feature_layer, "SAP_FUNC_L", where_clause) as cursor:
        for row in cursor:
            saps_func_location_number = row[0]

    # Check if saps_func_location_number was found
    if saps_func_location_number is not None:
        arcpy.AddMessage(f"{saps_func_location_number}")
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
                    "BEST_MATCH_QSI_TOWER":0,
                    "BEST_MATCH_PERCENT":0,
                    })
    else:
        arcpy.AddMessage("No matching saps_func_location_number found.")
    
    # changing CU to copper for fuzzy finder
    for item in arc_pro_list:
        if item["CONDUCTOR_TYPE"] == "CU":
            item["CONDUCTOR_TYPE"] = "copper"
    
    return arc_pro_list


def create_structures_feature_from_OH_conductor(structures, gdb, arc_pro_list):  
    '''takes in the current structures feature class, copies it, then looks at where the structure numbers match with the OH conductor infor and applies the OH conductor info to the coppied feature.
    It then deletes any structure that does not match with an item in OH conductor table.''' 
    structures_arc_pro_list = arc_pro_list
    
    arc_structures = os.path.join(gdb, 'arc_structres')
    arcpy.CopyFeatures_management(structures, arc_structures) 
    arcpy.AddField_management(arc_structures, 'ARC_FROM_STRUCTURE', 'TEXT')
    arcpy.AddField_management(arc_structures, 'ARC_TO_STRUCTURE', 'TEXT')
    arcpy.AddField_management(arc_structures, 'BEST_MATCH', 'DOUBLE')
    arcpy.AddField_management(arc_structures, 'WIRE', 'TEXT')


    
    with arcpy.da.UpdateCursor(arc_structures, 'BEST_MATCH') as cursor:
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)

    arc_structures_list_of_features = ['STRUCTURE', 'ARC_FROM_STRUCTURE','ARC_TO_STRUCTURE','BEST_MATCH', 'WIRE','QSI_TOWER']
    
    for section_arc in structures_arc_pro_list:
        with arcpy.da.SearchCursor(arc_structures, ['STRUCTURE','QSI_TOWER']) as cursor:
            for row in cursor:
                
                if float(similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])) > section_arc['BEST_MATCH_PERCENT']:
                    section_arc['BEST_MATCH_PERCENT'] = similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])
                    section_arc['BEST_MATCH_QSI_TOWER'] = row[1]
    for section_arc in structures_arc_pro_list:
        sql_query = f"QSI_TOWER = {section_arc['BEST_MATCH_QSI_TOWER']}"
        with arcpy.da.UpdateCursor(arc_structures, arc_structures_list_of_features, sql_query) as cursor:
            for row in cursor:
                row[1] = section_arc['FROM_SAP_STRUCTURE_NO']
                row[2] = section_arc['TO_SAP_STRUCTURE_NO']
                row[3] = similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])
                row[4] = f"{section_arc['CONDUCTOR_TYPE']} {section_arc['CONDUCTOR_SIZE']}{section_arc['CONDUCTOR_STRAND']}"
                cursor.updateRow(row)

    with arcpy.da.UpdateCursor(arc_structures, ['ARC_FROM_STRUCTURE']) as cursor:
        for row in cursor:
            if row[0] == None:
                cursor.deleteRow()

def create_sections_feature_from_OH_conductor(sections, gdb, arc_pro_list, sr):  
    '''takes in the current structures feature class, copies it, then looks at where the structure numbers match with the OH conductor infor and applies the OH conductor info to the coppied feature.
    It then deletes any structure that does not match with an item in OH conductor table.''' 
    sections_arc_pro_list = arc_pro_list
    arc_sections = os.path.join(gdb, 'arc_sections')
    arcpy.CopyFeatures_management(sections, arc_sections)
    arcpy.AddField_management(arc_sections, 'ARC_FROM_STRUCTURE', 'TEXT')
    arcpy.AddField_management(arc_sections, 'ARC_TO_STRUCTURE', 'TEXT')
    arcpy.AddField_management(arc_sections, 'BEST_MATCH', 'DOUBLE')
    arcpy.AddField_management(arc_sections, 'WIRE', 'TEXT') 
    
    
    
    with arcpy.da.UpdateCursor(arc_sections, ['BEST_MATCH']) as cursor:
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
    

    

    arc_sections_list_of_features = ['BST_ID', 'ARC_FROM_STRUCTURE','ARC_TO_STRUCTURE','BEST_MATCH', 'WIRE']
    # selelects the row if sections that has the closet match between from saps struc tand bst_id
    #puts that into best match qsi tower
    for section_arc in sections_arc_pro_list:
        with arcpy.da.SearchCursor(sections, ['BST_ID','OID@']) as cursor:
            for row in cursor:
  
                if float(similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])) > section_arc['BEST_MATCH_PERCENT']:
                    section_arc['BEST_MATCH_PERCENT'] = similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])
                    section_arc['BEST_MATCH_QSI_TOWER'] = row[1]
   
    for section_arc in sections_arc_pro_list:
        sql_query = f"SN = {section_arc['BEST_MATCH_QSI_TOWER']}"
        with arcpy.da.UpdateCursor(arc_sections, arc_sections_list_of_features, sql_query) as cursor:
            for row in cursor:
                row[1] = section_arc['FROM_SAP_STRUCTURE_NO']
                row[2] = section_arc['TO_SAP_STRUCTURE_NO']
                row[3] = similarity_ratio(row[0], section_arc['FROM_SAP_STRUCTURE_NO'])
                row[4] = f"{section_arc['CONDUCTOR_TYPE']} {section_arc['CONDUCTOR_SIZE']}{section_arc['CONDUCTOR_STRAND']}"
                cursor.updateRow(row)
####
    with arcpy.da.UpdateCursor(arc_sections, ['ARC_FROM_STRUCTURE']) as cursor:
        for row in cursor:
            if row[0] == None:
                cursor.deleteRow()
    
    #makes a list of the first point coordinates for each poly line
    vertices_to_keep = []
    with arcpy.da.SearchCursor(arc_sections, ["SHAPE@"]) as cursor:
        for row in cursor:
            polyline = row[0] 
            for part in polyline:
                if len(part) >= 2: 
                    first_point = (part[0].X, part[0].Y)
                    last_point = (part[-1].X, part[-1].Y)  
                    vertices_to_keep.append((first_point, last_point))
    with arcpy.da.UpdateCursor(arc_sections, ["OID@", "SHAPE@"]) as cursor:
        row_count = 0
        for oid, row in cursor:
            if row_count < len(vertices_to_keep) - 1:  # Ensure we have a next row to connect to
                current_line_vertices = vertices_to_keep[row_count]
                next_line_vertices = vertices_to_keep[row_count + 1]
                array = arcpy.Array([arcpy.Point(*point) for point in current_line_vertices])
                next_point = arcpy.Point(*next_line_vertices[0])  
                array.add(next_point)  
                polyline = arcpy.Polyline(array, sr)
                
                # Update the geometry of the current row
                cursor.updateRow([oid, polyline])
                
                row_count += 1



def main():
    # Inputs
    xml_file = arcpy.GetParameterAsText(0)
    xml_sr = arcpy.GetParameter(1)
    dst_dir = arcpy.GetParameterAsText(2)
    

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
    add_message(f"{xml_sr}")
    xml_to_spans(xml_file, dst_spans, dst_structures, sr=xml_sr)
    arcpy.DefineProjection_management(dst_spans, xml_sr)

    add_message('    - Structures')
    xml_to_tower_report(xml_file=xml_file, output=dst_report)
    tower_report_to_shape(dst_report, dst_structures)
    arcpy.DefineProjection_management(dst_structures, xml_sr)

    add_message('    - Sections')
    prep_for_qc(dst_spans, dst_sections)

    # make copy of structures where there are only dead ends
    structures_de = os.path.join(dst_gdb, 'Structures_DE')
    arcpy.CopyFeatures_management(dst_structures, structures_de)

    with arcpy.da.UpdateCursor(structures_de, ["STR_TYPE"]) as cursor:
        for row in cursor:
            if row[0] != "Dead End":
                cursor.deleteRow()

    #apply_unique_symbology_to_sections_layer(dst_gdb)
    
    create_structures_feature_from_OH_conductor(dst_structures, dst_gdb, get_arc_pro_list())
    create_sections_feature_from_OH_conductor(dst_spans, dst_gdb, get_arc_pro_list(), sr=xml_sr )


    


if __name__ == '__main__':
    main()
