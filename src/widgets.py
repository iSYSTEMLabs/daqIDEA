

from __future__ import print_function

from PyQt5 import QtCore, QtGui, QtWidgets

from math import *

import globals, daqIO, variable

class DaqItemDelegate(QtWidgets.QStyledItemDelegate):
    
    parent = None
    dataModel = None
    bIsAdaptiveTimeUnit = True

    def __init__(self, parent, dataModel):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)
        self.parent = parent
        self.dataModel = dataModel

    def setAdaptiveTimeUnit(self, bIsAdaptiveTimeUnit):
        self.bIsAdaptiveTimeUnit = bIsAdaptiveTimeUnit

    def getTimeUnit(self, dTime):
        aUnits = ['s', 'ms', 'us', 'ns']
        nUnit = 0
        if (dTime >= 0):
            while (dTime < 1 and nUnit + 1 < len(aUnits)):
              dTime *= 1000
              nUnit += 1
        return dTime, aUnits[nUnit]

    def paint(self, painter, option, index):
        if index.column() == 0:
            color = QtGui.QColor(0, 0, 0, 255)
        else:
            varIdx = self.dataModel.enabledVars[index.column()-1]
            var = self.parent.daqIdeaConfig.variableConfigs[varIdx]
            daqIdx = var.daqConfigIndex
            
            realValue = self.parent.daqManager.isRealValue(index.row(), daqIdx)
        
            if realValue:
                color = QtGui.QColor(0, 0, 0, 255)
            else:
                color = QtGui.QColor(0, 0, 0, 127)
         
        option.palette.setColor(QtGui.QPalette.Text, color)
        
        if index.column() == 0:
            strTime = None
            dTime = self.dataModel.getData(index.row(), index.column())
            if self.bIsAdaptiveTimeUnit:
                strUnit = None
                dTime, strUnit = self.getTimeUnit(dTime)
                strTime = "{:.4f} {}".format(dTime, strUnit)
            else:
                strTime = "{:10.6f}".format(dTime)

            option.rect.setWidth(option.rect.width() - 3)
            painter.drawText(option.rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignCenter, strTime);
        else:
            return QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)
    
    
