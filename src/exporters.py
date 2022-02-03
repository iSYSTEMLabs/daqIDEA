
from __future__ import print_function

import openpyxl
from openpyxl.styles.colors import Color

lastDataExportFile = None

def exportToExcel(app, fileName, dataModel, varNames):
    global lastDataExportFile

    book = openpyxl.Workbook(write_only = True)
    sheet = book.create_sheet()
    sheet.title = 'Variables'

    rowCount = dataModel.getRowCount()
    columnCount = dataModel.getColumnCount()
    
    varNames = []
    for c in range(columnCount):
        varNames.append(dataModel.getHorizontalHeaderName(c))
    sheet.append(varNames)
    
    for r in range(rowCount):
        values = []
        for c in range(columnCount):
            value = dataModel.getData(r, c)
            values.append(value)
        sheet.append(values)
    
    book.save(fileName)
    
    lastDataExportFile = fileName


def exportToCharSeparatedValues(fileName, datax, datay, separator, varNames, bFillInMissingValues):
    global lastDataExportFile

    # Open file
    f = open(fileName, 'w')

    # Add header
    f.write('Time [s]')
    for n in varNames:
        f.write(separator + n)
    #f.write('\n')
    
    # Organize data for writing
    lastValues = []
    allTimes = []
    for i in range(0, len(datax)):
        allTimes.extend(datax[i])
        lastValues.append(datay[i][0])
    
    allTimes = sorted(list(set(allTimes)))
            
    # For every timestamp X write a row
    for t in allTimes:
        f.write('\n')

        f.write(str(t))
        val = None
        
        # Find the time in every variables Y data list
        for di in range(0, len(datax)):
            strVal = ""
            if t in datax[di]:
                idx = datax[di].index(t)
                
                val = datay[di][idx]
                lastValues[di] = val
                strVal = str(val)
            else:
                if bFillInMissingValues:
                    val = lastValues[di]
                    strVal = str(val)

            f.write(separator + strVal)
    f.close()
    
    lastDataExportFile = fileName

    
    