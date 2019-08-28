from .Detector import Detector, SoftwareLiveDetector, TriggeredDetector, Link
from ..environment import env

import time
import numpy as np
import PyTango
import os

class Xspress3(Detector, SoftwareLiveDetector, TriggeredDetector):
    def __init__(self, name=None, lima_device=None, det_device=None):
        self.lima_device_name = lima_device
        self.det_device_name = det_device
        Detector.__init__(self, name=name)
        SoftwareLiveDetector.__init__(self)
        TriggeredDetector.__init__(self)

    def initialize(self):
        self.lima = PyTango.DeviceProxy(self.lima_device_name)
        self.lima.set_timeout_millis(10000)
        self.det = PyTango.DeviceProxy(self.det_device_name)
        
        self.lima.acq_trigger_mode = "INTERNAL_TRIGGER"
        self.lima.saving_mode = "MANUAL"
        self.lima.saving_managed_mode = 'SOFTWARE'
        self.lima.saving_overwrite_policy = 'MULTISET'
        self.lima.saving_format = 'HDF5'
        self.lima.saving_suffix = '.hdf5'
        self.lima.saving_index_format = '' # no index, different Limas need different values here
        self.lima.latency_time = 0.0

    def prepare(self, acqtime, dataid):
        """
        Run before acquisition, once per scan. Set up triggering,
        number of images etc.
        """
        # get out of the fault caused by trigger timeout, taken from Pilatus so maybe not useful
        if (self.lima.acq_status == 'Fault') and (self.lima.acq_status_fault_error == 'No error'):
            self.lima.stopAcq()
            self.lima.prepareAcq()

        if self.busy():
            raise Exception('%s is busy!' % self.name)

        if dataid is None:
            # no saving
            self.lima.saving_mode = "MANUAL" # no saving
            self.saving_filename = None
        else:
            # saving
            self.lima.saving_directory = env.paths.directory
            self.lima.saving_mode = "AUTO_FRAME"
            prefix = 'scan_%06d_%s' % (dataid, self.name)
            self.lima.saving_prefix = prefix
            self.saving_filename = prefix + self.lima.saving_suffix
            if os.path.exists(self.saving_filename):
                raise Exception('Xspress3 hdf5 file already exists')

        if self.hw_trig:
            self.lima.acq_trigger_mode = "EXTERNAL_GATE"
            self.lima.acq_nb_frames = self.hw_trig_n
        else:
            self.lima.acq_trigger_mode = "INTERNAL_TRIGGER"
            self.lima.acq_nb_frames = 1

        self.image_number = -1
        self.acqtime = acqtime
        self.lima.acq_expo_time = acqtime

    def arm(self):
        """
        Start the detector if hardware triggered, just prepareAcq otherwise.
        """
        if self.busy():
            raise Exception('%s is busy!' % self.name)
        self.image_number += 1
        self.lima.prepareAcq()
        if self.hw_trig:
            self.lima.startAcq()

    def start(self):
        """
        Start acquisition when software triggered.
        """
        if self.hw_trig:
            return
        if self.busy():
            raise Exception('%s is busy!' % self.name)
        self.lima.startAcq()

    def stop(self):
        self.stop_live()
        self.lima.stopAcq()

    def busy(self):
        return not self.lima.ready_for_next_acq

    def read(self):
        if self.saving_filename is None:
            return None
        else:
            absfile = os.path.join(self.lima.saving_directory, self.saving_filename)
            return Link(absfile , 'entry_%04d/measurement/xspress3/data' % self.image_number)