class DaqTableModel(QtCore.QAbstractTableModel):
    
    parent = None
    enabledVars = []
    dataModelFull = True
    strTimeUnit = None

    def __init__(self, parent, daqCfg, *args):
        QtCore.QAbstractTableModel.__init__(self, parent, *args)
        self.parent = parent

    def rowCount(self, parent):
        return self.getRowCount() 
    
    def getRowCount(self):
        return len(self.parent.daqManager.allTimePoints)
    
    def columnCount(self, parent):
        return self.getColumnCount()
        
    def getColumnCount(self):
        return len(self.enabledVars) + 1

    def data(self, index, role):
        if (self.parent.daqManager.wasConfigured  and 
            index.isValid()  and  
            role == QtCore.Qt.DisplayRole):

            r = index.row()
            c = index.column()

            return self.getData(r, c)
        else:
            return None
                
    def getData(self, r, c):
        if (c == 0):
            return self.parent.daqManager.allTimePoints[r]
        else:
            varIdx = self.enabledVars[c-1]
            var = self.parent.daqIdeaConfig.variableConfigs[varIdx]
            daqIdx = var.daqConfigIndex
            
            if (daqIdx >= 0):
                daq = self.parent.daqManager
                
                varType = self.parent.daqManager.getVariableByName(var.name)
                if varType == None:
                    return 'N/A'
                
                if (not self.dataModelFull) and (not daq.isRealValue(r, daqIdx)):
                    return ''
                
                if (varType != None  and  
                    varType.simpleType == variable.TYPE_IO  and  
                    varType.portType == daqIO.HIL_AIN):
                    
                    formater = '{0:f}'
                    return formater.format(daq.getEstimatedValue(r, daqIdx))
                else:
                    formater = globals.formatterStrings[var.format]
                    return formater.format(daq.getEstimatedValue(r, daqIdx))
            else:
                return 'N/A'
    
    
    def headerData(self, idx, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.getHorizontalHeaderName(idx)
            elif orientation == QtCore.Qt.Vertical:
                return self.getVerticalHeaderName(idx)
        else:
            return None
            
    def setTimeUnit(self, strUnit):
        self.strTimeUnit = strUnit

    def getHorizontalHeaderName(self, column):
        if column == 0:
            strColumn = 'Time'
            if None != self.strTimeUnit:
                strColumn = 'Time [{}]'.format(self.strTimeUnit)
            return strColumn
        else:
            varIdx = self.enabledVars[column-1]
            return self.parent.daqIdeaConfig.variableConfigs[varIdx].name
        
    def getVerticalHeaderName(self, row):
        return row + 1
    
    def isRealValue(self, row, column):
        if (column == 0):
            return True
        else:
            varIdx = self.enabledVars[column-1]
            var = self.parent.daqIdeaConfig.variableConfigs[varIdx]
            daqIdx = var.daqConfigIndex
            
            if (daqIdx >= 0):
                return self.parent.daqManager.isRealValue(row, daqIdx)
            else:
                return 'N/A'

    def setDataModelEstimation(self, full):
        self.dataModelFull = full

    # If the DAQ was reconfigured then we should call this
    def updateDataModel(self):
        # Checks which variables are used (excluding the disabled ones)
        newVars = []
        for idx, var in enumerate(self.parent.daqIdeaConfig.variableConfigs):
            if var.enabled:
                newVars.append(idx)
                
        self.beginResetModel()
        self.enabledVars = newVars
        self.endResetModel()
                
        self.updateFormatting()

        
    def updateFormatting(self):
        rc = len(self.parent.daqManager.allTimePoints)
        
        if (rc > 0):            
            for rowIdx, varConfig in enumerate(self.parent.daqIdeaConfig.variableConfigs):
                self.beginRemoveRows(QtCore.QModelIndex(), 0, rc-1)
                self.endRemoveRows()

                self.beginInsertRows(QtCore.QModelIndex(), 0, rc-1);
                self.endInsertRows()
                    

class VariableChooserCombo(QtWidgets.QComboBox):
    
    parent = None
    variables = []
    allFullNames = None
    completer = None
    lastText = None
    
    selectedVariable = None
    variableConfig = None
    
    itemsSet = None
    
    comboDeleted = False
    
    def __init__(self, p, varCfg):
        QtWidgets.QComboBox.__init__(self, p)
        self.parent = p
        self.variableConfig = varCfg
        self.itemsSet = False
    
    def setVariables(self, vars):
        self.variables = vars
        self.allFullNames = []
        
        for var in self.variables:
            self.allFullNames.append(var.fullName)
        
        self.allFullNames = sorted(self.allFullNames)
            
        self.clear()
        self.addItems(self.allFullNames)
        self.setEditable(True)
        
        self.completer = QtWidgets.QCompleter(self.allFullNames, self.parent)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)
        self.completer.setModelSorting(QtWidgets.QCompleter.CaseSensitivelySortedModel)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        
        self.completer.setMaxVisibleItems(20)
        
        self.setCompleter(self.completer)

        
        # variables with complexity of *name[3][4]        
        #rx = QtCore.QRegExp("\*?[A-Za-z_][A-Za-z0-9_]*((\[\d{1,4}\])|(\[\]))*")
        
        '''
        rx = QtCore.QRegExp("(([A-Za-z_]" + # var start char
                            "[A-Za-z0-9_]*" + # rest of chars
                            "(\[\d{0,4}\])*)" + # array indices
                            "(,,[A-Za-z0-9_\-\.\\ ]+))|" +
                            "(0x[0-9a-fA-F]{0,8})" # or just plain hex memory address
                            )
        
        v = QtGui.QRegExpValidator(rx)
        self.setValidator(v)
        ''' 
        self.itemsSet = True
        
        # New config
        if (len(self.variableConfig.name) <= 0):
            self.setCurrentIndex(0)
            
            self.parent.setVariableValidityStatus('black', 'Please select variable name for each row inside of variable table!')
        else:
            self.setEditText(self.variableConfig.name)
        
    
    def event(self, event):
        QtWidgets.QComboBox.event(self, event)
        
        if self.comboDeleted:
            return True
        
        if (not self.itemsSet):
            return True
        
        old = str(self.lastText)
        new = str(self.currentText())
        
        if (old != new):
            self.lastText = new
            self.variableConfig.name = new
            
            
            oldVar = self.variableConfig.variable
            try:
                newVar = self.parent.daqManager.getVariableByName(new)
            except:
                newVar = None
            
            if (newVar != None  and 
                newVar != oldVar):
                self.variableConfig.variable = newVar
                
                if (oldVar == None  or
                    newVar.formatters != oldVar.formatters):
                    self.variableConfig.updateFormatterComboBox()
            
            self.parent.checkAllVariablesValidity()
        
        return True
    
    
    def removing(self):
        self.comboDeleted = True

        
    # Count how many first characters are equal in both strings
    def countCharMatch(self, s1, s2):
        c = min(len(s1), len(s2))
        res = 0;
        for i in range(0, c):
            if (s1[res] == s2[res]):
                res += 1
                
        return res



