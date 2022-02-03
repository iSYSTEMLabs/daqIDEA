
from __future__ import print_function

import time, random
import imp, sys
import os, properties

import logging

#
# Just global variables
#

mainApplicationWindow = None

TIME_INTERVAL_DEFAULT = 5
TIME_INTERVAL_MIN = 1

MAX_DOTS_PER_PLOT = 1000.0
CHART_PLOT_UPDATE_INTERVAL_MS = 20

TABLE_COLUMN_ENABLED = 0
TABLE_COLUMN_INTERVAL = 1
TABLE_COLUMN_NAME = 2
TABLE_COLUMN_CHART = 3
TABLE_COLUMN_SCALE = 4
TABLE_COLUMN_FORMAT = 5
TABLE_COLUMN_COLOR = 6
TABLE_COLUMN_DELETE = 7
TABLE_COLUMN_COUNT = 8

samplingIntervalRaw = None #['1', '0.1', '0.01', '0.001', '0']
samplingIntervalNames = None #['1 s', '100 ms', '10 ms', '1 ms', 'MAX'] 
samplingIntervalValues = None #[None] * len(samplingIntervalNames)

defaultPlotColors = [ (255,   0,   0), 
                      (  0, 170,   0),
                      (  0,   0, 255),
                      (  0, 170, 170),
                      (255,   0, 255),
                      (170, 170,   0),
                      (  0,   0,   0) ]


formatInteger = ['Dec', 'Hex', 'Bin']
formatFloat = ['Norm', 'Sci']
formatAll = formatInteger + formatFloat

formatterStrings = dict()
formatterStrings[formatInteger[0]] = '{0:d}'
formatterStrings[formatInteger[1]] = '0x{0:x}'
formatterStrings[formatInteger[2]] = '0b{0:b}'
formatterStrings[formatFloat[0]] = '{0:f}'
formatterStrings[formatFloat[1]] = '{0:e}'
    
userProperties = None
appDataISystem = os.getenv("APPDATA") + "\\ASYST\\winIDEA\\"
daqIdeaPropertiesFile = appDataISystem + "daqIDEA.properties"
daqIdeaLogFile = appDataISystem + "daqIDEA.log"

class AverageInt():
    
    sampleCount = None
    samples = None
    nextSample = None
    sum = None
    min = 1000000000
    max = -1000000000
    
    def __init__(self, sc):
        self.sampleCount = sc
        self.samples = [0] * sc
        self.nextSample = 0
        self.sum = 0
        
    def add(self, val):
        
        self.nextSample = (self.nextSample + 1) % self.sampleCount

        self.sum += val - self.samples[self.nextSample]

        self.samples[self.nextSample] = val
        
        self.min = min(self.min, val)
        self.max = max(self.max, val)
        
    def getAvg(self):
        if (self.sampleCount > 0):
            return self.sum / self.sampleCount
        else:
            return 0
        
    def getMin(self):
        return self.min
    
    def getMax(self):
        return self.max

def getTkInterMsgDialogInstance():
    root = None
    try:
        import tkinter
        root = tkinter.Tk()
        import tkinter.messagebox as tkMsg
    except ImportError as err:
        import Tkinter
        root = Tkinter.Tk()
        import tkMessageBox as tkMsg
    root.withdraw()
    return tkMsg

def showModuleLoadFailedDialog(moduleName):
    title = 'Failed to load module'
    message = 'Failed to load Python module "' + moduleName + '"'
    getTkInterMsgDialogInstance().showerror(title, message)
    sys.exit()


def checkModule(moduleName):
    try:
        module = imp.find_module(moduleName)
        if module != None:
            logging.info('Module %s found.'%(moduleName))
        else:
            logging.error("Module %s missing!"%(moduleName))
            showModuleLoadFailedDialog(moduleName)
    except ImportError as err:
        logging.exception(err)
        showModuleLoadFailedDialog(moduleName)

