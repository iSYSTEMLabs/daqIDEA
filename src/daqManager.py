
from __future__ import print_function

import sys, csv, time, random, bisect
import logging

from math import *
from PyQt5 import QtCore
import isystem.connect as ic
import daqIO, variable

import threading

try:
    import pylab as plab
    isPyLabInstalled = True
except ImportError as ex:
    isPyLabInstalled = False

# In Python 3 the module Queue was renamed to queue
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

class DaqManager():
    
    allVariables = []
    qNameVariableMap = []
    variableMap = dict()

    selectedNames = []
    
    sampleQueue = Queue()
    sampleReaderThread = None
    
    datax = None
    datay = None
    allTimePoints = None

    daqCtrl = None
    dataCtrl = None
    hilCtrl = None
    memCtrl = None
    wasConfigured = False
    
    daqTimeStart = None
    daqTimeFactor = 0
    
    lastTimeFound = None
    lastIndexFound = None
    lastRowFound = None

    lastMinIndex = None
    lastMaxIndex = None

    lastErrorMsg = None
    
    
    def __init__(self, cmgr):
        try:
            self.daqCtrl = ic.CDAQController(cmgr)
            self.dataCtrl = ic.CDataController2(cmgr)
            self.hilCtrl = ic.CHILController(cmgr)
            self.ideCtrl = ic.CIDEController(cmgr)
            self.memCtrl = ic.CAddressController(cmgr)
            self.cfgCtrl = ic.CConfigurationController(cmgr)

        except  Exception as e:
            logging.error("Failed to initialize iConnect data controller!")
            logging.exception(e)

        self.resetPlotData(0)

        self.initVariableNamesList()
     
     
     
    def getTimeSinceStart(self):
        nowTime = self.daqCtrl.status().getTime() 
        return (nowTime * self.daqTimeFactor) - self.daqTimeStart
        
        
        
    def initVariableNamesList(self):
        logging.info("Loading variable names:")
        
        defaultPartition = self.ideCtrl.getOptionInt('/IDE/Debug.DownloadFiles.DefaultFile')

        paths = ic.StrVector()
        dlFileNames = ic.StrVector()
        self.dataCtrl.getPartitions(paths, dlFileNames)
        
        self.allVariables = []
        self.variableMap = dict()
        self.qNameVariableMap = dict()
        
        #
        # Add all variables from all partitions
        #
        # Variables are inside a map by name. Variables that exist
        # in other DL file that the primary must be referenced by
        # their qualified name or at least "var,,dl.elf"  
        logging.info("Download file count: %d"%(dlFileNames.size()))
        
        for partitionIdx in range(dlFileNames.size()):
            dlFileName = dlFileNames[partitionIdx]
            logging.info("File %s"%(dlFileName))
            dlFilePath = paths[partitionIdx]
            
            vars = ic.VariableVector()
            self.dataCtrl.getVariables(partitionIdx, vars)
            logging.info("Variable count: %d"%(vars.size()))
            for var in vars:
                try:
                    name = var.getName()
                    type = var.getType()
                    logging.info("\tloading var '%s %s'"%(type, name))
                    if partitionIdx == defaultPartition:
                        newVar = variable.DaqVariable.fromVariable(name, None, type, self.dataCtrl)
                    else:
                        newVar = variable.DaqVariable.fromVariable(name, dlFileName, type, self.dataCtrl)
                    self.allVariables.append(newVar)
                    
                    if partitionIdx == defaultPartition:
                        #print ("Adding to map '%s'"%(newVar.name))
                        self.variableMap[newVar.name] = newVar
                    #print ("Adding to qMap '%s'"%(newVar.fullName))
                    self.qNameVariableMap[newVar.fullName] = newVar
                except:
                    logging.warn("Failed to load variable '%s' details"%(name))
        
        #
        # Add I/O hil channels
        #

        if daqIO.HIL_ENABLED:
            hilPorts = daqIO.getHilPorts(self.hilCtrl)
        
            for port in hilPorts:
                if (port.isAvailable()  and  
                    (port.getType() == daqIO.HIL_DIN  or  port.getType() == daqIO.HIL_AIN)):
                
                    name = port.getName()
                    type = port.getType()
                    index = port.getIndex()
                
                    newVar = variable.DaqVariable.fromPort(name, type, index)
                    logging.info("\tLoading HIL %s Type %s Idx %s", name, type, index)
                  
                    self.allVariables.append(newVar)
                    self.variableMap[newVar.name] = newVar
        
        newVar = variable.DaqVariable.fromMemAddress(0x00000000)
        self.allVariables.append(newVar)
        self.variableMap[newVar.name] = newVar


    def isDaqConfigured(self):
        return self.wasConfigured
    
    
    def getVariables(self):
        return self.allVariables
    
    
    def getSelectedVariableNames(self):
        return self.selectedNames
                

    # Gets new variable from data controller
    def loadNewVariable(self, name):
        print ("Looking for new variable '%s'"%name)
        
        partitionName = None
        if (',,' in name):
            partIdx = name.index(',,')
            partitionName = name[partIdx+2:]
        
        optCtrl = self.cfgCtrl.ide_app()
        defaultPartitionIdx = optCtrl.get_int("SymbolFiles.DefaultFile")
        partitions = self.dataCtrl.getConfiguration(0).Partitions()
        defaultPartition = partitions.at(defaultPartitionIdx)

        try:
            exprType = self.dataCtrl.getExpressionType(0, name)
        except:
            return None
            
        expression = exprType.Expression()
        qName = expression.QualifiedName()
        type = expression.TypeName()
        print("New expression type: (%s, %s, %s, %s)"%(name, qName, type, partitionName))
        
        # With or without partition name
        newVar = None
        if (None == defaultPartition  or  None == partitionName  or  defaultPartition.Name() == partitionName):
            newVar = variable.DaqVariable.fromVariable(name, None, type, self.dataCtrl)
            self.variableMap[newVar.name] = newVar
        else:
            newVar = variable.DaqVariable.fromVariable(name, partitionName, type, self.dataCtrl)

        self.qNameVariableMap[newVar.fullName] = newVar
        
        self.dataCtrl.release(exprType)
        return newVar

 
    def getVariableByName(self, name):
        #if ('[' in name):
        #    name = name[:name.index('[')]
            
        if (name.startswith('0x')):
            name = '0x'
        
        if name in self.variableMap:
            return self.variableMap[name]
        else:
            if name in self.qNameVariableMap:
                return self.qNameVariableMap[name]
            else:
                # We get a new variable (used in case of 
                # structures or unions...)
                return self.loadNewVariable(name)

    def resetPlotData(self, variableCount):
        self.datax = []
        self.datay = []
        self.allTimePoints = []
        self.lastTimeFound = [0]*variableCount
        self.lastIndexFound = [0]*variableCount
        self.lastRows = [-10]*variableCount
        
        for i in range(0, variableCount):
            self.datax.append([])
            self.datay.append([])

    def checkDAQControllerAvailability(self):
        import globals

        bIsAvailable = True
        try:
            daqInfo = self.daqCtrl.info()
        except:
            bIsAvailable = False

        if daqInfo.getMaxItems() == 0:
            bIsAvailable = False

        if not bIsAvailable:
            strTitle = "Data Acquisition (DAQ)"
            strIsDemo = self.ideCtrl.getOptionStr('/IDE/Asyst.Demo')
            if 'true' == strIsDemo:
                strMsg = "Data Acquisition (DAQ) system is not available while winIDEA is in Demo Mode."
            else:
                strMsg = "Data Acquisition (DAQ) system is not available."
            globals.getTkInterMsgDialogInstance().showerror(strTitle, strMsg)

        return bIsAvailable

    # Array of elements [name, interval] 
    def startSampling(self, config):
        from datetime import datetime
        logging.info("Configuring DAQ @ %s"%(str(datetime.now())))
        
        self.selectedNames = []
        self.lastSampleTimes = []
        self.firstSampleRed = False
        self.firstSampleTime = 0

        if not self.checkDAQControllerAvailability():
            return
        
        # Calculate the factor for time in order to display time in seconds.
        # (DAQ methods return times in DAQ clock ticks).
        daqInfo = self.daqCtrl.info()
        self.daqTimeFactor = daqInfo.getTick_ns() / 1000000000.0

        # reset the DAQ configuration
        self.daqCtrl.configReset()

        self.lastErrorMsg = None

        nCfgIdx = 0
        vecDAQConfig = ic.DAQConfigVector();
        for varConfig in config:
            varConfig.daqConfigIndex = -1
            if (varConfig.enabled):
                logging.info("Variable: %s"%(varConfig.name))
                
                if varConfig.variable == None:
                    if not daqIO.HIL_ENABLED and varConfig.name[0] == '`':
                        self.lastErrorMsg = "HIL Channels not supported: " + varConfig.name
                    else:
                        self.lastErrorMsg = "Unknown variable: '" + varConfig.name + "'"
                    return False

                try:
                    varInfo = self.memCtrl.getSymbolInfo(ic.IConnectDebug.fMonitor | ic.IConnectDebug.gafExpression, varConfig.name)
                    varType = varInfo.getMType()
                    if not varType.m_byType in [ic.SType.tUnsigned, ic.SType.tSigned, ic.SType.tFloat]: 
                        self.lastErrorMsg = "Only simple types allowed for sampling: '{}'".format(varConfig.name)
                        return False
                except:
                    self.lastErrorMsg = "Could not evaluate expression: '{}'".format(varConfig.name)
                    return False
        
                daqConfigItem = None
                var = varConfig.variable
                strVarName = varConfig.name
                t = varConfig.samplingTimeInterval
                
                self.selectedNames.append(strVarName)
                                
                if var.simpleType == variable.TYPE_MEM_ADDR:
                    try:
                        addr = int(strVarName, 0)
                    except ValueError as err:
                        self.lastErrorMsg = "Invalid memory address '" + strVarName +"'"
                        logging.error(self.lastErrorMsg)
                        logging.exception(err)
                        return False
                    daqConfigItem = ic.CDAQConfigItem(4, 0, addr, t)
                # ADIO disabled for DAQController so this code was not ported
                #elif daqIO.HIL_ENABLED and var.simpleType == variable.TYPE_IO:
                #    if var.portType == daqIO.HIL_DIN:
                #        varConfig.daqConfigIndex = self.daqCtrl.configAddDIN(var.portBit, t);
                #    elif var.portType == daqIO.HIL_AIN:
                #        varConfig.daqConfigIndex = self.daqCtrl.configAddAIN(var.portBit, True, t);
                else:
                    try:
                        self.memCtrl.getExpressionAddress(strVarName)
                    except:
                        self.lastErrorMsg = "Can't find variable '{}'.".format(strVarName)
                        return False
                        
                    daqConfigItem = ic.CDAQConfigItem(strVarName, t)

                if None == daqConfigItem:
                    self.lastErrorMsg = "Failed to add configuration item '{}'.".format(strVarName)
                    return False

                vecDAQConfig.append(daqConfigItem)
                varConfig.daqConfigIndex = nCfgIdx
                nCfgIdx += 1

        try:
          self.daqCtrl.configure(vecDAQConfig)
        except Exception as ex:
          self.lastErrorMsg = "Failed to configure DAQ Controller using the given variables."
          logging.info("Exception caught: ", ex)
          return False;

        self.resetPlotData(len(config))
        self.resetDownsampleMetadata(len(config))
        
        if not self.checkDAQControllerAvailability():
            return
        
        self.daqCtrl.enableGlobal(True)

        # Get time 0
        daqStatus = self.daqCtrl.status()
        self.daqTimeStart = daqStatus.getTime() * self.daqTimeFactor
    
        # Get initial values at chart draw time point ZERO
        for i, varConfig in enumerate(config):
            if (varConfig.enabled):
                var = varConfig.variable
                
                if (len(self.datax[i]) == 0):
                    time = 0;
                    value = self.getInitialValue(varConfig)

                    self.datax[i].append(time)
                    self.datay[i].append(value)
        
        # Manually set the time point 0 for the initial values
        self.allTimePoints.append(0)
        
        #
        # Create the thread for reading sample data out of the DAQ queue
        # and start it
        #
        self.sampleReaderThread = DaqWorkerThread(self)
        self.sampleReaderThread.start()

        # Set the configured flag
        self.wasConfigured = True
        
        logging.info("Sampling started")
        
        return True
    
    '''
    def prependFakeData(self, x, y, count, time):
        
        time = float(time)
        t1 = time*0.25
        t2 = time*0.75
        
        x.extend([0]*count)
        y.extend([0]*count)
        
        x[0] = -time
        y[0] = 500
        
        for i in range(1, count-1):
            x[i] = t1 + ((t2-t1)/count)*i - time
            y[i] = 500 + random.randint(-20, 20) + 50*sin(15.0*i/count)

        x[-1] = 0
        y[-1] = 500
    '''
   
    def getInitialValue(self, varConfig):
        
        daqStatus = self.daqCtrl.status()
        
        ## Get initial value for every data variable
        #t0 = daqStatus.getTime()
            
        val = None
        
        try:
            if (varConfig.variable.simpleType == variable.TYPE_MEM_ADDR):
                # If a memory location was set
                addr = int(varConfig.name, 16)
                
                varType = ic.SType()
                varType.m_byBitSize = 32
                varType.m_byType = ic.SType.tSigned
                
                res = self.dataCtrl.readValue(ic.IConnectDebug.fMonitor | 
                                              ic.IConnectDebug.fRealTime
                                              , 0, addr, varType)
            else:
                res = self.dataCtrl.evaluate(ic.IConnectDebug.fRealTime, varConfig.name)

            if res.isTypeCompound() or res.isTypeAddress():
                val = 0
            elif res.isTypeFloat():
                val = res.getDouble()
            elif res.isTypeSigned  or  res.isTypeUnsigned():
                val = res.getLong()
            
            logging.info('Initial value for {} = {}'.format(varConfig.name, val))

        except:
            logging.error('Reading initial value for %s failed:'%(varConfig.name))        
            val = 0 
        
        return val
        
        
    def queueSamplingData(self):
        daqStatus = self.daqCtrl.status()

        # if any sample is available, display the status and print the samples  
        if daqStatus.getNumSamplesAvailable() > 0:
            if daqStatus.getOverflow():
                logging.warning('SAMPLING OVERFLOW!')  

            # read available samples into daqSamples
            daqSamples = ic.DAQSampleVector()
            self.daqCtrl.read(daqSamples)
            
            for daqSample in daqSamples:
                varIndex = daqSample.getIndex()
                sampleTime = daqSample.getTime()
                t = self.daqCtrl.getDataValue(daqSample)
                
                bIsValid = True
                sampleValue = 0
                if t.isTypeSigned() or t.isTypeUnsigned():
                    sampleValue = t.getLong()
                elif t.isTypeFloat():
                    dVal = t.getDouble()
                    if (float('inf') == dVal):
                        sampleValue = 0
                        bIsValid = False
                    else:
                        sampleValue = dVal
                    
                if bIsValid:
                    row = [varIndex, sampleTime, sampleValue]
                    self.sampleQueue.put(row)

    #
    # Updates the datax and datay data arrays with the newest sampling data
    # available
    #
    def deQueueSamplingData(self, tableDataModel):
        allNewTimePoints = [self.allTimePoints[-1]]
        
        # First get all the newest data
        while (not self.sampleQueue.empty()):
            row = self.sampleQueue.get()
            varIdx = row[0]
            sampleTime = row[1] * self.daqTimeFactor - self.daqTimeStart
            sampleValue = row[2]
            
            self.datax[varIdx].append(sampleTime)
            self.datay[varIdx].append(sampleValue)
            
            #if (sampleTime > self.allTimePoints[-1]):
            #    self.allTimePoints.append(sampleTime)
            
            if (sampleTime > allNewTimePoints[-1]):
                allNewTimePoints.append(sampleTime)

        if len(allNewTimePoints) > 1:
            # First and last edited line
            i1 = len(self.allTimePoints) - 1
            i2 = i1 + len(allNewTimePoints) - 1

            # WE will have to change the last existing row if data was added 
            # to it            
            tableDataModel.beginRemoveRows(QtCore.QModelIndex(), i1, i1)
            tableDataModel.endRemoveRows()
            
            # We add new data rows to the table data model
            tableDataModel.beginInsertRows(QtCore.QModelIndex(), i1, i2);
            self.allTimePoints.extend(allNewTimePoints[1:])
            tableDataModel.endInsertRows()


    def resetDownsampleMetadata(self, varCount):
        self.lastMinIndex = [None]*varCount
        self.lastMaxIndex = [None]*varCount


    #
    # Writes the data in the time interval to the x and y arrays
    #        
    def getRawPlotData(self, varIndex, minTime, maxTime, scaleFactor):
        
        x = self.datax[varIndex] 
        y = self.datay[varIndex]

        # Take the last displayed time interval and update it according to 
        # the new interval
        
        left = self.lastMinIndex[varIndex]
        if (left == None):
            left = 0

        right = self.lastMaxIndex[varIndex]
        if (right == None):
            right = len(x)-1

        # Expand left and right bounds                   
        while (left > 0) and (x[left] > minTime):
            left -= 1
        while (right < len(x)) and (x[right] < maxTime):
            right += 1

        # Shrink left and right bounds
        while (left+1 < len(x)) and (x[left+1] < minTime):
            left += 1
        while (right-1 >= 0) and (x[right-1] > maxTime):
            right -= 1

        x = x[left:right+1]
        y = y[left:right+1]
        
        if (scaleFactor != 1):
            y = [e * scaleFactor for e in y] 
        
        self.lastMinIndex[varIndex] = left
        self.lastMaxIndex[varIndex] = right
        
        return x, y


    def getAdjustedTimeSlices(self, reqTimeStart, reqTimeEnd, reqSliceCount, debug = False):
        
        reqTimeStart = float(reqTimeStart)
        reqTimeEnd = float(reqTimeEnd)
        
        if (debug):
            print('getAdjustedTimeSlices(', reqTimeStart, ', ', reqTimeEnd, ', ', reqSliceCount, ')')
        
        reqDt = reqTimeEnd - reqTimeStart
        if (debug):
            print('reqDt = ', reqDt)
    
        reqMaxSliceWidth = reqDt / reqSliceCount
        if (debug):
            print('reqMaxSliceWidth = ', reqMaxSliceWidth)
            print('------------------')
        #
        # CALCULATE
        #
        
        maxSliceWidth2n = 2**floor(log(reqMaxSliceWidth, 2))
        if (debug):
            print('maxSliceWidth2n = ', maxSliceWidth2n)
    
        minSlotCount = reqDt / maxSliceWidth2n
        if (debug):
            print('### min slot count = ', minSlotCount)
        
        sliceCount2n = 2**ceil(log(minSlotCount, 2))
        if (debug):
            print('sliceCount2n = ', sliceCount2n)
        
        viewWidth2n = sliceCount2n * maxSliceWidth2n
        if (debug):
            print('viewWidth2n = ', viewWidth2n)
    
        maxTimeStart2n = floor(reqTimeStart / maxSliceWidth2n) * maxSliceWidth2n
        if (debug):
            print('maxTimeStart2n = ', maxTimeStart2n)
    
        minTimeEnd2n = ceil(reqTimeEnd / maxSliceWidth2n) * maxSliceWidth2n
        if (debug):
            print('minTimeEnd2n = ', minTimeEnd2n)
        
        sliceCount = (minTimeEnd2n - maxTimeStart2n) / maxSliceWidth2n
        if (debug):
            print('sliceCount = ', sliceCount)
        
        sliceCount2n = 2**(floor(log(sliceCount, 2))+1)
        if (debug):
            print('sliceCount2n = ', sliceCount2n)
        
        leftAdd = (sliceCount2n - sliceCount) // 2
        rightAdd = sliceCount2n - sliceCount - leftAdd
        if (debug):
            print('adding left = ', leftAdd, ', adding right = ', rightAdd, ', sum = ', (sliceCount + leftAdd + rightAdd))
        
        timeStart2n = maxTimeStart2n - leftAdd * maxSliceWidth2n
        timeEnd2n = minTimeEnd2n + rightAdd * maxSliceWidth2n
        if (debug):
            print('interval [', timeStart2n, ', ', timeEnd2n, '] with s = ', maxSliceWidth2n, ' and c = ', sliceCount2n)
        
        return timeStart2n, maxSliceWidth2n, int(sliceCount2n)

    #
    # Writes the data in the time interval to the x and y arrays
    #        
    def getDownsampledPlotData(self, varIndex, reqTimeStart, reqTimeEnd, scaleFactor, reqSampleCount):
        debug = False
        
        if debug:
            print
            print        
            print('downsample(', varIndex, reqTimeStart, reqTimeEnd, reqSampleCount, ')')
        
        rawx = self.datax[varIndex] 
        rawy = self.datay[varIndex]

        '''
        doDownsampling = None
        
        rawIdxStart = self.getLessOrEqualIndex(rawx, reqTimeStart)
        rawIdxEnd = self.getLessOrEqualIndex(rawx, reqTimeEnd)
        
        if debug:
            print 'raw interval [', rawIdxStart, ',', rawIdxEnd, '] = (', rawx[rawIdxStart], ',', rawx[rawIdxEnd], ')'
        
        #self.dsStatIntervalRawSampleCount = rawIdxEnd - rawIdxStart

        # Do we down-sample
        if (rawIdxEnd - rawIdxStart <= 1):
            # If not enough raw samples then skip down-sampling
            doDownsampling = False
            if debug:
                print 'RAW not enough samples: ', (rawIdxEnd - rawIdxStart), '<= 1'
        else:
            requestedResolution = float(reqSampleCount) / (reqTimeEnd - reqTimeStart)
            rawResolution = float(rawIdxEnd - rawIdxStart) / (rawx[rawIdxEnd] - rawx[rawIdxStart])
            
            # We down-sample if we have more samples per time unit then was 
            # requested by time interval length and reqSampleCount
            doDownsampling = (rawResolution > requestedResolution)
            
            if debug:
                print 'RAW doDownsampling = (', rawResolution, '>', requestedResolution, ')' 
                
        # If there aren't enough samples to down-sample
        if not doDownsampling:
            if debug:
                print 'returning raw data'
            
            x, y = self.getRawPlotData(varIndex, reqTimeStart, reqTimeEnd, scaleFactor)
            
            return x, y, None, None
        
        else:
        '''
        if True:
            if debug:
                print('requested(', reqTimeStart, reqTimeEnd, reqSampleCount, ')')
                
            t0, s, c = self.getAdjustedTimeSlices(reqTimeStart, reqTimeEnd, reqSampleCount)
            
            adjTimeStart = t0
            adjTimeEnd = t0 + s*c
            adjSampleCount = c
            adjTimeSlice = s
            
            #rawIdxStart = self.getLessOrEqualIndex(rawx, adjTimeStart)
            #rawIdxEnd = self.getLessOrEqualIndex(rawx, adjTimeEnd)
            rawIdxStart = bisect.bisect_left(rawx, adjTimeStart)
            if rawIdxStart <= 0: rawIdxStart = 0
            rawIdxEnd = bisect.bisect_right(rawx, adjTimeEnd)
            if rawIdxEnd >= len(rawx): rawIdxEnd = len(rawx)-1

            if debug:
                print('adjusted ', adjTimeStart, adjTimeEnd, adjSampleCount, 'ts = ', adjTimeSlice)
                print('fount limits: [', rawx[rawIdxStart], ' - ', rawx[rawIdxEnd], ']')
                #print 'raw list[', rawIdxStart, ',', rawIdxEnd, '] of ', len(rawx)
            
    
            # Return arrays
            res_time = [None] * adjSampleCount
            res_miny = [sys.float_info.max] * adjSampleCount
            res_maxy = [-sys.float_info.max] * adjSampleCount
            res_avgy = [0] * adjSampleCount
            res_dps = [0] * adjSampleCount
            
            #print 'time = ', adjTimeStart
            for i in range(0, adjSampleCount):
                res_time[i] = adjTimeStart + i*adjTimeSlice
            
            # First data index to be taken into down-sampling
            # Before or at adjTimeStart
            while (rawx[rawIdxStart] < adjTimeStart):
                rawIdxStart += 1
            while (rawx[rawIdxEnd] >= adjTimeEnd):
                rawIdxEnd -= 1
            
            # First and last added slot index
            firstUsedSlotIndex = None 
            lastUsedSlotIndex = None
            
            # Start time of the first slot
            slotStartTime = adjTimeStart
            slotEndTime = adjTimeStart + adjTimeSlice

            #
            # Convert raw data to slots
            #
            slotIdx = 0
            rawIdx = rawIdxStart

            #print '\nnew time slot[', slotIdx, '] (', slotStartTime, ', ', slotEndTime, '): ',
                
            # Use all data samples and put them into slots 
            while (rawIdx <= rawIdxEnd):
                
                t = rawx[rawIdx]
                
                # Move to the appropriate slot
                while (t >= slotEndTime):

                    slotStartTime += adjTimeSlice
                    slotEndTime += adjTimeSlice
                    
                    slotIdx += 1
                    
                    #res_time[slotIdx] = slotStartTime
                    
                    # If we are past the last slot then exit loop
                    if (slotIdx >= adjSampleCount):
                        break
                    
                    #print '\nnew time slot[', slotIdx, '] (', slotStartTime, ', ', slotEndTime, '): ',
                    
                #print t, ', ',
                    
                res_miny[slotIdx] = min(res_miny[slotIdx], rawy[rawIdx])
                res_maxy[slotIdx] = max(res_maxy[slotIdx], rawy[rawIdx])
                res_avgy[slotIdx] += rawy[rawIdx]
                res_dps[slotIdx] += 1
            
                rawIdx +=1
                
                lastUsedSlotIndex = slotIdx

            #print '\ndone with time slots'

            #
            # Take care of start and end of chart to prevent anomalies
            #
            '''
            # First slot
            if (res_dps[0] == 0):
                # If we have data to the left of the chart then use the last sample
                if (rawIdxStart > 0):
                    i = rawIdxStart - 1
                    
                    res_time[0] = rawx[i]
                    res_miny[0] = rawy[i]
                    res_maxy[0] = rawy[i]
                    res_avgy[0] = rawy[i]
                    res_dps[0] = 1

                    firstUsedSlotIndex = 0
            
            # Last slot
            if (res_dps[-1] == 0):
                # If we have data to the right of the chart then use the first sample
                if (rawIdxEnd < len(rawx) - 1):
                    i = rawIdxEnd + 1
                    
                    res_time[-1] = rawx[i]
                    res_miny[-1] = rawy[i]
                    res_maxy[-1] = rawy[i]
                    res_avgy[-1] = rawy[i]
                    res_dps[-1] = 1
            
                    lastUsedSlotIndex = len(res_dps) - 1
            '''
                
            #
            # Finalize data down-sampling per slot and scale as required
            #
            avgDps = 0
            dps0count = 0
            
            for i in range(adjSampleCount):
                if (res_dps[i] > 0):
                    res_avgy[i] /= res_dps[i]

                    if firstUsedSlotIndex == None:                     
                        firstUsedSlotIndex = i
                    
                    res_miny[i] *= scaleFactor
                    res_maxy[i] *= scaleFactor
                    res_avgy[i] *= scaleFactor
                    
                    avgDps += res_dps[i]
                else:
                    dps0count += 1
                
            if (avgDps < 3):
                x, y = self.getRawPlotData(varIndex, reqTimeStart, reqTimeEnd, scaleFactor)
                
                return x, y, None, None
                
            #
            # Fill in the blanks by interpolation
            #
            lastFoundIdx = None
                
            #for i in range(firstUsedSlotIndex, lastUsedSlotIndex+1):
            i = 0
            while i < adjSampleCount:
                if (res_dps[i] == 0):
                    
                    # Last left non-null element
                    li = lastFoundIdx
                    
                    # Get first right non-null element
                    ri = None
                    
                    while (i < adjSampleCount  and 
                           res_dps[i] == 0):
                        i += 1
                        
                    if (i < adjSampleCount):
                        ri = i
                    
                    self.interpolate(res_avgy, res_miny, res_maxy, li, ri)
                        
                else:
                    lastFoundIdx = i
                    i += 1
                        


            #
            # Return only used slots
            #
            if firstUsedSlotIndex < lastUsedSlotIndex:
                i1 = firstUsedSlotIndex
                i2 = lastUsedSlotIndex + 1

                return res_time[i1:i2], res_avgy[i1:i2], res_miny[i1:i2], res_maxy[i1:i2]
            else:
                return [], [], [], []
    '''     
    def interpolate(self, a, i1, i2):
        for i in range(i1+1, i2):
            a[i] = a[i1] + ((i-i1) / float(i2-i1) * (a[i2]-a[i1]))
    '''
    def interpolate(self, a, min, max, i1, i2):
        #print 'interpolating ', i1, i2
        if i1 == None:
            for i in range(i2):
                v = a[i2]
                a[i] = v
                min[i] = v
                max[i] = v
        elif i2 == None:
            for i in range(i1+1, len(a)):
                v = a[i1]
                a[i] = v
                min[i] = v
                max[i] = v
        else:
            for i in range(i1+1, i2):
                v = a[i1] + ((i-i1) / float(i2-i1) * (a[i2]-a[i1]))
                a[i] = v 
                min[i] = v
                max[i] = v
           
    #
    # Gets the estimated value of a selected variable for a particular moment 
    # in time. The value is taken at that time or the last sample before that.
    # Used for rich (without empty cells) table population.
    #
    def getEstimatedValue(self, row, varIdx):
        
        time = self.allTimePoints[row]
        
        #
        # Optimization
        #
        
        lastIdx = self.lastIndexFound[varIdx]
        lastRow = self.lastRows[varIdx]
        
        x = self.datax[varIdx]
        y = self.datay[varIdx]
        
        # If we just went to next row and if any more data left for this variable
        if (lastRow + 1 == row):
            
            # If the last used timestep was the last in the data then use it again
            if (len(x) <= lastIdx + 1):
                self.lastRows[varIdx] = row
                #return '***' + str(y[lastIdx])
                return y[lastIdx]
            
            # If next data point has greater value than the current row then 
            # use the data value of previous row
            if (x[lastIdx+1] > time):
                
                self.lastRows[varIdx] = row
                #return '*' + str(y[lastIdx])
                return y[lastIdx]
            
            elif (x[lastIdx+1] == time):
                
                self.lastIndexFound[varIdx] = lastIdx+1
                self.lastRows[varIdx] = row

                #return '**' + str(y[lastIdx+1])
                return y[lastIdx+1]

        # Brute force find by bisection
        index = self.getLessOrEqualIndex(x, time)

        self.lastIndexFound[varIdx] = index
        self.lastRows[varIdx] = row
        
        return y[index]
        
    #
    # Returns true if we have a data sample for the 
    # specified variable in the specified row
    #
    def isRealValue(self, row, varIdx):
        
        exactTime = self.allTimePoints[row]
        x = self.datax[varIdx]

        index = self.getLessOrEqualIndex(x, exactTime)
        
        return None != index and x[index] == exactTime
        
        
    #
    # Use bisection to find index exact value or greatest value 
    # that is smaller than that
    #
    def getLessOrEqualIndex(self, array, val):
        left = 0
        right = len(array)-1
        
        if (len(array) <= 0):
            return None
        elif (val > array[-1]):
            return len(array)-1
        elif (val < array[0]):
            return 0
        
        while (left + 1 < right):
            center = (left + right) // 2
    
            if (array[center] == val):
                return center
            elif (array[center] > val):
                right = center
            else:
                left = center
    
        if (array[right] <= val):
            return right
        else:
            return left
        
        
        
    #
    # Returns the unprocessed sample data
    #
    def getRawData(self):
        return [self.datax, self.datay]
    
    
    
    # Cleanup resources
    def stopSampling(self):

        if self.wasConfigured:
            
            if (self.daqCtrl != None):
                daqStatus = self.daqCtrl.status()
                if daqStatus.getGlobalEnable():
                    self.daqCtrl.enableGlobal(False);
            
            # Stop worker thread
            if self.sampleReaderThread != None:
                self.sampleReaderThread.stopRunning()
                self.sampleReaderThread.join()
                
                # Remove unused data from thread queue
                while (not self.sampleQueue.empty()):
                    row = self.sampleQueue.get()


   
class DaqWorkerThread(threading.Thread):
    
    running = None
    daqManager = None
    
    # 20 fps
    sleepPeriod = 1.0 / 20 
    
    def __init__(self, daqMgr):
        threading.Thread.__init__(self)
        
        self.running = True
        self.daqManager = daqMgr
    
    #
    # This method just reads the data from the DAQ queue to prevent the sampling 
    # overflow error. It puts the data into the data queue that is read every time
    # that the updateSamplingData is called
    #
    def run(self):
        logging.info("Starting DAQ reading")
        while(self.running):
            self.daqManager.queueSamplingData()
            time.sleep (self.sleepPeriod);
        logging.info("DAQ reading stopped")

            
    def stopRunning(self):
        self.running = False

        
