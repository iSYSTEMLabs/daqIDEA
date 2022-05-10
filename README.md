# daqIDEA
iSYSTEM graphic presentation tool for data acquired through winIDEA, more info available here:
https://www.isystem.com/downloads/winIDEA/help/daqidea.html

## How to prepare environment
1. Required on Linux:

    `sudo apt install libxerces-c3.2`
   
2. Add required python dependencies by executing setup.py module, an example:  

    `python setup.py install`
   
3. Since pyqt5 dependency fails to install via setup.py, it needs to be installed manually as:  

    `python.exe -m pip install pyqt5`


## How to run daqIDEA

    python src\daqIDEA.py
