import xml.etree.ElementTree as et
import pprint
import json

xml = "ref/ignacio_mare_island_2_115kv_true.xml"
tree = et.parse(xml)
root = tree.getroot()

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



def get_xml_tables(xml_file):
    tree = et.parse(xml_file)
    root = tree.getroot()
    tables = {branch.get('tagname'): branch for branch in root
              if branch.tag == 'table' and int(branch.get('nrows'))}
    return tables



tables = {branch.get('tagname'): branch for branch in root if
            branch.tag == 'table' and int(branch.get('nrows'))}
structure_dict = xml_table_element_dict(
            tables['construction_staking_report'],
            as_list=False)
to_remove = {i for i in structure_dict if
                structure_dict[i]['stake_description'] != 'Structure Hub'}
for i in to_remove:
    structure_dict.pop(i)

r_dict = {}
for cnt, i in enumerate(sorted(structure_dict)):
    r_dict[cnt] = {}
    rec = structure_dict[i]
    print(rec['structure_comment_1'])
# print(json.dumps(structure_dict, indent=4))
