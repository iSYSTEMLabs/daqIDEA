
from __future__ import print_function

import os, sys, time
import logging

os.environ['QT_API'] = 'pyqt5'
import matplotlib
matplotlib.use('Qt5Agg')
from numpy import arange, sin, pi
import numpy as np
import pylab

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import *

from PyQt5 import QtCore, QtGui, QtWidgets
import globals

class MyMplCanvas(FigureCanvas):
    
    fig = None
    subplots = []
    
    lastBounds = dict()
   
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        col = 0.95
        self.fig = Figure(figsize=(width, height), dpi=dpi, 
                          facecolor=(col, col, col), edgecolor=(0, 0, 0), 
                          frameon=True)
        
        self.addSubplot()
        self.fig.tight_layout()
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                                   QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Expanding)
        
        FigureCanvas.updateGeometry(self)

    
    def addSubplot(self):
        n = len(self.subplots)
        
        for i in range(len(self.subplots)):
            self.subplots[i].change_geometry(n+1, 1, i+1)
            self.subplots[i].tick_params(axis='x', labelsize=0, which='both')
                     
        sp = self.fig.add_subplot(n+1, 1, n+1)
        sp.tick_params(axis='both', labelsize=8, which='both')
        
        #sp.hold(True)
        sp.grid(True)

        self.subplots.append(sp)
        
        self.lastBounds[sp] = [0, 1, 0, 1]
        

    def removeSubplot(self):
        # Remove last chart
        del self.lastBounds[self.subplots[-1]]
        self.fig.delaxes(self.subplots[-1])
        self.subplots = self.subplots[:-1]
        
        # Adjust grid and indexes of rest
        n = len(self.subplots)
        for i in range(len(self.subplots)):
            self.subplots[i].change_geometry(n, 1, i+1)
            self.subplots[i].tick_params(axis='x', labelsize=0, which='both')
            
        self.subplots[-1].tick_params(axis='both', labelsize=8, which='both')
        
    def resizeEvent(self, event):
        s = event.size()
        # Prevent resizing if too small because it generates an exception
        if (s.width() > 0  and s.height() > 0):
            super(FigureCanvas, self).resizeEvent(event)
        self.fig.tight_layout()

