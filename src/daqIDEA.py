
from __future__ import print_function

import globals
import logging

#
# Logging
#
try:
    globals.initLogging()
except Exception as e:
    title = 'Failed to initialize logging'
    msg = str(e)
    globals.getTkInterMsgDialogInstance().showwarning(title, msg)

#
# Checking required modules
#
# This doesn't work when launched as daqIDEA.exe
# try:
#    globals.checkPythonInstallationAndModules()
# except Exception as e:
#    logging.exception(e)
#    title = "Module check process failed!"
#    msg = str(e) + "\n\n See log file at: " + globals.daqIdeaLogFile
#    globals.getTkInterMsgDialogInstance().showerror(title, msg)

# The rest of the imports
import sys
import isystem.connect as ic
import random, math, time

from PyQt5 import QtCore, QtGui, QtWidgets

from chart import *
from widgets import *
from daqManager import *
from variable import *

import user_data
import variableConfiguration
import exporters

# import cProfile

class ApplicationWindow(QtWidgets.QMainWindow):

    userData = user_data.CUserData()
    daqIdeaConfig = None
    daqIdeaFilePath = None

    textFrame = None

    main_widget = None
    variableTable = None
    variableAddButton = None

    mainSplitter = None

    mainChartGroup = None
    mainTableGroup = None
    mainControlGroup = None

    applicationControllGroup = None
    variableControllGroup = None
    chartControllGroup = None

    canvasGraph = None

    appDownloadButton = None
    appPlayButton = None
    appStopButton = None
    appStatusLabel = None

    chartPlayButton = None
    chartPauseButton = None
    chartStopButton = None
    chartEstimateMissingValuesCb = None
    chartAdaptiveTimeUnitCb = None

    variableStatusLabel = None

    iconZoom = None
    iconPan = None

    # WinIDEA IConnect
    connectionMgr = None
    debugMgr = None
    daqManager = None
    lastWinIdeaAstatus = -1
    waitingForDownload = None

    dataTable = None
    dataModel = None

    def setWinIdeaConfig(self, cMgr, dMgr):
        self.connectionMgr = cMgr
        self.debugMgr = dMgr

    #
    # After we setup the entire GUI we can start updating it with WinIDEA statuses
    #
    def startWinIdeaSynch(self):
        self.appStatusLabel.setText('<font color=black size=5>Waiting for download</font>')
        self.updateApplicationControlGroup()
        self.startWinIDEAStatusChecker()

    # We check WinIDEA status (download/run/stop) so we can update the
    # application control GUI
    def startWinIDEAStatusChecker(self):
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateApplicationControlGroup)
        # Every 300ms
        timer.start(300)

    def updateApplicationControlGroup(self):
        if not self.connectionMgr.isAttached():
            # Lost connection to winIDEA - closing daqIDEA
            self.close()
            return

        cpuStatus = self.debugMgr.getCPUStatus()

        # At start of the application we check the download status
        if self.waitingForDownload == None:
            self.waitingForDownload = cpuStatus.isMustInit()

        newStatus = 0
        newStatus += int(cpuStatus.isMustInit()) << 2
        newStatus += int(cpuStatus.isRunning()) << 1
        newStatus += int(cpuStatus.isStopped()) << 0

        if (self.lastWinIdeaAstatus != newStatus):
            self.appDownloadButton.setEnabled(True)
            self.appPlayButton.setEnabled(cpuStatus.isStopped() and
                                          not cpuStatus.isMustInit())
            self.appStopButton.setEnabled(cpuStatus.isRunning() and
                                          not cpuStatus.isMustInit())

            # If at start the app was not downloaded and now it happened
            if (self.waitingForDownload and not cpuStatus.isMustInit()):
                self.daqManager = DaqManager(self.connectionMgr)
                self.variableControllGroup.setEnabled(True)
                self.chartControllGroup.setEnabled(True)
                self.waitingForDownload = False
                self.initVariableTableGui()
            elif (not self.waitingForDownload and self.daqManager == None):
                self.daqManager = DaqManager(self.connectionMgr)
                self.initVariableTableGui()


            self.variableControllGroup.setEnabled(not cpuStatus.isMustInit())
            self.chartControllGroup.setEnabled(not cpuStatus.isMustInit())

            if (cpuStatus.isMustInit()):
                self.appStatusLabel.setText('<font color=black size=5>' +
                                            'Waiting for download</font>')
            elif (cpuStatus.isRunning()):
                self.appStatusLabel.setText('<font color=black size=5>' +
                                            'Application Running</font>')
            elif (cpuStatus.isStopped()):
                self.appStatusLabel.setText('<font color=black size=5>' +
                                            'Application Stopped</font>')
            else:
                logging.error("Unexpected CPU Status:")
                logging.error("isMustInit() = %r" % cpuStatus.isMustInit())
                logging.error("isStopped() = %r" % cpuStatus.isStopped())
                logging.error("isRunning() = %r" % cpuStatus.isRunning())
                logging.error("isReset() = %r" % cpuStatus.isReset())
                logging.error("isHalted() = %r" % cpuStatus.isHalted())
                logging.error("isWaiting() = %r" % cpuStatus.isWaiting())
                logging.error("isAttach() = %r" % cpuStatus.isAttach())
                logging.error("isIdle() = %r" % cpuStatus.isIdle())
                logging.error("isStopReasonExplicit() = %r"%cpuStatus.isStopReasonExplicit())
                logging.error("isStopReasonBP() = %r"%cpuStatus.isStopReasonBP())
                logging.error("isStopReasonStep() = %r"%cpuStatus.isStopReasonStep())
                logging.error("isStopReasonHW() = %r"%cpuStatus.isStopReasonHW())
                logging.error("toString() = %s" % cpuStatus.toString())

            self.lastWinIdeaAstatus = newStatus


    def checkAllVariablesValidity(self):
        allOk = True
        plotCount = 0

        for varIdx, varConfig in enumerate(self.daqIdeaConfig.variableConfigs):
            varEnabled = varConfig.enabled
            varName = varConfig.name

            # Check variable name only if the variable is enabled
            if varEnabled:
                plotCount += 1
                if (len(varName) <= 0):
                    self.setVariableValidityStatus('red', "Please specify " +
                                                   "the names of all variables.")
                    allOk = False

        if (allOk and
            plotCount > 0 and
                not self.canvasGraph.isAnimationRunning()):
            self.chartPlayButton.setEnabled(True)
        else:
            self.chartPlayButton.setEnabled(False)


    def addNewVariableTableRow(self, varConfig=None):
        table = self.variableTable

        newRowIndex = table.rowCount()-1
        table.insertRow(newRowIndex)

        if varConfig == None:
            varCount = len(self.daqIdeaConfig.variableConfigs)
            varConfig = variableConfiguration.VariableConfiguration(varCount)
            self.daqIdeaConfig.variableConfigs.append(varConfig)

        checkBox = QtWidgets.QCheckBox()
        checkBox.setToolTip("Show or hide the variable in the chart.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_ENABLED, checkBox)

        intervalCombo = QtWidgets.QComboBox(self)
        intervalCombo.addItems(globals.samplingIntervalNames)
        intervalCombo.setToolTip("Time interval for DAQ process of this variable.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_INTERVAL, intervalCombo)

        variableCombo = VariableChooserCombo(self, varConfig)
        variableCombo.setVariables(self.daqManager.getVariables())
        variableCombo.setEditable(True)
        variableCombo.setToolTip("Name of the variable for which to gather data.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_NAME, variableCombo)

        chartSpin = QtWidgets.QSpinBox()
        chartSpin.setRange(1, 6)
        chartSpin.setPrefix('Chart ')
        chartSpin.setToolTip("Chart in which to show this variables data.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_CHART, chartSpin)

        scaleFactorSpin = ScaleSpinner(self, varConfig)
        scaleFactorSpin.setToolTip("A factor by which to multiply this variables data inside of the chart.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_SCALE, scaleFactorSpin)

        formatCombo = QtWidgets.QComboBox(self)
        formatCombo.setToolTip("Format in which to show the this variables data inside of the data table.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_FORMAT, formatCombo)

        colorButton = ColorButton(self, varConfig)
        colorButton.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        colorButton.setToolTip("Color to be used for plotting this variables data on the chart.")
        colorButton.updateIcon()
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_COLOR, colorButton)

        deleteButton = DeleteButton(self, varConfig)
        deleteButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\delete.png'))
        deleteButton.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        deleteButton.setToolTip("Remove this variable from the selected variables list.")
        table.setCellWidget(newRowIndex, globals.TABLE_COLUMN_DELETE, deleteButton)

        #
        # Setup initial values and event listeners
        #
        w = [checkBox,
             intervalCombo,
             variableCombo,
             chartSpin,
             scaleFactorSpin,
             formatCombo,
             colorButton,
             deleteButton]
        varConfig.setWidgets(self, table, w)

        checkBox.clicked.connect(varConfig.enableVariableChanged)
        checkBox.setChecked(varConfig.enabled)

        intervalCombo.currentIndexChanged.connect(varConfig.samplingIntervalChanged)
        intervalCombo.setCurrentIndex(varConfig.samplingTimeInterval)

        variableCombo.setEditText(varConfig.name)

        chartSpin.valueChanged.connect(varConfig.chartIndexChanged)
        chartSpin.setValue(varConfig.chartIndex)

        scaleFactorSpin.setMultiplicator(varConfig.scale)

        varConfig.updateFormatterComboBox()
        formatCombo.currentIndexChanged.connect(varConfig.formatIndexChanged)

        #
        # General GUI update
        #
        self.checkAllVariablesValidity()
        self.canvasGraph.updateChartSubplots()



    def resizeVariableTableHack(self, varConfig=None):
        table = self.variableTable

        table.insertRow(0)

        checkBox = QtWidgets.QCheckBox()
        table.setCellWidget(0, globals.TABLE_COLUMN_ENABLED, checkBox)

        intervalCombo = QtWidgets.QComboBox(self)
        intervalCombo.addItems(['1 s', '100 ms', '10 ms', '1 ms', 'MAX'])
        intervalCombo.setCurrentIndex(1)
        table.setCellWidget(0, globals.TABLE_COLUMN_INTERVAL, intervalCombo)

        variableCombo = QtWidgets.QComboBox(self)
        variableCombo.addItems(['small', 'biggest_variable_name_ever'])
        variableCombo.setEditable(True)
        table.setCellWidget(0, globals.TABLE_COLUMN_NAME, variableCombo)

        chartSpin = QtWidgets.QSpinBox()
        chartSpin.setRange(1, 6)
        chartSpin.setPrefix('Chart ')
        chartSpin.setValue(6)
        table.setCellWidget(0, globals.TABLE_COLUMN_CHART, chartSpin)

        scaleFactorSpin = QtWidgets.QSpinBox()
        scaleFactorSpin.setWrapping(True)
        scaleFactorSpin.setRange(-9, -1)
        scaleFactorSpin.setPrefix('-1e')
        scaleFactorSpin.setValue(-9)
        table.setCellWidget(0, globals.TABLE_COLUMN_SCALE, scaleFactorSpin)

        formatCombo = QtWidgets.QComboBox(self)
        formatCombo.addItems(globals.formatAll)
        formatCombo.setCurrentIndex(3)
        table.setCellWidget(0, globals.TABLE_COLUMN_FORMAT, formatCombo)

        colorButton = QtWidgets.QPushButton()
        colorButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\delete.png'))
        colorButton.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        table.setCellWidget(0, globals.TABLE_COLUMN_COLOR, colorButton)

        deleteButton = QtWidgets.QPushButton()
        deleteButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\delete.png'))
        deleteButton.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        table.setCellWidget(0, globals.TABLE_COLUMN_DELETE, deleteButton)

        table.resizeColumnsToContents()
        table.setColumnWidth(globals.TABLE_COLUMN_ENABLED, 18)

        table.removeRow(0)


    def initVariableTableGui(self, newConfig=None):
        globals.samplingIntervalRaw = ['0', '0.001', '0.01', '0.1', '1']
        globals.samplingIntervalNames = ['MAX', '1 ms', '10 ms', '100 ms', '1 s']
        globals.samplingIntervalValues = [ic.CDAQController.daqSampleMax,
                                          ic.CDAQController.daqSample1ms,
                                          ic.CDAQController.daqSample10ms,
                                          ic.CDAQController.daqSample100ms,
                                          ic.CDAQController.daqSample1s]

        # If we already have an active configuration then first clean up the
        # GUI
        if (self.daqIdeaConfig != None and newConfig != None):
            configs = self.daqIdeaConfig.variableConfigs

            while len(configs) > 0:
                configs.pop(0)
                self.variableTable.cellWidget(0, globals.TABLE_COLUMN_NAME).removing()
                self.variableTable.removeRow(0)

            self.canvasGraph.updateChartSubplots()
            self.dataTable.model().updateDataModel()
            self.checkAllVariablesValidity()

            self.daqIdeaConfig = newConfig
            

        self.dataModel = DaqTableModel(self, self.daqIdeaConfig)
        itemDelegate = DaqItemDelegate(self, self.dataModel)
        self.dataTable.setModel(self.dataModel)
        self.dataTable.setItemDelegate(itemDelegate)

        # Setup GUI using new configuration file
        for varConf in self.daqIdeaConfig.variableConfigs:
            self.addNewVariableTableRow(varConf)

        self.saveConfigurationAction.setEnabled(True)
        self.saveAsConfigurationAction.setEnabled(True)
        self.openConfigurationAction.setEnabled(True)

    def createMenu(self):
        #
        # File menu
        #
        file_menu = QtWidgets.QMenu('&File', self)
        self.menuBar().addMenu(file_menu)

        # Save configuration
        self.saveConfigurationAction = QtWidgets.QAction(QtGui.QIcon('\\..\\resources\\icons\\Save.png'), 'Save', self)
        self.saveConfigurationAction.setShortcut('Ctrl+S')
        self.saveConfigurationAction.setStatusTip('Save configuration to file')
        self.saveConfigurationAction.triggered.connect(self.saveConfigurationToCurrentFile)
        self.saveConfigurationAction.setEnabled(True)
        file_menu.addAction(self.saveConfigurationAction)

        # Save configuration as
        self.saveAsConfigurationAction = QtWidgets.QAction(QtGui.QIcon('\\..\\resources\\icons\\Save.png'), 'Save As...', self)
        self.saveAsConfigurationAction.setShortcut('Ctrl+A')
        self.saveAsConfigurationAction.setStatusTip('Save configuration to an alternate file')
        self.saveAsConfigurationAction.triggered.connect(self.showSaveConfigurationDialog)
        self.saveAsConfigurationAction.setEnabled(True)
        file_menu.addAction(self.saveAsConfigurationAction)

        # Open config
        self.openConfigurationAction = QtWidgets.QAction(QtGui.QIcon('\\..\\resources\\icons\\Save.png'), 'Open', self)
        self.openConfigurationAction.setShortcut('Ctrl+O')
        self.openConfigurationAction.setStatusTip('Open configuration file')
        self.openConfigurationAction.triggered.connect(self.showOpenConfigurationDialog)
        self.openConfigurationAction.setEnabled(True)
        file_menu.addAction(self.openConfigurationAction)

        # Export data
        self.exportDataAction = QtWidgets.QAction(QtGui.QIcon('\\..\\resources\\icons\\Save.png'), 'Export data', self)
        self.exportDataAction.setShortcut('Ctrl+E')
        self.exportDataAction.setStatusTip('Export data to file')
        self.exportDataAction.triggered.connect(self.showExportDataDialog)
        self.exportDataAction.setEnabled(False)
        file_menu.addAction(self.exportDataAction)

        # Exit
        file_menu.addAction('&Exit', self.fileQuit,QtCore.Qt.CTRL + QtCore.Qt.Key_X)

        #
        # Help menu
        #
        help_menu = QtWidgets.QMenu('&Help', self)

        # About
        self.menuBar().addSeparator()
        self.menuBar().addMenu(help_menu)

        help_menu.addAction('&User Guide', self.help, QtGui.QKeySequence(QtCore.Qt.Key_F1))
        help_menu.addAction('&About', self.about)


    def showExportDataDialog(self):
        startFile = None

        # If no export has been done yet then take the daqIDEA configuration directory
        if exporters.lastDataExportFile != None:
            startFile = exporters.lastDataExportFile
        elif variableConfiguration.lastConfigFile != None:
            startFile = os.path.dirname(variableConfiguration.lastConfigFile)
        else:
            startFile = variableConfiguration.daqIdeaXmlFile

        fileName, fileType = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Export data to file',
            startFile,
            'Excel file (*.xlsx);;' +
            'Comma separated values file (*.csv);;' +
            'Text file (*.txt)')

        data = self.daqManager.getRawData()
        varNames = self.canvasGraph.myParent.daqManager.getSelectedVariableNames()

        if (fileType.find('.xlsx') != -1):
            fileName = self.appendFileExtension(fileName, '.xlsx')
            # exporters.exportToExcel(fileName, data[0], data[1], varNames)
            exporters.exportToExcel(self, fileName, self.dataTable.model(), varNames)
        elif (fileType.find('.csv') != -1):
            fileName = self.appendFileExtension(fileName, '.csv')
            exporters.exportToCharSeparatedValues(fileName, data[0], data[1], ',', varNames, self.dataTable.model().dataModelFull)
        elif (fileType.find('.txt') != -1):
            fileName = self.appendFileExtension(fileName, '.txt')
            exporters.exportToCharSeparatedValues(fileName, data[0], data[1], ' ', varNames, self.dataTable.model().dataModelFull)
        else:
            logging.error("Invalid file extension for filename '%s'"%fileName)

    def appendFileExtension(self, fileName, fileExtension):
        if not fileName.endswith(fileExtension):
            fileName += fileExtension

        return fileName

    def getConfigurationFileName(self):
        startFile = variableConfiguration.lastConfigFile
        if startFile == None:
            startFile = variableConfiguration.daqIdeaXmlFile
        return startFile

    def saveConfigurationToCurrentFile(self):
        fileName = self.getConfigurationFileName()
        variableConfiguration.saveConfigurationFile(
            fileName, self.daqIdeaConfig)

    def showSaveConfigurationDialog(self):
        startFile = self.getConfigurationFileName()

        fileName, fileType = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Save configuration',
            startFile,
            'daqIDEA Configuration file (*.daq)')

        if (len(fileName.strip()) > 0):
            variableConfiguration.saveConfigurationFile(fileName, self.daqIdeaConfig)

        self.updateWindowTitle()

    def showOpenConfigurationDialog(self):
        startFile = variableConfiguration.lastConfigFile
        if startFile == None:
            startFile = variableConfiguration.daqIdeaXmlFile

        fileName, fileType = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Open Configuration',
            startFile,
            'daqIDEA Configuration file (*.daq)')

        if (len(fileName.strip()) > 0):
            newConfig = variableConfiguration.loadConfigurationFile(fileName)

            if newConfig != None:
                self.initVariableTableGui(newConfig)
                self.updateWindowTitle()

    def updateWindowTitle(self):
        fileName = self.getConfigurationFileName()
        if len(fileName) > 0:
            self.setWindowTitle('{} daqIDEA'.format(fileName))
        else:
            self.setWindowTitle('iSYSTEM daqIDEA')

    def createPlayGroup(self, parentLayout, stretch):
        group = QtWidgets.QGroupBox("Application control")
        layout = QtWidgets.QHBoxLayout()
        group.setLayout(layout)

        self.appDownloadButton = QtWidgets.QPushButton()
        self.appDownloadButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\download.png'))
        self.appDownloadButton.setToolTip('Download application')
        self.appDownloadButton.setEnabled(True)
        self.appDownloadButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F5))
        self.appDownloadButton.clicked.connect(self.applicationDownloadButtonPressed)
        layout.addWidget(self.appDownloadButton, 0)

        self.appPlayButton = QtWidgets.QPushButton()
        self.appPlayButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\play.png'))
        self.appPlayButton.setToolTip('Run application')
        self.appPlayButton.setEnabled(False)
        self.appPlayButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F6))
        self.appPlayButton.clicked.connect(self.applicationStartButtonPressed)
        layout.addWidget(self.appPlayButton)

        self.appStopButton = QtWidgets.QPushButton()
        self.appStopButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\stop.png'))
        self.appStopButton.setToolTip('Stop application')
        self.appStopButton.setEnabled(False)
        self.appStopButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F7))
        self.appStopButton.clicked.connect(self.applicationStopButtonPressed)
        layout.addWidget(self.appStopButton, 0)

        self.appStatusLabel = QtWidgets.QLabel("<font color=black size=5>Waiting</font>")
        self.appStatusLabel.setToolTip('Current processing status')
        self.appStatusLabel.setEnabled(False)
        layout.addWidget(self.appStatusLabel, 1)

        parentLayout.addWidget(group, stretch=stretch)

    def applicationDownloadButtonPressed(self):
        self.appStatusLabel.setText('<font color=black size=5>Downloading</font>')
        self.appDownloadButton.setEnabled(False)
        self.appPlayButton.setEnabled(False)
        self.appStopButton.setEnabled(False)
        self.variableControllGroup.setEnabled(False)
        self.chartControllGroup.setEnabled(False)

        # Create worker thread and start the download
        ide = ic.CIDEController(self.connectionMgr)
        self.downloadThread = DownloadThread(self.debugMgr, ide)
        self.downloadThread.signal.downloaded.connect(self.applicationDownloadCompleted)
        self.downloadThread.start()

    def applicationDownloadCompleted(self, data):
        # Set download, play and stop buttons according to the current CPU Status
        self.appStatusLabel.setText('<font color=black size=5>' +
                                    'Application Downloaded</font>')
        status = self.debugMgr.getCPUStatus()
        self.appDownloadButton.setEnabled(True)
        self.appPlayButton.setEnabled(status.isStopped() or status.isWaiting())
        self.appStopButton.setEnabled(status.isRunning())
        self.variableControllGroup.setEnabled(True)
        self.chartControllGroup.setEnabled(True)

        self.show()
        self.raise_()
        self.activateWindow()

        self.daqManager = DaqManager(self.connectionMgr)

    def applicationStartButtonPressed(self):
        self.appPlayButton.setEnabled(False)
        self.appStopButton.setEnabled(True)
        self.appStatusLabel.setText('<font color=black size=5>' +
                                    'Application Running</font>')
        self.debugMgr.run()

    def applicationStopButtonPressed(self):
        self.appPlayButton.setEnabled(True)
        self.appStopButton.setEnabled(False)
        self.appStatusLabel.setText('<font color=black size=5>' +
                                    'Application Stopped</font>')
        self.debugMgr.stop()

    def createVariableGroup(self, parentLayout, stretch):
        group = QtWidgets.QGroupBox("Variable settings")
        self.variableControllGroup = group

        layout = QtWidgets.QVBoxLayout()
        group.setLayout(layout)

        table = QtWidgets.QTableWidget(1, globals.TABLE_COLUMN_COUNT, self)
        self.variableTable = table
        table.setHorizontalHeaderLabels(
            ('', 'Sampling', 'Variable name', 'Chart', 'Scale', 'Format', 'Color', ''))
        table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        table.setShowGrid(False)

        # New variable row button
        self.variableAddButton = QtWidgets.QPushButton("Add Variable")
        self.variableAddButton.setToolTip("Adds a new variable to be shown on the chart.")
        self.variableAddButton.clicked.connect(lambda: self.addNewVariableTableRow(None))

        table.setSpan(0, 0, 1, globals.TABLE_COLUMN_COUNT)
        table.setCellWidget(0, 0, self.variableAddButton)

        sizes = [18, 60, 170, 65, 50, 60, 45, 30]

        table.setMinimumSize(QtCore.QSize(sum(sizes)+4, 100))

        self.resizeVariableTableHack()

        self.mainControlGroup.layout().update()

        layout.addWidget(table, 1)

        # Variable status messages
        self.variableStatusLabel = QtWidgets.QLabel()
        self.variableStatusLabel.setToolTip('Current processing status')
        self.variableStatusLabel.setEnabled(False)
        self.variableStatusLabel.setWordWrap(True)
        layout.addWidget(self.variableStatusLabel, 0)

        self.setVariableValidityStatus('black', "")

        group.setEnabled(False)
        parentLayout.addWidget(group, stretch=stretch)

    def setVariableValidityStatus(self, col, msg):
        self.variableStatusLabel.setText('<font color=' + col + ' size=4>' +
                                         msg + '</font>')

    def createChartControlGroup(self, parentLayout, stretch):
        group = QtWidgets.QGroupBox("Data Acquisition Control")
        self.chartControllGroup = group
        layout = QtWidgets.QHBoxLayout()
        group.setLayout(layout)

        self.chartPlayButton = QtWidgets.QPushButton()
        self.chartPlayButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\play.png'))
        self.chartPlayButton.setToolTip('Start DAQ process')
        self.chartPlayButton.setEnabled(False)
        self.chartPlayButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F9))
        self.chartPlayButton.clicked.connect(self.chartPlayButtonPressed)
        layout.addWidget(self.chartPlayButton)

        self.chartPauseButton = QtWidgets.QPushButton()
        self.chartPauseButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\pause.png'))
        self.chartPauseButton.setToolTip('Pause DAQ process')
        self.chartPauseButton.setEnabled(False)
        self.chartPauseButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F10))
        self.chartPauseButton.clicked.connect(self.chartPauseButtonPressed)
        layout.addWidget(self.chartPauseButton)

        self.chartStopButton = QtWidgets.QPushButton()
        self.chartStopButton.setIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\stop.png'))
        self.chartStopButton.setToolTip('Stop DAQ process')
        self.chartStopButton.setEnabled(False)
        self.chartStopButton.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F11))
        self.chartStopButton.clicked.connect(self.chartStopButtonPressed)
        layout.addWidget(self.chartStopButton)

        layout.addStretch(1)

        self.chartAdaptiveTimeUnitCb = QtWidgets.QCheckBox()
        self.chartAdaptiveTimeUnitCb.setToolTip('Time units are changed depending on the value.')
        self.chartAdaptiveTimeUnitCb.setText('Adjust units')
        self.chartAdaptiveTimeUnitCb.setEnabled(True)
        self.chartAdaptiveTimeUnitCb.setChecked(True)
        self.chartAdaptiveTimeUnitCb.clicked.connect(self.chartAdaptiveTimeUnitButtonPressed)
        layout.addWidget(self.chartAdaptiveTimeUnitCb)

        self.chartEstimateMissingValuesCb = QtWidgets.QCheckBox()
        self.chartEstimateMissingValuesCb.setToolTip('When this is checked all empty table cells will be filled with estimated (most recent) values.')
        self.chartEstimateMissingValuesCb.setText('Estimate missing values')
        self.chartEstimateMissingValuesCb.setEnabled(True)
        self.chartEstimateMissingValuesCb.setChecked(True)
        self.chartEstimateMissingValuesCb.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F12))
        self.chartEstimateMissingValuesCb.clicked.connect(self.chartShowEstimatedValuesButtonPressed)
        layout.addWidget(self.chartEstimateMissingValuesCb)

        group.setEnabled(False)
        parentLayout.addWidget(group, stretch=stretch)

    def chartPlayButtonPressed(self):
        if not self.daqManager.checkDAQControllerAvailability():
            return

        if self.canvasGraph.startAnimation():
            self.chartPlayButton.setEnabled(False)
            self.chartPauseButton.setEnabled(True)
            self.chartStopButton.setEnabled(True)
            self.appDownloadButton.setEnabled(False)

            self.variableTableEnableEditing(False)
            self.exportDataAction.setEnabled(False)

    def chartPauseButtonPressed(self):
        self.chartPlayButton.setEnabled(True)
        self.chartPauseButton.setEnabled(False)
        self.chartStopButton.setEnabled(True)

        self.canvasGraph.pauseAnimation()
        self.exportDataAction.setEnabled(True)

    def chartStopButtonPressed(self):
        self.chartPlayButton.setEnabled(True)
        self.chartPauseButton.setEnabled(False)
        self.chartStopButton.setEnabled(False)

        self.canvasGraph.stopAnimation()
        self.appDownloadButton.setEnabled(True)
        self.variableTableEnableEditing(True)
        self.exportDataAction.setEnabled(True)

    def chartAdaptiveTimeUnitButtonPressed(self):
        bAdapt = self.chartAdaptiveTimeUnitCb.isChecked()
        self.dataTable.itemDelegate().setAdaptiveTimeUnit(bAdapt)
        if (bAdapt):
            self.dataTable.model().setTimeUnit(None)
        else:
            self.dataTable.model().setTimeUnit('s')

        self.dataTable.horizontalHeader().viewport().repaint()
        self.dataTable.viewport().repaint()

    def chartShowEstimatedValuesButtonPressed(self):
        full = self.chartEstimateMissingValuesCb.isChecked()
        self.dataTable.model().setDataModelEstimation(full)
        self.dataTable.model().updateDataModel()

    def variableTableEnableEditing(self, enable):
        configs = self.daqIdeaConfig.variableConfigs

        for rowIdx, varConfig in enumerate(configs):
            self.variableTable.cellWidget(rowIdx, globals.TABLE_COLUMN_ENABLED).setEnabled(enable)
            self.variableTable.cellWidget(rowIdx, globals.TABLE_COLUMN_DELETE).setEnabled(enable)

            # The rows that are not editable during the animation running time
            enableRowWidgets = varConfig.enabled and enable
            self.variableTable.cellWidget(rowIdx, globals.TABLE_COLUMN_INTERVAL).setEnabled(enableRowWidgets)
            self.variableTable.cellWidget(rowIdx, globals.TABLE_COLUMN_NAME).setEnabled(enableRowWidgets)

        self.variableAddButton.setEnabled(enable)
        

    def createChartGroup(self, splitter):

        self.mainChartGroup = QtWidgets.QGroupBox()
        group = self.mainChartGroup
        layout = QtWidgets.QVBoxLayout()

        self.canvasGraph = MyDynamicMplCanvas(self, width=7, height=4, dpi=100)

        self.canvasGraph.mpl_connect('button_press_event', self.canvasGraph.mousePress)
        self.canvasGraph.mpl_connect('button_release_event', self.canvasGraph.mouseRelease)    
        self.canvasGraph.mpl_connect('motion_notify_event', self.canvasGraph.mouseMotion)
        self.canvasGraph.mpl_connect('scroll_event', self.canvasGraph.mouseScroll)
        self.canvasGraph.mpl_connect('axes_leave_event', self.canvasGraph.mouseLeaveAxis)
        # self.canvasGraph.mpl_connect('pick_event', self.canvasGraph.pickEvent)

        self.canvasGraph.setMinimumSize(QtCore.QSize(200, 250))

        layout.addWidget(self.canvasGraph)
        group.setLayout(layout)

        splitter.addWidget(group)
        

    def createDataTableGroup(self, splitter):

        self.mainTableGroup = QtWidgets.QGroupBox("")
        group = self.mainTableGroup
        layout = QtWidgets.QVBoxLayout()

        self.dataTable = QtWidgets.QTableView()

        self.dataTable.setSortingEnabled(False)
        self.dataTable.setMinimumSize(QtCore.QSize(200, 100))
        self.dataTable.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.dataTable.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        layout.addWidget(self.dataTable)

        group.setLayout(layout)
        splitter.addWidget(group)


    def createControlGroup(self, splitter):

        controlGroupSplitter = QtWidgets.QSplitter()
        controlGroupSplitter.setOrientation(QtCore.Qt.Vertical)

        self.mainControlGroup = QtWidgets.QGroupBox("")
        layout = QtWidgets.QVBoxLayout()
        self.mainControlGroup.setLayout(layout)

        self.createPlayGroup(layout, 0)
        self.createVariableGroup(layout, 1)
        self.createChartControlGroup(layout, 0)

        controlGroupSplitter.addWidget(self.mainControlGroup)
        self.createDataTableGroup(controlGroupSplitter)

        splitter.addWidget(controlGroupSplitter)

    def createMainGroup(self, parentLayout):
        layout = QtWidgets.QHBoxLayout()

        self.mainSplitter = QtWidgets.QSplitter()

        self.createChartGroup(self.mainSplitter)
        self.createControlGroup(self.mainSplitter)

        parentLayout.addWidget(self.mainSplitter)

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

    SPEC_RAW = 0
    SPEC_AVG = 1
    SPEC_MM = 2
    SPEC_CON = 3

    specialNames = ['Raw', 'Avg', 'Min/Max', 'Container']
    specialEnabled = [True]*len(specialNames)

    def addSpecialToolbar(self):
        detailAction = QtWidgets.QAction(self.specialNames[0], self)
        detailAction.setShortcut('Ctrl+z')
        detailAction.triggered.connect(self.button1click)
        toolbar = self.addToolBar(self.specialNames[0])
        toolbar.addAction(detailAction)

        minMaxAction = QtWidgets.QAction(self.specialNames[1], self)
        minMaxAction.setShortcut('Ctrl+x')
        minMaxAction.triggered.connect(self.button2click)
        toolbar = self.addToolBar(self.specialNames[1])
        toolbar.addAction(minMaxAction)

        averageAction = QtWidgets.QAction(self.specialNames[2], self)
        averageAction.setShortcut('Ctrl+c')
        averageAction.triggered.connect(self.button3click)
        toolbar = self.addToolBar(self.specialNames[2])
        toolbar.addAction(averageAction)

        averageAction = QtWidgets.QAction(self.specialNames[3], self)
        averageAction.setShortcut('Ctrl+v')
        averageAction.triggered.connect(self.button4click)
        toolbar = self.addToolBar(self.specialNames[3])
        toolbar.addAction(averageAction)


    def button1click(self):
        self.specialEnabled[0] = not self.specialEnabled[0]
        self.canvasGraph.updateCharts()

    def button2click(self):
        self.specialEnabled[1] = not self.specialEnabled[1]
        self.canvasGraph.updateCharts()

    def button3click(self):
        self.specialEnabled[2] = not self.specialEnabled[2]
        self.canvasGraph.updateCharts()

    def button4click(self):
        self.specialEnabled[3] = not self.specialEnabled[3]
        self.canvasGraph.updateCharts()

    
    def guiSetup(self):

        import sys
        # This happens in case of running as PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.daqIdeaFilePath = getattr(sys, '_MEIPASS', '.') + '\\src'
        else:
            self.daqIdeaFilePath = os.path.abspath(os.path.dirname(sys.argv[0]))

        # Main
        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.mainLayout = QtWidgets.QVBoxLayout(self.main_widget)

        # Menus
        self.createMenu()

        # Entire GUI with chart, variables and control
        self.createMainGroup(self.mainLayout)

        # Status bar
        self.statusBar().showMessage("", 0)

        # Other global details of the window frame
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setGeometry(100, 100, 1400, 800)

        self.setWindowIcon(QtGui.QIcon(self.daqIdeaFilePath + '\\..\\resources\\icons\\daqIDEA.png'))

    def loadUserData(self):
        return self.userData.loadUserData(variableConfiguration.strUserDaqIdeaFilePath)

    def loadStartConfiguration(self):
        fileName = None
        if len(sys.argv) >= 2:
            fileName = sys.argv[1]

        # No file name was specified in cmd line
        if fileName == None or len(fileName.strip()) == 0:
            self.daqIdeaConfig = variableConfiguration.loadDefaultConfiguration()
        else:
            self.daqIdeaConfig = variableConfiguration.loadConfigurationFile(fileName)

        if self.daqIdeaConfig == None:
            self.daqIdeaConfig = variableConfiguration.ApplicationConfiguration()

        self.updateWindowTitle()

    def isConfigurationChanged(self):
        fileName = self.getConfigurationFileName()
        activeConfigStr = variableConfiguration.getConfigurationAsText(
            self.daqIdeaConfig)
        savedConfigStr = variableConfiguration.getSavedConfigurationAsText(
            fileName)
        return (activeConfigStr != savedConfigStr)

    def closeEvent(self, event):
        if self.daqManager != None:
            self.daqManager.stopSampling()

        if len(self.daqIdeaConfig.variableConfigs) > 0:

            if self.isConfigurationChanged():
                reply = QtWidgets.QMessageBox.question(self,
                                                       'Save Configuration',
                                                       "Would you like to save the current configuration before exiting daqIDEA?",
                                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                                                       QtWidgets.QMessageBox.Cancel)

                if reply == QtWidgets.QMessageBox.Yes:
                    fileName = self.getConfigurationFileName()
                    variableConfiguration.saveConfigurationFile(fileName, self.daqIdeaConfig)

                elif reply == QtWidgets.QMessageBox.Cancel:
                    event.ignore()

    def fileQuit(self):
        self.canvasGraph.stopAnimation()
        self.close()

    def about(self):
        QtWidgets.QMessageBox.about(self, "About",
                                    """
iSYSTEM daqIDEA
"""
                                    )

    def help(self):
        import webbrowser
        webbrowser.open('https://www.isystem.com/downloads/winIDEA/help/daqidea.html')

    def configureDaqController(self):
        self.dataTable.model().beginResetModel()

        cfg = self.daqIdeaConfig.variableConfigs
        wasConfigured = self.daqManager.startSampling(cfg)

        if (wasConfigured):
            self.setVariableValidityStatus('black', '')
        else:
            if None != self.daqManager.lastErrorMsg:
                self.setVariableValidityStatus('red', self.daqManager.lastErrorMsg)
            else:
                self.setVariableValidityStatus('red', "DAQ Initialization failed.")

        self.dataTable.model().endResetModel()

        return wasConfigured



