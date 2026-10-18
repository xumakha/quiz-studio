"""Use the Tcl/Tk scripts shipped beside the frozen application."""
import os
import sys

os.environ['TCL_LIBRARY'] = os.path.join(sys._MEIPASS, '_tcl_data')
os.environ['TK_LIBRARY'] = os.path.join(sys._MEIPASS, '_tk_data')
