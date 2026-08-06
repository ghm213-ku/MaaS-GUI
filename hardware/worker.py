import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

# Ensure you have the Swabian TimeTagger library installed
import TimeTagger 

class CountRateWorker(QThread):
    """
    Background thread dedicated to interacting with the Swabian API.
    Never update the UI directly from this class.
    """
    # Signal that will carry the Numpy array of count rates back to the main thread
    newDataReady = pyqtSignal(np.ndarray)

    def __init__(self, channels):
        super().__init__()
        self.channels = channels
        self.running = True
        self.tagger = None
        self.countrate = None
        
    def run(self):
        try:
            # 1. Connect to the Time Tagger
            self.tagger = TimeTagger.createTimeTagger()
            
            # 2. Create the continuous Countrate measurement
            self.countrate = TimeTagger.Countrate(self.tagger, self.channels)
            
            # 3. Enter the polling loop
            while self.running:
                # Sleep to define the GUI refresh rate (~20 Hz)
                self.msleep(50) 
                
                # Retrieve the current average count rate in cps
                rates = self.countrate.getData()
                
                # Emit the signal to notify the GUI thread
                self.newDataReady.emit(rates)
                
        except Exception as e:
            print(f"Hardware Error: {e}")
            
        finally:
            # Always free the hardware resources when the loop breaks
            if self.tagger is not None:
                TimeTagger.freeTimeTagger(self.tagger)
        
    def stop(self):
        self.running = False
        self.wait() # Block until the thread gracefully exits
