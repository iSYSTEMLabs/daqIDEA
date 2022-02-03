
from __future__ import print_function

import xml.dom.minidom
import codecs
import isystem.connect as ic
import globals
import os
import io
import logging

from PyQt5 import QtCore, QtGui, QtWidgets

XML_ROOT = 'daqIdeaConfiguration'
XML_GLOBAL_CONFIG = 'global'
XML_ANIMATION_TIME = 'history'
XML_VARIABLES = 'variables'
XML_VARIABLE = 'variable'
XML_ENABLED = 'enabled'
XML_NAME = 'name'
XML_SAMPLING_INTERVAL = 'interval'
XML_CHART_INDEX = 'chart'
XML_SCALE_FACTOR = 'scale'
XML_DATA_FORMAT = 'format'
XML_CHART_COLOR = 'color'


userDir = os.getenv('USERPROFILE')
iSystemDir = userDir + r'\iSYSTEM'
daqIdeaDir = iSystemDir + r'\daqIDEA'
daqIdeaXmlFile = daqIdeaDir + r'\daqIDEA.daq'
strUserDaqIdeaFilePath = daqIdeaDir + r'\daqIDEA.user'
lastConfigFile = None

#
# Load configuration file
#


def getSavedConfigurationAsText(fileName):
    if not os.path.exists(fileName):
        return ''

    file = io.open(fileName, 'r', encoding='utf-8')
    xmlString = file.read()
    file.close()
    return xmlString


def loadConfigurationFile(fileName):
    global lastConfigFile

    # Does it exist?
    if not os.path.exists(fileName):
        lastConfigFile = fileName
        return ApplicationConfiguration()

    if not os.access(fileName, os.R_OK):
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "Configuration file '" +
            os.path.abspath(fileName) +
            "' is not accessible!")
        return None

    # Can we load it normally?
    try:
        xmlString = getSavedConfigurationAsText(fileName)
        dom = xml.dom.minidom.parseString(xmlString)
        #dom = xml.dom.minidom.parse(fileName)
        config = parseConfiguration(dom)

        lastConfigFile = fileName
        return config
    except IOError:
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "Failed to read daqIDEA configuration from file '" +
            os.path.abspath(fileName) + "'")
        return None

def loadDefaultConfiguration():
    if not os.path.exists(userDir):
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "User directory '" +
            os.path.abspath(userDir) +
            "' missing!")
        return ApplicationConfiguration()

    if not os.path.exists(iSystemDir):
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "iSYSTEM directory '" +
            os.path.abspath(iSystemDir) +
            "' missing!")
        return ApplicationConfiguration()

    if not os.path.exists(daqIdeaDir):
        os.makedirs(daqIdeaDir)
        config = ApplicationConfiguration()
        saveConfigurationFile(daqIdeaXmlFile, config)
        return config

    if not os.path.exists(daqIdeaXmlFile):
        config = ApplicationConfiguration()
        saveConfigurationFile(daqIdeaXmlFile, config)
        return config

    if not os.access(daqIdeaXmlFile, os.R_OK):
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "Configuration file '" +
            os.path.abspath(daqIdeaXmlFile) +
            "' not accessible - skipping configuration load!")
        return ApplicationConfiguration()

    try:
        dom = xml.dom.minidom.parse(daqIdeaXmlFile)
    except IOError:
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "Failed to read daqIDEA configuration from file '" +
            os.path.abspath(daqIdeaXmlFile) +
            "'")
        return ApplicationConfiguration()
    except xml.parsers.expat.ExpatError:
        QtWidgets.QMessageBox.critical(
            globals.mainApplicationWindow, "Error!",
            "Malformed configuration file '" +
            os.path.abspath(daqIdeaXmlFile) +
            "'")
        return ApplicationConfiguration()

    lastConfigFile = daqIdeaXmlFile
    return parseConfiguration(dom)


def parseConfiguration(doc):
    config = ApplicationConfiguration()

    root = doc.documentElement
    parseGlobalConfiguration(root, config)
    parseVariableConfiguration(root, config)

    return config


def parseGlobalConfiguration(rootNode, config):
    elements = rootNode.getElementsByTagName(XML_GLOBAL_CONFIG)
    if len(elements) < 1:
        return

    globalConfig = elements[0]

    timeIntervalElements = globalConfig.getElementsByTagName(XML_ANIMATION_TIME)

    if len(timeIntervalElements) > 0:
        config.animationTimeInterval = int(getText(timeIntervalElements[0].childNodes))


def parseVariableConfiguration(rootNode, config):

    variables = rootNode.getElementsByTagName(XML_VARIABLES)
    if len(variables) < 1:
        return

    for varNode in variables[0].getElementsByTagName(XML_VARIABLE):
        parseVariable(varNode, config)


