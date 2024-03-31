import arcpy


def add_message(msg):
    arcpy.AddMessage(msg)
    print(msg)


def add_warning(msg):
    arcpy.AddWarning(msg)
    print(msg)


def add_error(msg):
    arcpy.AddError(msg)
    print(msg)