def checkModuleVersion(moduleName, requiredVersion, currentVersion, showWarning):
    if (currentVersion != requiredVersion):
        message = "Python module %s version is not supported: %s - expected %s."%(moduleName, currentVersion, requiredVersion)
        logging.warning(message)
        if (showWarning):
            import warningDialog
            showWarning = warningDialog.showWarning('Unsupported module version', message)
    else:
        message = "Python module %s version %s supported."%(moduleName, currentVersion)
        logging.info(message)
    return showWarning

def checkPyQtModuleVersion(requiredVersion, showWarning):
    from PyQt5.QtCore import QT_VERSION_STR
    currentVersion = QT_VERSION_STR
    
    if currentVersion != requiredVersion:
        message = "Python module PyQt5 version is not supported: %s - expected %s."%(currentVersion, requiredVersion)
        logging.warning(message)
        if (showWarning):
            import warningDialog
            showWarning = warningDialog.showWarning('Unsupported module version', message)
    else:
        message = "Python module PyQt5 version %s supported."%(currentVersion)
        logging.info(message)
    return showWarning

def getPythonVersion():
    return str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.' + str(sys.version_info.micro)

def checkModulesForPython(showWarning):
    import numpy
    showWarning = checkModuleVersion('numpy', '1.14.2', getattr(numpy, '__version__'), showWarning)
    import matplotlib
    showWarning = checkModuleVersion('matplotlib', '2.2.2', getattr(matplotlib, '__version__'), showWarning)
    import PyQt5
    showWarning = checkPyQtModuleVersion('5.15.0', showWarning)
    import openpyxl
    showWarning = checkModuleVersion('openpyxl', '2.5.2', getattr(openpyxl, '__version__'), showWarning)
    
    return showWarning

def getUserProperties():
    global daqIdeaPropertiesFile
    logging.info("Loading properties file '%s'"%daqIdeaPropertiesFile)
    
    # Create empty file if it doesn't exist yet
    if os.path.exists(daqIdeaPropertiesFile):
        file = open(daqIdeaPropertiesFile, 'r+')
    else:
        file = open(daqIdeaPropertiesFile, 'a+')
    
    props = properties.Properties()
    props.load(file)
    
    return props

def storeUserProperties(props):
    global daqIdeaPropertiesFile
    file = open(daqIdeaPropertiesFile, 'w+')
    props.store(file)

def checkPythonInstallationAndModules():
    global userProperties
    
    pythonVersion = getPythonVersion()
    logging.info('Python version: %s'%pythonVersion)

    try:
        logging.info('Importing module isystem')
        import isystem
        logging.info('Importing module numpy')
        import numpy
        logging.info('Importing module matplotlib')
        import matplotlib
        logging.info('Importing module PyQt5')
        import PyQt5
        logging.info('Importing module openpyxl')
        import openpyxl
    except ImportError as err:
        logging.error("Module import failed:")
        logging.exception(err)
        checkModule('isystem')
        checkModule('numpy')
        checkModule('matplotlib')
        checkModule('PyQt5')
        checkModule('openpyxl')
    
    logging.info("All required Python modules installed - proceeding with version checks.")
    
    userProperties = getUserProperties()
    showModuleWarning = userProperties.getProperty('show.invalid.module.versions.warning', 'True') == 'True'
    showPythonWarning = userProperties.getProperty('show.invalid.python.versions.warning', 'True') == 'True'

    userProperties.setProperty('show.invalid.module.versions.warning', '%r'%showModuleWarning)
    userProperties.setProperty('show.invalid.python.versions.warning', '%r'%showPythonWarning)
    
    storeUserProperties(userProperties)
    
def initLogging():
    print("Initializing logging. Log file: '%s'"%daqIdeaLogFile)
    logging.basicConfig(filename=daqIdeaLogFile, level=logging.DEBUG)
    msg = "Logging initialized."
    prettyLoggingStart(msg)
    print(msg)

###########
##  msg  ##
###########
def prettyLoggingStart(msg):
    len1 = 100
    logging.info('#'*len1)
    len2 = len1 - len(msg) - 4
    l = len2//2
    r = len2 - l
    logging.info('%s  %s  %s'%('#'*l, msg, '#'*r))
    logging.info('#'*len1)
        