def parseVariable(varNode, config):
    idx = len(config.variableConfigs)
    var = VariableConfiguration(idx)

    # Enabled
    v = str(getVariableParameterValue(varNode, XML_ENABLED))
    if (v == 'True' or v == 'False'):
        var.enabled = (v == 'True')
    else:
        param = getVariableParameterValue(varNode, 'enabled')
        logging.error('daqIDEA configuration parse error: Invalid enabled parameter value: <%s>'%str(param))

    # Variable name
    var.name = str(getVariableParameterValue(varNode, XML_NAME))

    # Time interval
    v = float(getVariableParameterValue(varNode, XML_SAMPLING_INTERVAL))

    if (v == 1):
        var.samplingTimeInterval = ic.CDAQController.daqSample1s
    elif (v == 0.1):
        var.samplingTimeInterval = ic.CDAQController.daqSample100ms
    elif (v == 0.01):
        var.samplingTimeInterval = ic.CDAQController.daqSample10ms
    elif (v == 0.001):
        var.samplingTimeInterval = ic.CDAQController.daqSample1ms
    elif (v == 0):
        var.samplingTimeInterval = ic.CDAQController.daqSampleMax
    else:
        param = getVariableParameterValue(varNode, 'interval')
        logging.error('daqIDEA configuration parse error: Invalid variable configuration time interval: <%s>'%str(param))

    # Chart index
    var.chartIndex = int(getVariableParameterValue(varNode, XML_CHART_INDEX))

    # Chart scale factor
    var.scale = float(getVariableParameterValue(varNode, XML_SCALE_FACTOR))

    # Data table formatter
    var.format = str(getVariableParameterValue(varNode, XML_DATA_FORMAT))

    # Variable chart line color
    var.color = int(getVariableParameterValue(varNode, XML_CHART_COLOR), 16)
    r = (var.color >> 16) & 0xff
    g = (var.color >> 8) & 0xff
    b = var.color & 0xff
    var.floatColor = (r/255.0, g/255.0, b/255.0)

    # Add the variable to the list
    config.variableConfigs.append(var)


def getVariableParameterValue(varNode, parameterName):
    param = varNode.getElementsByTagName(parameterName)

    if len(param) > 0:
        return getText(param[0].childNodes).strip()
    else:
        return None


def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


def getConfigurationAsText(config):
    dom = createDomModel(config)
    xmlstr = dom.toxml()
    return xmlstr


def saveConfigurationFile(fileName, config):
    global lastConfigFile

    if fileName == None:
        fileName = lastConfigFile

    if (fileName == None):
        if not os.path.exists(iSystemDir):
            # print 'Missing iSYSTEM directory: ', iSystemDir
            # print "Failed to create default configuration file '", iSystemDir, "'"
            return

        if not os.path.exists(daqIdeaDir):
            os.makedirs(daqIdeaDir)

        # if not os.path.exists(daqIdeaXmlFile):
        #    print "No default configuration file '" + daqIdeaXmlFile + "' found - creating new one"

        fileName = daqIdeaXmlFile

    xmlstr = getConfigurationAsText(config)
    file = io.open(fileName, 'w', encoding='utf-8')
    file.write(xmlstr)
    file.close()

    lastConfigFile = fileName
    # print 'Saved configuration to file ', lastConfigFile


def createDomModel(config):
    impl = xml.dom.minidom.getDOMImplementation()
    dom = impl.createDocument(None, XML_ROOT, None)
    root_el = dom.documentElement

    # Global configuration
    global_el = dom.createElement(XML_GLOBAL_CONFIG)
    root_el.appendChild(global_el)

    interval_el = dom.createElement(XML_ANIMATION_TIME)
    global_el.appendChild(interval_el)

    interval_el.appendChild(dom.createTextNode(str(config.animationTimeInterval)))

    # Variable configuration
    variables_el = dom.createElement(XML_VARIABLES)
    root_el.appendChild(variables_el)

    # All variables
    for var in config.variableConfigs:
        var_el = dom.createElement(XML_VARIABLE)
        variables_el.appendChild(var_el)

        enabled_el = dom.createElement(XML_ENABLED)
        enabled_el.appendChild(dom.createTextNode(str(var.enabled)))
        var_el.appendChild(enabled_el)

        name_el = dom.createElement(XML_NAME)
        name_el.appendChild(dom.createTextNode(str(var.name)))
        var_el.appendChild(name_el)

        val = globals.samplingIntervalValues.index(var.samplingTimeInterval)
        raw = globals.samplingIntervalRaw[val]
        samplingTimeInterval_el = dom.createElement(XML_SAMPLING_INTERVAL)
        samplingTimeInterval_el.appendChild(dom.createTextNode(raw))
        var_el.appendChild(samplingTimeInterval_el)

        chartIndex_el = dom.createElement(XML_CHART_INDEX)
        chartIndex_el.appendChild(dom.createTextNode(str(var.chartIndex)))
        var_el.appendChild(chartIndex_el)

        scale_el = dom.createElement(XML_SCALE_FACTOR)
        scale_el.appendChild(dom.createTextNode('{0:e}'.format(var.scale)))
        var_el.appendChild(scale_el)

        format_el = dom.createElement(XML_DATA_FORMAT)
        format_el.appendChild(dom.createTextNode(str(var.format)))
        var_el.appendChild(format_el)

        color_el = dom.createElement(XML_CHART_COLOR)
        color_el.appendChild(dom.createTextNode('0x{0:x}'.format(var.color)))
        var_el.appendChild(color_el)

    return dom