class DownloadSignal(QtCore.QObject):
    downloaded = QtCore.Signal(str)



class DownloadThread(QtCore.QThread):

    debug = None
    ideCtrl = None
    signal = None

    def __init__(self, dbg, ide, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.debug = dbg
        self.ideCtrl = ide
        self.signal = DownloadSignal()

    def run(self):
        if self.debug != None:
            self.ideCtrl.restore()
            self.ideCtrl.bringWinIDEAToTop()
            try:
                self.debug.download()
            except:
                return
            self.signal.downloaded.emit('Downloaded')

def displayArguments(args):
    logging.info("Program argument count: %d" % len(args))
    for i in range(len(args)):
        logging.info(" - arg[%d] = '%s'" % (i, args[i]))

def main():
    global mainApplicationWindow

    displayArguments(sys.argv)

    try:
        #
        # Start Application
        #
        logging.info('Creating application window... ')
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        application = QtWidgets.QApplication(sys.argv)
        # application.setStyle("plastique")

        globals.mainApplicationWindow = ApplicationWindow()
        logging.info('Done.')

        logging.info('Starting iConnect...')
        cmgr = ic.ConnectionMgr()
        logging.info('Connecting to winIDEA...')
        cmgr.connectMRU('')
        ideCtrl = ic.CIDEController(cmgr)
        logging.info('winIDEA version: %s'%(ideCtrl.getWinIDEAVersion().toString()))
        variableConfiguration.strwinIDEAWorkspaceDir = ideCtrl.getPath(ic.CIDEController.WORKSPACE_DIR)
        debug = ic.CDebugFacade(cmgr)
        logging.info('Initializing GUI...')
        globals.mainApplicationWindow.setWinIdeaConfig(cmgr, debug)
        globals.mainApplicationWindow.loadUserData()
        globals.mainApplicationWindow.loadStartConfiguration()
        globals.mainApplicationWindow.guiSetup()
        logging.info('Starting winIDEA Synch...')
        globals.mainApplicationWindow.startWinIdeaSynch()

        logging.info('Opening main window.')
        globals.mainApplicationWindow.show()
        logging.info('done')

        sys.exit(application.exec_())
    except Exception as e:
        logging.exception(e)

        title = "daqIDEA encountered a problem."
        msg = str(e) + "\n\n See log file at: " + globals.daqIdeaLogFile
        globals.getTkInterMsgDialogInstance().showerror(title, msg)


if __name__ == '__main__':
    # cProfile.run('main()')
    main()