class MyDynamicMplCanvas(MyMplCanvas):

    myParent = None
    
    downx = None
    downy = None

    axe2plot = []
    requiredChartCount = 0;
    
    # Animation updates
    chartPlotTimer = None
    chartPlotSignal = None
    chartAminationRunning = False
    chartAminationPaused = False
    
    animationStopTime = 0
    
    zoomRectangle = Rectangle((0, 0), 0, 0, 
                              fill=True, alpha=0.1, 
                              fc='r', ec='k', linestyle='dotted')
    zoomDraw = False
    zoomedSubplot = None
    
    lastPanX = None
    lastPanY = None
    
    averageTimeStatistic = globals.AverageInt(50)
    
    
    def __init__(self, parent, *args, **kwargs):
        MyMplCanvas.__init__(self, *args, **kwargs)
        self.myParent = parent


    def startAnimation(self):
        if (not self.chartAminationRunning):
            
            # IF animation was un-paused or played for the first time
            if (self.chartAminationPaused):
                self.chartPlotTimer.start(globals.CHART_PLOT_UPDATE_INTERVAL_MS)
            else:
                self.myParent.dataTable.model().updateDataModel()
                
                isOK = self.myParent.configureDaqController()
                
                if not isOK:
                    return False
                
                self.chartPlotTimer = QtCore.QTimer(self)
                self.chartPlotTimer.timeout.connect(self.updateCharts)
                self.chartPlotTimer.start(globals.CHART_PLOT_UPDATE_INTERVAL_MS)
                for s in self.subplots:
                    s.clear()
            
            self.chartAminationRunning = True
            self.chartAminationPaused = False
            
        return True
        
        
    def pauseAnimation(self):
        if (self.chartAminationRunning and not self.chartAminationPaused):
            self.chartPlotTimer.stop()
            self.chartAminationRunning = False
            self.animationStopTime = self.myParent.daqManager.getTimeSinceStart()
            self.chartAminationPaused = True
        
        
    def stopAnimation(self):
        if (self.chartAminationRunning or self.chartAminationPaused):
            
            self.chartPlotTimer.stop()
            self.chartPlotTimer.timeout.disconnect(self.updateCharts)
            
            self.chartAminationRunning = False
            self.animationStopTime = self.myParent.daqManager.getTimeSinceStart()
            self.chartAminationPaused = False
            self.myParent.daqManager.stopSampling()
        else:
            logging.error('chart.stopAnimation()')
        
        
    def isAnimationRunning(self):
         return self.chartAminationRunning
     
     
    def isAnimationPaused(self):
         return not self.chartAminationRunning and self.chartAminationPaused


    def isAnimationStopped(self):
         return not self.chartAminationRunning and not self.chartAminationPaused
    
    
    def updateCharts(self):
        if None == self.myParent.daqManager:
            return

        startPlotTime = time.time()
        
        dataCount = 0
        dataShownCount = 0
        
        if self.myParent.daqManager.isDaqConfigured():

            if (self.isAnimationRunning()):
                tableModel = self.myParent.dataTable.model()
                self.myParent.daqManager.deQueueSamplingData(tableModel)

            # Add/remove unused charts
            while len(self.subplots) < self.requiredChartCount:
                self.addSubplot()
            while len(self.subplots) > self.requiredChartCount:
                self.removeSubplot()

            for sp in self.subplots:
                sp.clear()
                sp.grid(True)

            # Reset the bounds so we can calculate them during plotting
            if (self.isAnimationRunning()):
                for b in self.lastBounds.values():
                    b[0] = sys.float_info.max
                    b[1] = -sys.float_info.max
                    b[2] = sys.float_info.max
                    b[3] = -sys.float_info.max
                
            #
            # Plot all variables to their corresponding charts
            #
            daqVarIdx = -1
            for varIdx, varConfig in enumerate(self.myParent.daqIdeaConfig.variableConfigs):
                
                # Draw only enabled variables
                if (not varConfig.enabled  or 
                    varConfig.daqConfigIndex == -1):
                    continue
                
                daqVarIdx += 1
                
                subplot = self.subplots[self.axe2plot[daqVarIdx]]

                bounds = self.lastBounds[subplot]

                if (self.isAnimationRunning()):
                    t = self.myParent.daqManager.getTimeSinceStart()
                    maxx = float(max(t, self.myParent.daqIdeaConfig.animationTimeInterval))
                    minx = float(maxx - self.myParent.daqIdeaConfig.animationTimeInterval)
                else:
                    minx = bounds[0]
                    maxx = bounds[1]

                #
                # Get latest plot data
                #
                
                xp, yp = self.myParent.daqManager.getRawPlotData(varConfig.daqConfigIndex, minx, maxx, varConfig.scale)

                # Calculate Y bounds
                if (self.isAnimationRunning()):
                    # If nop data then set to [-1, 1] interval
                    if (len(yp) <= 0):
                        miny = -1.0
                        maxy = 1.0
                    else:
                        miny = min(yp)
                        maxy = max(yp)
                    
                        # If only one sample then stretch the chart by 0.5 over and under
                        if (miny == maxy):
                            miny -= 0.5
                            maxy += 0.5

                    # Ir we have a normal chart then add 5% bounds over and under
                    margin = 0.05
                    d = maxy - miny
                    
                    miny -= d * margin
                    maxy += d * margin
                    
                    
                    bounds[0] = min(minx, bounds[0])
                    bounds[1] = max(maxx, bounds[1])
                    bounds[2] = min(miny, bounds[2])
                    bounds[3] = max(maxy, bounds[3])
                    
                subplot.plot(
                             xp, yp
                             , color=varConfig.floatColor, label=varConfig.name 
                             , clip_on=True, antialiased=True
                             , drawstyle='steps-post'
                             , marker='.', picker=5
                             )

                # Draw the last sample of each chart as a dotted line to the current time
                subplot.plot(
                             [xp[-1], maxx], [yp[-1], yp[-1]]
                             , color=varConfig.floatColor, label=varConfig.name 
                             , linestyle='--'
                             , clip_on=True, antialiased=True
                             , drawstyle='default'
                             , picker=5
                             )

                '''
                # Here yp is the average of all y's in the time slice
                xp, yp, minyp, maxyp = self.myParent.daqManager.getDownsampledPlotData(daqVarIdx, minx, maxx, varConfig.scale, 1000)

                rawx, rawy = self.myParent.daqManager.getRawPlotData(daqVarIdx, minx, maxx, varConfig.scale)

                # Calculate Y bounds
                if (self.isAnimationRunning()):
                    # If nop data then set to [-1, 1] interval
                    if (len(yp) <= 0):
                        miny = -1.0
                        maxy = 1.0
                    else:
                        if (minyp == None)  and  (maxyp == None):
                            miny = min(yp)
                            maxy = max(yp)
                        else:
                            miny = min(minyp)
                            maxy = max(maxyp)
                            
                    
                        # If only one sample then stretch the chart by 0.5 over and under
                        if (miny == maxy):
                            miny -= 0.5
                            maxy += 0.5

                    # Ir we have a normal chart then add 5% bounds over and under
                    margin = 0.05
                    d = maxy - miny
                    
                    miny -= d * margin
                    maxy += d * margin
                    
                    
                    bounds[0] = min(minx, bounds[0])
                    bounds[1] = max(maxx, bounds[1])
                    bounds[2] = min(miny, bounds[2])
                    bounds[3] = max(maxy, bounds[3])
                
                #
                # Plot the data
                #
                # Old school
                if (self.myParent.specialEnabled[globals.mainApplicationWindow.SPEC_RAW]):
                    subplot.plot(
                                 rawx, rawy
                                 , color='b', label=varConfig.name 
                                 , clip_on=True, antialiased=True
                                 )

                # Average
                if (self.myParent.specialEnabled[globals.mainApplicationWindow.SPEC_AVG]):
                    subplot.plot(
                                 xp, yp
                                 , color=varConfig.floatColor, label=varConfig.name
                                 , clip_on=True, antialiased=False
                                 #, drawstyle='steps-post'
                                 #, marker='.', picker=5
                                 )

                if (self.myParent.specialEnabled[globals.mainApplicationWindow.SPEC_MM]):
                    subplot.fill_between(
                                         xp, minyp, maxyp
                                         , color='blue', edgecolor='none'
                                         , antialiased=False
                                         , alpha=0.7
                                         )                

                # Min/Max container
                if (self.myParent.specialEnabled[globals.mainApplicationWindow.SPEC_CON]):
                    t = []
                    a1 = []
                    a2 = []
                    
                    for i in range(0, len(xp)-1):
                        t.append(xp[i])
                        a1.append(minyp[i])
                        a2.append(maxyp[i])
    
                        t.append(xp[i+1])
                        a1.append(minyp[i])
                        a2.append(maxyp[i])
    
                    subplot.fill_between(
                                         t, a1, a2
                                         , color=varConfig.floatColor, edgecolor='none'
                                         , antialiased=False
                                         #, alpha=1.0
                                         )                
                '''
                dataCount += len(xp)

                '''
                # We pull the last value of a plot to the right edge of the graph
                ax = [xp[-1], maxx]
                ay = [yp[-1], yp[-1]]
                subplot.plot(ax, 
                             ay, 
                             self.defaultPlotColors[varIdx]#, label=names[varIdx]
                             )
                '''
                
            for subplot in self.subplots:
                bounds = self.lastBounds[subplot]

                if not np.isnan(bounds[0]) and not np.isnan(bounds[1]):
                    subplot.set_xbound(lower=bounds[0], upper=bounds[1])

                if not np.isnan(bounds[2]) and not np.isnan(bounds[3]):
                    subplot.set_ybound(lower=bounds[2], upper=bounds[3])
                
                if (self.zoomDraw  and  subplot == self.zoomedSubplot):
                    subplot.add_patch(self.zoomRectangle)
                    
                subplot.legend(loc='upper left', fontsize='small', frameon=False)
            
            # Draw
            self.fig.tight_layout()
            self.draw()
            
        '''
        # Show frame rate of plot drawing
        self.averageTimeStatistic.add(int((time.time() - startPlotTime)*1000))
        print ('draw time [', 
            self.averageTimeStatistic.getAvg(), 'ms] (', 
            self.averageTimeStatistic.getMin(), '-',
            self.averageTimeStatistic.getMax(),')')
        '''
        
        '''
        # Show number of plotted data points
        self.myParent.statusBar().showMessage(
                    'Data units shown:' + str(dataCount) + 
                    ' dt = ' + str(self.averageTimeStatistic.getAvg()) + 'ms', 0)
        '''
        
        #print 'data points: ', dataCount
        
        
    #
    # sets the status bar to the current mouse location inside the chart
    # and checks if there are any subplots and returns True if so
    #
    def chartEventCheck(self, event):
        
        if event.xdata != None  and  event.ydata != None:
            s =  '[t = %f' % event.xdata 
            s += ', y = %f]' % event.ydata
            
            self.myParent.statusBar().showMessage(s)

        return event.inaxes != None  and  event.inaxes in self.subplots


    def mousePress(self, event):  
        if not self.chartEventCheck(event):
            return True
        
        # Only when paused
        if (not self.isAnimationRunning()):
            if event.button != 1:
                # Zooming start        
                if (event.inaxes != None)  and  (event.inaxes in self.subplots):
                    sp = event.inaxes
    
                    # Remember which chart                
                    self.zoomedSubplot = sp
                    
                    # Set the start
                    r = self.zoomRectangle
                    r.set_x(event.xdata)
                    r.set_y(event.ydata)
                    r.set_width(0)
                    r.set_height(0)
                    
                    # We are selecting the zoom area
                    self.zoomDraw = True
            else:
                #Paning
                if (event.inaxes != None)  and  (event.inaxes in self.subplots):
                    self.zoomedSubplot = event.inaxes

                    self.lastPanX = event.xdata
                    self.lastPanY = event.ydata
    
    
    def mouseMotion(self, event):
        if not self.chartEventCheck(event):
            return True
        
        # Only when paused
        if (not self.isAnimationRunning()):
            if event.button != 1:
                # If we are still inside the same chart
                if (self.zoomedSubplot != None  and  
                    self.zoomedSubplot == event.inaxes  and  
                    self.zoomDraw):
                
                    # Setup the rectangle as the zoom area
                    r = self.zoomRectangle
        
                    w = event.xdata - r.get_x()
                    h = event.ydata - r.get_y()
                    
                    r.set_width(w)
                    r.set_height(h)
                
                    # Show what we have selected
                    self.updateCharts()
            else:
                #Paning
                if (event.inaxes != None)  and  (event.inaxes == self.zoomedSubplot):
                    dx = event.xdata - self.lastPanX
                    dy = event.ydata - self.lastPanY
                    
                    b = self.lastBounds[event.inaxes]
                    b[0] -= dx
                    b[1] -= dx
                    b[2] -= dy
                    b[3] -= dy
                    self.updateCharts()
                
                
    def mouseLeaveAxis(self, event):
        if not self.chartEventCheck(event):
            return True
        
        if not self.isAnimationRunning():
            if event.button != 1:
                if (event.inaxes != None)  and  (event.inaxes == self.zoomedSubplot):
                    self.zoomDraw = False
                    self.zoomedSubplot = None
                    self.updateCharts()
            else:
                if (event.inaxes != None)  and  (event.inaxes == self.zoomedSubplot):
                    self.lastPanX = None
                    self.lastPanY = None
                    self.zoomedSubplot = None
        
        self.myParent.statusBar().showMessage('')


    def mouseRelease(self, event):
        if not self.chartEventCheck(event):
            return True
        
        if not self.isAnimationRunning():  
            if event.button != 1:
                if (self.zoomDraw  and  
                    self.zoomedSubplot == event.inaxes):
                
                    self.zoomDraw = False
                    
                    r = self.zoomRectangle
                    
                    x0 = min(r.get_x(), event.xdata)
                    x1 = max(r.get_x(), event.xdata)
        
                    y0 = min(r.get_y(), event.ydata)
                    y1 = max(r.get_y(), event.ydata)
                    
                    w = x1 - x0
                    h = y1 - y0
                    
                    if (w > 0  and  h > 0):
                        # We have to adjust the bounds on the redraw
                        bounds = self.lastBounds[self.zoomedSubplot]
                        r = self.zoomRectangle
                        
                        bounds[0] = x0
                        bounds[1] = x1
                        bounds[2] = y0
                        bounds[3] = y1
        
                        # Make the zoom
                        self.updateCharts()

                    self.zoomedSubplot = None
            else:
                #Paning
                if (event.inaxes != None)  and  (event.inaxes == self.zoomedSubplot):
                    dx = event.xdata - self.lastPanX
                    dy = event.ydata - self.lastPanY
                    
                    self.lastPanX = None
                    self.lastPanY = None
                    self.zoomedSubplot = None

                    b = self.lastBounds[event.inaxes]
                    b[0] -= dx
                    b[1] -= dx
                    b[2] -= dy
                    b[3] -= dy
                    self.updateCharts()


    def mouseScroll(self, event):
        if not self.chartEventCheck(event):
            return True
        
        # If we are scrolling while animation is running then the time 
        # interval is changed
        if self.isAnimationRunning():
            t = self.myParent.daqIdeaConfig.animationTimeInterval
            
            stepCount = int(abs(event.step))
            step = -int(event.step / stepCount)

            for i in range(stepCount):
                if step < 0:
                    if (t <= globals.TIME_INTERVAL_MIN): # Min is TIME_INTERVAL_MIN
                        pass
                    elif (t <= 5): # Between 1 and 5 the step is 1
                        t += step
                    elif (t <= 60): # Between 5 and 60 the step is 5
                        t += 5*step
                    elif (t <= 300): # Between 60 and 300 the step is 30
                        t += 30*step
                    else:
                        t += 60*step
                else:
                    if (t >= 300):
                        t += 60*step
                    elif (t >= 60):
                        t += 30*step
                    elif (t >= 5):
                        t += 5*step
                    elif (t >= 1):
                        t += 1*step
            
            self.myParent.daqIdeaConfig.animationTimeInterval = t
            
        elif (not self.zoomDraw  and  
            event.inaxes != None):
            
            zoomFactor = 1.4 ** (-event.step)
            xm = event.xdata
            ym = event.ydata

            bounds = self.lastBounds[event.inaxes]
            bounds[0] = xm - (xm - bounds[0]) * zoomFactor
            bounds[1] = xm + (bounds[1] - xm) * zoomFactor
            bounds[2] = ym - (ym - bounds[2]) * zoomFactor
            bounds[3] = ym + (bounds[3] - ym) * zoomFactor

            self.updateCharts()


    def pickEvent(self, event):
        #print 'PICK EVENT: '
        thisline = event.artist
        xdata, ydata = thisline.get_data()
        ind = event.ind
        #print('on pick line[', ind,']:', zip(xdata[ind], ydata[ind]))
    
            
    def updateChartSubplots(self):
        
        spinValues = []
        
        for varConfig in self.myParent.daqIdeaConfig.variableConfigs:
            if (varConfig.enabled):
                spinValues.append(varConfig.chartIndex)
            
        # All unique values
        spinUniqValues = sorted(list(set(spinValues)))
        
        # Which chart should the variable have
        sortedValues = []
        for i in spinValues:
            sortedValues.append(spinUniqValues.index(i))
        
        # How many charts required?
        self.requiredChartCount = len(set(spinValues))
        
        self.axe2plot = sortedValues
                

