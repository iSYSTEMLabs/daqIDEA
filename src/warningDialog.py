
import logging

try:
    import Tkinter as tk
    logging.info("Imported Tkinter")
except ImportError as err:
    import tkinter as tk
    logging.info("Imported tkinter")

class WarningDialog(tk.Frame):
  
    def __init__(self, parent, title, msg):
        tk.Frame.__init__(self, parent)   
         
        self.parent = parent   
        self.initUI(parent, title, msg)
        
        w = parent.winfo_screenwidth()
        h = parent.winfo_screenheight()
        parent.geometry("+%d+%d" % (w/2-100, h/2-100))
        
    def initUI(self, master, title, msg):
      
        self.master.title(title)

        self.warnLabel = tk.Label(master, text=msg)
        self.warnLabel.grid(row=0, sticky=tk.N, padx=15, pady=5)
    
        self.checkedVar = tk.IntVar()
        self.showAgainChecbox = tk.Checkbutton(master, text="Do not show this message again", variable=self.checkedVar)
        self.showAgainChecbox.grid(row=1, sticky=tk.W, padx=5, pady=3)
        
        self.okButton = tk.Button(master, text="OK", command=self.quit)
        self.okButton.grid(row=2, sticky=tk.SE, padx=10, pady=10, ipadx=20, ipady=0)
        
    def getShowWarningAgain(self):
        if self.checkedVar.get() == 1:
            return False
        else:
            return True
    
    def quit(self):
        self.destroy()
        self.parent.quit();

def showWarning(title, msg):
  
    tkRoot = tk.Tk()
    ex = WarningDialog(tkRoot, title, msg)
    tkRoot.mainloop()
    res = ex.getShowWarningAgain()
    tkRoot.destroy()
    
    return res