#
# Configuration structure
#
class ApplicationConfiguration():
    animationTimeInterval = globals.TIME_INTERVAL_DEFAULT
    variableConfigs = None

    def __init__(self):
        self.animationTimeInterval = 5
        self.variableConfigs = []

    def printout(self, eventStr=None):
        if (eventStr != None):
            logging.info("Application configuration %s:" % eventStr)
        else:
            logging.info("Application configuration:")
        logging.info("\tAnimation time interval: %s seconds."%str(self.animationTimeInterval))
        logging.info("\tVariables: ")
        for v in self.variableConfigs:
            logging.info('\t\tVariable')
            v.printout('\t\t\t')


class VariableConfiguration():

    #
    # Persistent variable settings
    #
    enabled = None
    name = None
    samplingTimeInterval = None
    chartIndex = None
    scale = None
    format = None
    color = None

    #
    # Convenience parameters
    #

    # Required for matplotlib color settings
    floatColor = None
    # Which index is used for this variable inside
    # of the DAQController configuration
    daqConfigIndex = None
    # Variable type that holds this types details
    variable = None
    # Widgets of this variable configuration
    parent = None
    table = None

    rowIndex = -1
    checkBox = None
    intervalCombo = None
    variableCombo = None
    chartSpin = None
    scaleFactorSpin = None
    formatCombo = None
    colorButton = None
    deleteButton = None

    def __init__(self, index):
        #
        # Persistent variables
        #
        self.enabled = True
        self.name = ''
        self.samplingTimeInterval = ic.CDAQController.daqSample1s
        self.chartIndex = 1
        self.scale = 1
        self.format = globals.formatAll[0]
        self.color = 0x000000

        #
        # Convenience variables
        #
        self.floatColor = (0.0, 0.0, 0.0)
        self.daqConfigIndex = -1

        # Get the color from the defaults list
        self.setupDefaultColor(index)

    def setWidgets(self, p, t, widgets):
        self.parent = p
        self.table = t

        self.enableCheckBox = widgets[0]
        self.intervalCombo = widgets[1]
        self.variableCombo = widgets[2]
        self.chartSpin = widgets[3]
        self.scaleFactorSpin = widgets[4]
        self.formatCombo = widgets[5]
        self.colorButton = widgets[6]
        self.deleteButton = widgets[7]


    def setupDefaultColor(self, index):
        # Set the default color for a new blank row
        defaultColorCount = len(globals.defaultPlotColors)
        c = globals.defaultPlotColors[index % defaultColorCount]
        self.color = (c[0] << 16) + (c[1] << 8) + c[2]
        self.floatColor = (c[0]/255.0, c[1]/255.0, c[2]/255.0)


    def printout(self, indent='\t'):
        logging.info()
        logging.info('%sEnabled: %s' % (indent, str(self.enabled)))
        logging.info('%sName: %s' % (indent, str(self.name)))
        logging.info('%sSampling time: %s'%(indent, str(self.samplingTimeInterval)))
        logging.info('%sChart: %s' % (indent, str(self.chartIndex)))
        logging.info('%sScale factor: %s' % (indent, str(self.scale)))
        logging.info('%sPrint format: %s' % (indent, str(self.format)))

        fStr = '0x{0:x}'.format(self.color)
        logging.info('%sColor: %s(%s)' % (indent, fStr, str(self.floatColor)))
        logging.info('%sVar: %s' % (indent, self.variable.toString()))


    def enableVariableChanged(self):
        if self.enableCheckBox == None:
            return

        self.enabled = self.enableCheckBox.isChecked()

        self.intervalCombo.setEnabled(self.enabled)
        self.variableCombo.setEnabled(self.enabled)
        self.chartSpin.setEnabled(self.enabled)
        self.scaleFactorSpin.setEnabled(self.enabled)
        self.formatCombo.setEnabled(self.enabled)
        self.colorButton.setEnabled(self.enabled)

        self.parent.checkAllVariablesValidity()
        self.parent.canvasGraph.updateChartSubplots()

            
    def samplingIntervalChanged(self):
        if self.intervalCombo == None:
            return

        comboIndex = self.intervalCombo.currentIndex()
        self.samplingTimeInterval = globals.samplingIntervalValues[comboIndex]

                
    def chartIndexChanged(self):
        if self.chartSpin == None:
            return

        self.chartIndex = self.chartSpin.value()
        self.parent.canvasGraph.updateChartSubplots()

        
    def formatIndexChanged(self):
        if self.formatCombo == None:
            return

        formatIndex = self.formatCombo.currentIndex()

        if (formatIndex >= 0):
            self.format = self.variable.formatters[formatIndex]

        self.parent.dataTable.model().updateFormatting()


    def updateFormatterComboBox(self):
        selectedFormat = self.format

        if self.formatCombo != None:
            self.formatCombo.clear()

            if (self.variable != None):
                self.formatCombo.addItems(self.variable.formatters)

                if (selectedFormat in self.variable.formatters):
                    idx = self.variable.formatters.index(selectedFormat)
                    self.formatCombo.setCurrentIndex(idx)


