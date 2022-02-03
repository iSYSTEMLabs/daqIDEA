
from __future__ import print_function

import globals, daqIO, logging

TYPE_INT = 0
TYPE_FLOAT = 1
TYPE_STRUCT = 2
TYPE_IO = 3
TYPE_MEM_ADDR = 4

class DaqVariable:
    # myInteger
    name = None
    partitionName = None
    # myTable[4]
    fullName = None

    # 0=int 1=real 2=complex 3=mem 4=I/O
    simpleType = None
    # unsigned short.....
    fullType = None
    
    arrayStartIndices = None
    arrayLengthIndices = None
    
    # 1..8
    portBit = None
    # digital/analogue
    portType = None
    
    # Memory address
    memAddr = None
    
    # Formatters available to us for this data type
    formatters = None
    
    @classmethod
    def fromMemAddress(cls, addr):
        c = cls()
        c.name = '0x'
        c.fullName = '0x'
        c.memAddr = addr
        c.simpleType = TYPE_MEM_ADDR
        c.formatters = globals.formatInteger
        return c
    
    @classmethod
    def fromPort(cls, name, portType, portBit):
        c = cls()
        c.name = '`' + name
        c.fullName = c.name # Nothing extra
        c.portBit = portBit
        c.portType = portType
        c.simpleType = TYPE_IO
        
        if (c.portType == daqIO.HIL_DIN):
            c.formatters = globals.formatInteger
        elif (c.portType == daqIO.HIL_AIN):
            c.formatters = globals.formatFloat
        
        c.fullType = '`' + '[' + str(c.portBit) + ']'
        return c

    @classmethod
    def fromVariable(cls, name, partitionName, type, dataCtrl):
        c = cls()
        c.name = name
        c.partitionName = partitionName
        c.fullName = name # We later add array indices
        c.fullType = type
        
        if ('char' in type or 
            'int' in type or 
            'short' in type or 
            'long' in type):
            c.simpleType = TYPE_INT
            c.formatters = globals.formatInteger
        elif ('float' in type or 
              'double' in type):
            c.simpleType = TYPE_FLOAT
            c.formatters = globals.formatFloat
        else:
            c.simpleType = TYPE_STRUCT
            c.formatters = globals.formatAll
            
        c.arrayStartIndices, c.arrayLengthIndices, c.fullName = c.extractIndices(type, name, dataCtrl)
        
        if (c.partitionName != None):
            c.fullName += ',,' + partitionName

        return c

    @classmethod
    def extractIndices(cls, t, name, dataCtrl):
        if ('[' in t and ']' in t):
            returnName = name
            
            indicesFirst = []
            indicesLength = []
            exprType = dataCtrl.getExpressionType(0, name)
            expr = exprType.Expression()
            while expr.ArrayDimension() > 0:
                indicesFirst.append(expr.ArrayFirstElement())
                indicesLength.append(expr.ArrayDimension())
               
                name = "%s[%d]"%(expr.Name(), expr.ArrayFirstElement())
                
                if (expr.ArrayFirstElement() == 0):
                    returnName = "%s[%d]"%(returnName, expr.ArrayDimension())
                else:
                    returnName = "%s[%d..%d]"%(returnName, 
                                               expr.ArrayFirstElement(), 
                                               expr.ArrayFirstElement() + expr.ArrayDimension() - 1)

                self.dataCtrl.release(exprType)
                exprType = dataCtrl.getExpressionType(0, name)
                expr = exprType.Expression()

            self.dataCtrl.release(exprType)
            return indicesFirst, indicesLength, returnName
        else:
            return None, None, name
    

    #
    # Type getters            
    #
    def isInteger(self):
        return self.simpleType == TYPE_INT
    
    def isFloat(self):
        return self.simpleType == TYPE_FLOAT
    
    def isComlex(self):
        return self.simpleType == TYPE_STRUCT
    
    def isMemAddr(self):
        return self.simpleType == TYPE_MEM_ADDR
    
    def isIO(self):
        return self.simpleType == TYPE_IO

    
    def toString(self):
        if self.simpleType == TYPE_MEM_ADDR:
            return "Variable MEM: " + hex(self.memAddr) 
        elif self.simpleType == TYPE_IO:
            return "Variable IO: " + self.fullName + " at index " + str(self.portBit)
        else:
            return "Variable: " + self.fullType + " " + self.fullName
      
         

