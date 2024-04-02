import xml.etree.ElementTree as et
import pprint

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
            tables['structure_coordinates_report'],
            as_list=False)


print(structure_dict)

print("\n".join("{}\t{}".format(k, v) for k, v in structure_dict.items()))