class DeleteButton(QtWidgets.QPushButton):
    
    myParent = None
    varConfig = None

    def __init__(self, parent, varCfg):
        QtWidgets.QPushButton.__init__(self)
        self.myParent = parent
        self.varConfig = varCfg
        self.clicked.connect(self.deleteButtonClick)

    def deleteButtonClick(self):
        # find the button that called this delete event
        configs = self.myParent.daqIdeaConfig.variableConfigs
        varIdx = configs.index(self.varConfig)

        if (varIdx >= 0):
            configs.pop(varIdx)
            
            self.myParent.variableTable.cellWidget(varIdx, globals.TABLE_COLUMN_NAME).removing()
            self.myParent.variableTable.removeRow(varIdx)
            self.myParent.canvasGraph.updateChartSubplots()
            self.myParent.checkAllVariablesValidity()
           


class ColorButton(QtWidgets.QPushButton):
    
    myParent = None
    variableConfig = None

    def __init__(self, parent, varCfg):
        QtWidgets.QPushButton.__init__(self)
        self.myParent = parent
        self.variableConfig = varCfg
        
        self.clicked.connect(self.colorButtonClick)

    def colorButtonClick(self):

        oldc = self.variableConfig.color
        r = (oldc >> 16) & 0xff
        g = (oldc >> 8) & 0xff
        b = oldc & 0xff
        
        c = QtGui.QColor(r, g, b)
        res = QtWidgets.QColorDialog.getColor(c)
        
        if (res.value() != 0):
            newc = (res.red() << 16) + (res.green() << 8) + res.blue() 
            
            if  (newc != oldc):
                self.variableConfig.color = newc
                self.variableConfig.floatColor = (res.red()/255.0, res.green()/255.0, res.blue()/255.0)
                self.updateIcon()
                
                if (not self.myParent.canvasGraph.isAnimationRunning()):
                    self.myParent.canvasGraph.updateCharts()


    def updateIcon(self):
        c = self.variableConfig.color
        color = QtGui.QColor((c >> 16) & 0xff, (c >> 8) & 0xff, c & 0xff, 0xff)

        pixmap = QtGui.QPixmap(40, 40)
        pixmap.fill(color)
        icon = QtGui.QIcon(pixmap)
        self.setIcon(icon)


class ScaleSpinner(QtWidgets.QSpinBox):
    
    myParent = None
    lastValue = None
    sign = None
    variableConfig = None
    
    def __init__(self, parent, varCfg):
        global spinnerCount
        
        QtWidgets.QSpinBox.__init__(self)
        self.myParent = parent
        self.variableConfig = varCfg

        self.setWrapping(True)
        self.setRange(-9, 9)
        self.setPrefix('1e')
        self.setValue(0)
        self.lastValue = 0
        self.sign = 1
        
        self.valueChanged.connect(self.valChanged)
        
    def valChanged(self):
        self.valueChanged.disconnect(self.valChanged)

        old = self.lastValue
        new = self.value()
        
        if ((old == 9  and  new == -9) or 
            (old == -9  and  new == 9)):
            self.sign *= -1
            self.setPrefix(str(int(self.sign))+'e')
        
        self.lastValue = new
        self.valueChanged.connect(self.valChanged)
        
        self.variableConfig.scale = self.getMultiplicator()
    
    def getMultiplicator(self):
        return self.sign * (10**self.value())
    
    def setMultiplicator(self, m):
        
        if (m < 0.0):
            self.sign = -1
            self.setPrefix('-1e')
        else:
            self.sign = 1
            self.setPrefix('1e')
        
        self.setValue(int(round(log(self.sign*m, 10))))
