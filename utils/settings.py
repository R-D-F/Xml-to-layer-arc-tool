"""
Script:  Default settings for vegetation management processes
Purpose: Maintain default values in a single file
Author:  Conrad Hilley <chilley@quantumspatial.com>
Notes: Built config and ProcessingGDB class based on class by Greg Berardinelli
"""

import collections
# moduel name changed to configparser for python 3 from ConfigParser in 2
from configparser import ConfigParser


class DictObj(object):
    """Object created from dictionary"""

    def __init__(self, d):
        # Convert parsed dict to attributes
        for k, v in d.items():
            if isinstance(v, (list, tuple)):
                setattr(self, k, [DictObj(i) if isinstance(i, dict)
                                  else i for i in v])
            else:
                setattr(self, k, DictObj(v) if isinstance(v, dict) else v)


class ConfigFile(object):
    """ConfigFile file class with access via attributes and dict"""

    def __init__(self, config_file, sections=()):

        # Parse config file
        self.config_dict = self.get_config_dict(config_file, sections=sections)
        self.sections = self.config_dict.keys()

        # Convert parsed dict to attributes
        for k, v in self.config_dict.items():
            if isinstance(v, (list, tuple)):
                setattr(self, k, [DictObj(i) if isinstance(i, dict)
                                  else i for i in v])
            else:
                setattr(self, k, DictObj(v) if isinstance(v, dict) else v)

    @staticmethod
    def get_config_dict(config_file, sections=()):

        # Create a parser
        parser = ConfigParser()
        parser.optionxform = str  # Retain casing

        # Read config file
        parser.read(config_file)

        # Return all sections if none specified
        if not sections:
            sections = [sec for sec in parser.sections()]

        # Build dict and verify specified sections
        config_dict = {}
        for sec in sections:
            if sec not in parser.sections():
                raise Exception(
                    '{} not found in {}'.format(sec, config_file))

            config_dict[sec] = {p[0]: p[1] for p in parser.items(sec)}

        return config_dict


class Settings(object):
    # Kibana logging
    # 2.0 is first release in ArcPro, last ArcMap was 1.2.18
    app_version = '2.2.0'

    log_host = "10.8.16.32"
    log_port = 5009  # Portland  (5012  # Testing)

    # Fields
    FIELD_CLIENT = 'CLIENT'
    FIELD_FEEDERID = 'FEEDERID'
    FIELD_PROC_GROUP = 'PROC_GROUP'
    FIELD_LINE_ID = 'LINE_ID'
    FIELD_LINE_NBR = 'LINE_NBR'
    FIELD_LINE_NAME = 'LINE_NAME'
    FIELD_MILES = 'MILES'
    FIELD_SR_NAME = 'SR_NAME'
    FIELD_SR_CODE = 'SR_CODE'
    FIELD_VOLTAGE = 'VOLTAGE'
    FIELD_STR_GEOTAG = 'STR_GEOTAG'
    FIELD_STR_NUM = 'STR_NUM'
    FIELD_SPAN_ID = 'SPAN_ID'
    FIELD_SPAN_NAME = 'SPAN_NAME'
    FIELD_SPAN_TAG = 'SPAN_TAG'
    FIELD_BST_ID = 'BST_ID'
    FIELD_AST_ID = 'AST_ID'
    FIELD_BST_TAG = 'BST_TAG'
    FIELD_AST_TAG = 'AST_TAG'
    FIELD_LATITUDE = 'LATITUDE'
    FIELD_LONGITUDE = 'LONGITUDE'
    FIELD_LAYER = 'LAYER'
    FIELD_SPAN_LGTH = 'SPAN_LGTH'

    FIELD_TYPES = {FIELD_LATITUDE: 'DOUBLE',
                   FIELD_LONGITUDE: 'DOUBLE',
                   FIELD_MILES: 'DOUBLE',
                   FIELD_VOLTAGE: 'LONG'}

    # Update with ConfigFile
    def update_defaults(self, config_file=None):
        if config_file is None:
            return

        cfg = ConfigFile(config_file)
        for section in cfg.config_dict:
            for k, v in cfg.config_dict[section].items():
                if hasattr(self, k):
                    # Ensure type is consistent
                    setattr(self, k,
                            match_type(v, getattr(self, k)))
                else:
                    setattr(self, k, v)


def match_type(s, _type=str):
    # if a 'type' is not input, copy type of input
    if type(_type) != type(str):
        _type = type(_type)

    try:
        return _type(s)
    except:
        raise (TypeError('Could not convert {} to {} type'.format(s, _type)))


def invert_dict(_dict):
    hashable = collections.Hashable
    return {v: k for k, v in _dict.items() if isinstance(v, hashable)}
