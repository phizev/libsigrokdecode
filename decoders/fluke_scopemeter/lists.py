##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 Ryan Zev Solomon
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##
from collections import namedtuple

# Key for command 'flow'
# T - Transmit
# A - ACK
# R - Receive

# SAVE SETUP (SS)
SS_setups = {}
for i in range(1, 41):
    SS_setups[str(i)] = 'Stored setup ' + str(i)
SS_setups += {'101': 'Live trace setup',
              '102': 'Live trace setup',
              '103': 'Live trace setup'}
for i in range(1, 21):
    SS_setups[str(103 + i)] = 'Stored waveform setup ' + str(i)

# RECALL SETUP (RS)
RS_setups = SS_setups
for i in range(1, 11):
    RS_setups[str(60 + i)] = 'Stored screen setup ' + str(i)
for i in range(1, 9):
    RS_setups[str(91 + i)] = 'Live trace setup'

# PROGRAM WAVEFORM (PW) traces
PW_traces = {'101': 'INPUT A', '102': 'INPUT B', '103': 'A +/- B'}
for i in range(1, 21):
    PW_traces[str(103 + i)] = 'Stored waveform ' + str(i)

# QUERY WAVEFORM (QW) traces
QW_traces = {'88': 'ScopeRecord INPUT A',
             '89': 'ScopeRecord INPUT B',
             '92': 'Max A',
             '93': 'Min A',
             '94': 'Max B',
             '95': 'Min B',
             '96': 'Max Trend',
             '97': 'Avg Trend',
             '98': 'Min Trend'}
QW_traces += PW_traces

# VIEW SCREEN (VS)
VS_screens = {'0': 'Exit View Screen mode'}
for i in range(1, 11):
    VS_screens[str(i)] = 'View screen ' + str(i)

# QUERY MEASUREMENT (QM) Scope mode parameters
QMScopeField = namedtuple('QMScopeField', 'field_no, mtype, desc')
QMScopeField.__doc__ += ': Command parameter values for QM in scope mode'
QMScopeField.field_no.__doc__ = 'Field number for field_no parameter'
QMScopeField.mtype.__doc__ = 'Measurement type'
QMScopeField.desc.__doc__ = 'Description of the measurement'

QM_scope_field_no = (
    QMScopeField(1, 'dV', 'Voltage between cursors'),
    QMScopeField(2, 'dt', 'Time between cursors'),
    QMScopeField(3, '1/dt', 'Reciprocal of field no 2'),
    QMScopeField(4, 't1 from TRIG', 'Trigger to cursor left'),
    QMScopeField(5, 'RMS', 'RMS value'),
    QMScopeField(6, 'MEAN', 'MEAN value'),
    QMScopeField(7, 'P-P', 'Peak to Peak voltage'),
    QMScopeField(8, 'MAX-P', 'Maximum peak voltage'),
    QMScopeField(9, 'MIN-P', 'Minimum peak voltage'),
    QMScopeField(10, 'FREQ', 'Signal frequency'),
    QMScopeField(11, 'RISE', 'Rise time (10% to 90%)'),
    QMScopeField(12, 'PHASE src>des1', 'Phase src to destination'),
    QMScopeField(13, 'PHASE src>des2', 'Phase src to destination'),
    QMScopeField(14, 'PHASE src>des3', 'Phase src to destination'),
    QMScopeField(15, 'V1', 'Voltage at cursor left'),
    QMScopeField(16, 'V2', 'Voltage at cursor right'),
    QMScopeField(17, 't2 from TRIG', 'Trigger to cursor right'),
    QMScopeField(18, 't1 from START', 'Time from start to cursor left'),
    QMScopeField(19, 't2 from START', 'Time from start to cursor right'),
    QMScopeField(20, 't1 time of day', 'Real time stamp at cursor left'),
    QMScopeField(21, 't2 time of day', 'Real time stamp at cursor right'),
)

