# This script lists all data descriptors for IO module.  You need
# winIDEA connected to IC5000 with IO module (app. downloaded)
# for this script to work.

from __future__ import print_function

import isystem.connect as ic

HIL_DIN = 0
HIL_DOUT = 1
HIL_AIN = 2
HIL_AOUT = 3

HIL_ENABLED = False

def getHilPorts(hilCtrl):
    hilChannels = ic.HILChannelVector()
    hilCtrl.getChannels(hilChannels)
    return list(hilChannels)


def main():
    #create connection and hil controller object
    cMgr = ic.ConnectionMgr()
    cMgr.connectMRU('')
    hilCtrl = ic.CHILController(cMgr)
    
    
    hilChannels = ic.HILChannelVector()
    
    hilCtrl.getChannels(hilChannels)
    for hilChannel in list(hilChannels):
        if (hilChannel.isAvailable()  and  (hilChannel.getType() == 0  or  hilChannel.getType() == 2)):
            print('name: ', hilChannel.getName())
            print('  avail: ', hilChannel.isAvailable())
            print('  type:  ', hilChannel.getType())
            print('  index: ', hilChannel.getIndex())
            print('  unit:  ', hilChannel.getUnit())
            print('  min:   ', hilChannel.getAMin())
            print('  max:   ', hilChannel.getAMax())

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

