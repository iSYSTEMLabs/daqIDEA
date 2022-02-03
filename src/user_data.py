
import os
import xml.etree.ElementTree as ET

class CUserData:
    XML_ROOT = 'user'
    XML_VERSION = 'winIDEA_verison'
    XML_CONFIGS = 'previous_configs'
    XML_CONFIG = 'config'
    XML_CONFIG_PATH = 'path'

    def __init__(self):
        self.reset()

    def reset(self):
        self.strwinIDEAVersion = '9.21.44' # At the moment of writing this
        self.vstrPreviousWorkspacePaths = []

    def loadUserData(self, strFilePath):
        self.reset()
        if not os.path.exists(strFilePath):
            return

        nodeUser = ET.parse(strFilePath).getroot()

        # winIDEA version at writing this file
        nodeVersion = nodeUser.find(self.XML_VERSION)
        if None != nodeVersion:
            self.strwinIDEAVersion = nodeVersion.text

        # Previously opened daqIDEA config files sorted in MRU
        for nodeConfigs in nodeUser.findall(self.XML_CONFIGS):
            for nodeConfig in nodeConfigs.findall(self.XML_CONFIG):
                nodeConfigPath = nodeConfig.find(self.XML_CONFIG_PATH)
                if None != nodeConfigPath:
                    strConfigPath = nodeConfigPath.text
                    if None != strConfigPath and os.path.exists(strConfigPath):
                        self.vstrPreviousWorkspacePaths.append(strConfigPath)