# QUERY MEASUREMENT (QM) Meter mode parameters
QMMeterField = namedtuple('QMScopeField', 'field_no, desc')
QMMeterField.__doc__ += ': Command parameter values for QM in meter mode'
QMMeterField.field_no.__doc__ = 'Field number for field_no parameter'
QMMeterField.desc.__doc__ = 'Description of the measurement'

QM_meter_field_no = (
    QMMeterField(1, 'First measurement result'),
    QMMeterField(2, 'Second measurement result'),
    QMMeterField(3, 'First calculated result'),
    QMMeterField(4, 'Maximum (record) result'),
    QMMeterField(5, 'Average (record) result'),
    QMMeterField(6, 'Minimum (record) result'),
    QMMeterField(7, 'Time stamp of last recorded maximum'),
    QMMeterField(8, 'Time stamp of last recorded average'),
    QMMeterField(9, 'Time stamp of last recorded minimum'),
    QMMeterField(10, 'Third measurement result'),
    QMMeterField(11, 'Fourth measurement result'),
    QMMeterField(12, 'Record MAX-MIN'),
    QMMeterField(13, 'Time and date stamp of last recorded maximum'),
    QMMeterField(14, 'Time and date stamp of last recorded average'),
    QMMeterField(15, 'Time and date stamp of last recorded minimum'),
)

commands = {
    # Handles the situation where no command is sent, only the terminator.
    'NONE_CR': {
        'name': 'Command terminator',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_none_cmd',
    },
    # Handles a command which is not present in this list.
    'UNKNOWN': {
        'name': 'Unknown command',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'AS': {
        'name': 'AUTO SETUP',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'AT': {
        'name': 'ARM TRIGGER',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'CV': {
        'name': 'CPL VERSION QUERY',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_plain_text',
    },
    'DS': {
        'name': 'DEFAULT SETUP',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'GL': {
        'name': 'GO TO LOCAL',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'GR': {
        'name': 'GO TO REMOTE',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'ID': {
        'name': 'IDENTIFICATION',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_plain_text',
    },
    'IS': {
        'name': 'INSTRUMENT STATUS',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_register_responses',
    },
    'LL': {
        'name': 'LOCAL LOCKOUT',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'PC': {
        'name': 'PROGRAM COMMUNICATION',
        'parameters': (
            {
                'name': 'Baud rate',
                'required': True,
                'values': (75, 110, 150, 300, 600, 1200, 2400, 4800, 9600, 19200, 38400),
            },
            {
                'name': 'Parity',
                'required': True,
                'values': ('O', 'E', 'N'),
            },
            {
                'name': 'Data bits',
                'required': True,
                'values': (7, 8),
            },
            {
                'name': 'Stop bits',
                'required': True,
                'values': (1,),
            },
            {
                'name': 'Handshake',
                'required': False,
                'values': ('XONXOFF',),
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'PS': {
        'name': 'PROGRAM SETUP',
        'parameters': (
            {
                'name': '1',
                'required': True,
                'values': ('1',),
            },
            {
                'name': 'Setup',
                'required': True,
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'PW': {  # Snowflake
        'name': 'PROGRAM WAVEFORM',
        'parameters': (
            {
                'name': 'Trace no',
                'required': True,
                'values': PW_traces,
            },
            {
                'name': 'Setup',
                'required': False,
                'values': ('S',),
            },
        ),
        'flow': 'TATA',
        'callback': 'handle_program_waveform_cmd',
    },
    # Used by FlukeView to get a screenshot of the ScopeMeter.
    'QG': {
        'name': 'QG - UNDOCUMENTED',
        'parameters': (
            {
                'name': 'UNDOCUMENTED',
                'required': True,
            },
        ),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_binary',
    },
    'QM': {  # Snowflake
        'name': 'QUERY MEASUREMENT',
        # TODO handle SCOPE vs METER mode.
        'parameters': {
            'scope_mode': (
                {
                    'name': 'Field no',
                    'required': True,
                    'values': QM_scope_field_no,
                },
                {
                    'name': 'Values only',
                    'required': False,
                    'values': ('V',),
                },
            ),
            'meter_mode': (
                {
                    'name': 'Field no',
                    'required': True,
                    'values': QM_meter_field_no,
                },
                {
                    'name': 'Values only',
                    'required': False,
                    'values': ('V',),
                },
            ),
        },
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'handle_query_measurement_rx',
    },
    'QP': {
        'name': 'QUERY PRINT',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_binary',
    },
    'QS': {
        'name': 'QUERY SETUP',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'handle_query_setup_rx',
    },
    'QW': {  # Snowflake
        'name': 'QUERY WAVEFORM',
        'parameters': (
            {
                'name': 'Trace no',
                'required': True,
                'values': QW_traces,
            },
            {
                'name': 'Format option',
                'required': False,
                'values': ('V', 'S'),
            },
        ),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'handle_query_waveform_rx',
    },
    'RD': {
        'name': 'READ DATE',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_plain_text',
    },
    'RI': {
        'name': 'RESET INSTRUMENT',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'RS': {
        'name': 'RECALL SETUP',
        'parameters': (
            {
                'name': 'Setup register',
                'required': True,
                'values': RS_setups
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'RT': {
        'name': 'READ TIME',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_plain_text',
    },
    'SS': {
        'name': 'SAVE SETUP',
        'parameters': (
            {
                'name': 'Setup register',
                'required': True,
                'values': SS_setups,
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'ST': {
        'name': 'STATUS QUERY',
        'parameters': (),
        'flow': 'TAR',
        'callback': 'handle_simple_cmd',
        'response_callback': 'ann_register_responses',
    },
    'TA': {
        'name': 'TRIGGER ACQUISITION',
        'parameters': (),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'VS': {
        'name': 'VIEW SCREEN',
        'parameters': (
            {
                'name': 'View screen',
                'required': True,
                'values': VS_screens,
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'WD': {
        'name': 'WRITE DATE',
        'parameters': (
            {
                'name': 'Date',
                'required': True,
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
    'WT': {
        'name': 'WRITE TIME',
        'parameters': (
            {
                'name': 'Time',
                'required': True,
            },
        ),
        'flow': 'TA',
        'callback': 'handle_simple_cmd',
    },
}

RegBit = namedtuple('RegBit', ['bit', 'dec', 'desc'])
RegBit.__doc__ += ': Register bit to message mapping'
RegBit.bit.__doc__ = 'Register bit position'
RegBit.dec.__doc__ = 'Decimal value of a register bit'
RegBit.desc.__doc__ = 'Description of a register bit'

instrument_status_data = (
    RegBit(0, 1, 'Hardware settled'),
    RegBit(1, 2, 'Acquisition armed'),
    RegBit(2, 4, 'Acquisition triggered'),
    RegBit(3, 8, 'Acquisition busy'),
    RegBit(4, 16, 'WAVEFORM A memory filled'),
    RegBit(5, 32, 'WAVEFORM B memory filled'),
    RegBit(6, 64, 'WAVEFORM A+/-B memory filled'),
    RegBit(7, 128, 'Math function ready'),
    RegBit(8, 256, 'Numeric results available'),
    RegBit(9, 512, 'Hold mode active'),
)

status_query_data = (
    RegBit(0, 1, 'Illegal command'),
    RegBit(1, 2, 'Wrong parameter data format'),
    RegBit(2, 4, 'Parameter out of range'),
    RegBit(3, 8, 'Instruction not valid in present state'),
    RegBit(4, 16, 'Called function not implemented'),
    RegBit(5, 32, 'Invalid number of parameters'),
    RegBit(6, 64, 'Wrong number of data bits'),
    RegBit(9, 512, 'Conflicting instrument settings'),
    RegBit(14, 16384, 'Checksum error'),
)
