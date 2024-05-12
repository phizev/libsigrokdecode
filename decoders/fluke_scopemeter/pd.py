##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 Ryan Solomon
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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

from .lists import *
import sigrokdecode as srd

RX = 0
TX = 1
CR = 13


class State:
    BUFFERING_TX, BUFFERING_RX, PROCESSING = range(3)


class Ann:
    (COMMAND, PARAMETER, PARAMETERS, SEPARATOR, TX_CR, RX_CR, ACK, TX_ERROR, RX_ERROR, RX_SEPARATOR, RX_DETAIL,
     RESPONSE, TX_SCOPE, TX_METER, RX_SCOPE, RX_METER, TX_CS, RX_CS, TX_CS_ERR, RX_CS_ERR, TX_LENGTH, RX_LENGTH) \
        = range(22)


# noinspection PyMethodMayBeStatic
class Decoder(srd.Decoder):
    api_version = 3
    id = 'fluke_scopemeter'
    name = 'Fluke ScopeMeter'
    longname = 'Fluke ScopeMeter Control Protocol'
    desc = 'Fluke ScopeMeter remote control and programming protocol.'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = []
    tags = ['Embedded/industrial', 'IR']
    channels = (
        {'id': 'command', 'name': 'Command', 'desc': 'Commands sent to the ScopeMeter'},
        {'id': 'response', 'name': 'Response', 'desc': 'Responses from the ScopeMeter'},
    )
    optional_channels = ()
    # TODO Support syntax variations, and commands added in later series.
    options = (
        {'id': 'variant', 'desc': 'ScopeMeter Model', 'default': '91,92(B),96(B),97,99(B),105(B)',
         'values': ('91,92(B),96(B),97,99(B),105(B)',)},
    )
    annotations = (
        ('command', 'Command'),
        ('parameter', 'Command parameter'),
        ('parameters', 'Command parameters'),
        ('separator', 'Separator'),
        ('tx-terminator', 'Command terminator'),
        ('rx-terminator', 'Response terminator'),
        ('ack', 'Response status'),
        ('tx-error', 'Transmission error'),
        ('rx-error', 'Response error'),
        ('rx-separator', 'Separator'),
        ('rx-detail', 'Response detail'),
        ('response', 'Response'),
        ('tx-scope-detail', 'TX scope mode'),
        ('tx-meter-detail', 'TX meter mode'),
        ('rx-scope-detail', 'RX scope mode'),
        ('rx-meter-detail', 'RX meter mode'),
        ('tx-cs', 'Checksum OK'),
        ('rx-cs', 'Checksum OK'),
        ('tx-cs-err', 'Checksum Error'),
        ('rx-cs-err', 'Checksum Error'),
        ('tx-length', 'Length'),
        ('rx-length', 'Length'),
    )
    annotation_rows = (
        ('tx-scope-details', 'TX scope mode', (Ann.TX_SCOPE,)),
        ('tx-meter-details', 'TX meter mode', (Ann.TX_METER,)),
        ('tx-details', 'Command details', (Ann.PARAMETER, Ann.SEPARATOR, Ann.TX_CS, Ann.TX_CS_ERR, Ann.TX_LENGTH)),
        ('commands', 'Commands', (Ann.COMMAND, Ann.PARAMETERS, Ann.TX_CR, Ann.TX_ERROR)),
        ('responses', 'Responses', (Ann.RX_CR, Ann.ACK, Ann.RX_ERROR, Ann.RESPONSE)),
        ('rx-details', 'Response details', (Ann.RX_SEPARATOR, Ann.RX_DETAIL, Ann.RX_CS, Ann.RX_CS_ERR, Ann.RX_LENGTH)),
        ('rx-scope-details', 'RX scope mode', (Ann.RX_SCOPE,)),
        ('rx-meter-details', 'RX meter mode', (Ann.RX_METER,)),
    )

    def __init__(self):
        self.xfer_length = 0
        self.buffer = None
        self.cache = None
        self.command_scope = None
        self.out_ann = None
        self.progress = None
        self.reset_required = None
        self.state = None
        self.reset()

    def reset(self):
        self.xfer_length = 0
        self.buffer = {TX: '', RX: ''}
        self.cache = {TX: [], RX: []}
        self.command_scope = None
        self.progress = None
        self.reset_required = False
        self.state = State.BUFFERING_TX

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self, startsample, endsample, data):
        ptype, rxtx, pdata = data

        if ptype != 'DATA':
            return

        if self.state == State.BUFFERING_TX and rxtx == RX:
            self.aput(startsample, endsample, [Ann.RX_ERROR, ['Bad/Unknown RX', 'Bad RX', 'BRX']])
            return

        elif self.state == State.BUFFERING_RX and rxtx == TX:
            self.aput(startsample, endsample, [Ann.TX_ERROR, ['Bad/Unknown TX', 'Bad TX', 'BTX']])
            return

        # Buffer data until we get a terminator (CR).
        if (self.state == State.BUFFERING_TX and rxtx == TX) or (self.state == State.BUFFERING_RX and rxtx == RX):
            self.update_buffer(rxtx, startsample, endsample, pdata)

            if rxtx == TX:
                # Buffer text data until we get a terminator (CR).
                if pdata[0] == CR:
                    self.state = State.PROCESSING
                else:
                    return
            else:
                if self.cmd_xfer_type(self.command_scope) == 'BINARY':
                    # We need to get to the first comma, then skip the first 2 bytes to get the length.
                    # <ACK><CR><length ...><comma>
                    # For binary data, buffer until that length is reached.
                    # 8 is arbitrary, it's just to ensure we get the comma in the string.
                    if self.xfer_length == 0 and len(self.buffer[RX][2:]) > 8:
                        bin_length, len_length = self.transfer_length(self.buffer[RX][2:])
                        self.xfer_length = bin_length + len_length + 1
                    elif 0 < self.xfer_length <= len(self.buffer[RX][2:]):
                        self.state = State.PROCESSING
                    else:
                        return
                else:
                    # Buffer text data until we get a terminator (CR).
                    if pdata[0] == CR:
                        self.state = State.PROCESSING
                    else:
                        return

        if self.state == State.PROCESSING:
            if rxtx == TX:
                if len(self.buffer[TX]) == 1 and self.cache[TX][0]['data'] == CR:
                    self.command_scope = 'NONE_CR'

                if self.command_scope is None:
                    self.command_scope = self.buffer[TX][:2].upper()

                if self.command_scope not in commands:
                    self.command_scope = 'UNKNOWN'

            callback = commands.get(self.command_scope)['callback']
            fn = getattr(self, callback)
            annotations = fn(rxtx)

            if annotations is not None:
                for annotation in annotations:
                    start, end, ann = annotation
                    self.aput(start, end, ann)

        if self.reset_required is True:
            self.reset()

    def aput(self, start: int, end: int, data: list) -> None:
        """
        Wrapper function to avoid the third argument of put() on every use.

        :param start: Start sample number
        :param end: End sample number
        :param data: The annotation for the sample run
        :return:
        """
        return self.put(start, end, self.out_ann, data)

    def update_buffer(self, rxtx: int, startsample: int, endsample: int, data: list) -> None:
        """
        Add another character to the cache, and string buffer

        :param rxtx: Direction of the transfer
        :param startsample: Absolute start sample number of the data chunk
        :param endsample: Absolute end sample number of the data chunk
        :param data: Details of the chunk from the UART decoder
        """
        self.cache[rxtx].append({'data': data, 'start': startsample, 'end': endsample})
        text = chr(data[0])
        self.buffer[rxtx] += text

    def handle_response_code(self, cache: dict) -> tuple[int, int, list]:
        """
        Handles the ack response code, resets the state if non-zero

        :param cache: Transfer cache
        :return: Annotation for response code
        """
        ack = chr(cache[RX][0]['data'][0])

        # If ack is not zero, we have a problem, reset once output is done.
        if ack != '0':
            self.reset_required = True

        return self.ann_response_code(cache)

    def ann_binary(self) -> list[tuple[int, int, list]]:
        """
        Annotation of a binary response

        :return: Annotation tuples for a binary response
        """
        buffer = self.buffer[RX]
        cache = self.cache[RX]
        command = self.command_scope

        bin_length, len_length = self.transfer_length(buffer[2:])
        start, end = self.text_run(cache[len_length + 1:])

        length_string = [Ann.RX_LENGTH, ['Length: ' + str(bin_length), str(bin_length)]]
        separator_string = [Ann.RX_SEPARATOR, ['Separator: ,', ',']]
        separator_item = cache[len_length + 2]
        rx_string = [commands[command]['name'] + ' binary response', command + ' binary RX', 'Binary']

        return [(cache[2]['start'], cache[len_length + 1]['end'], length_string),
                (separator_item['start'], separator_item['end'], separator_string),
                (start, end, [Ann.RX_DETAIL, rx_string]),
                self.ann_checksum(self.cache, buffer[len_length + 3:-1], RX)]

    def ann_checksum(self, cache: list[dict], buffer: str, rxtx: int) -> tuple[int, int, list[list[str]]]:
        """
        Annotation for the checksum byte

        :param cache: Cache for the current command scope
        :param buffer: The string used for the checksum calculation
        :param rxtx: Whether the transfer is TX, or RX
        :return: Tuple for the annotation of the checksum
        """

        if self.calc_checksum(buffer) == cache[rxtx][-1]['data'][0]:
            result = 'OK'
            if rxtx == RX:
                xdir = Ann.RX_CS
            else:
                xdir = Ann.TX_CS
        else:
            result = 'Error'
            if rxtx == RX:
                xdir = Ann.RX_CS_ERR
            else:
                xdir = Ann.TX_CS_ERR

        return cache[rxtx][-1]['start'], cache[rxtx][-1]['end'], [xdir, ['Checksum ' + result, 'Xsum ' + result]]

    def ann_cmd_details(self, command: str) -> list:
        command_name = commands[command]['name']
        return [Ann.COMMAND, [command_name + ' (' + command + ')', command_name, command]]

    def ann_cmd_param(self, data: dict) -> tuple[int, int, list]:
        return (data['start'], data['end'],
                [Ann.PARAMETER, [data['param_name'] + ': ' + data['string'], data['string']]])

    def ann_cmd_params(self, command: str) -> list:
        command_name = commands[command]['name']
        return [Ann.PARAMETERS, [command_name + ' parameters', command + ' param']]

    def ann_cr(self, cache: list[dict], rxtx: int, index=-1) -> tuple[int, int, list[list[str]]]:
        """
        Annotation for the terminator/CR byte.

        :param cache: Cache for the current command scope.
        :param rxtx: Whether the transfer is TX, or RX
        :param index: Position of the terminator, defaults to the last item in the cache
        :return: Tuple for the annotation of the terminator/CR
        """
        if rxtx == RX:
            xdir = Ann.RX_CR
        else:
            xdir = Ann.TX_CR

        return cache[rxtx][index]['start'], cache[rxtx][index]['end'], [xdir, ['<CR>', 'CR']]

    def ann_plain_text(self) -> list[tuple[int, int, list]]:
        """
        Annotation of a plain text response

        :return: Annotation tuple for a plain text response
        """
        start, end = self.text_run(self.cache[RX])
        rx_string = self.buffer[RX][2:-1]
        return [(start, end, [Ann.RX_DETAIL, [rx_string]]), self.ann_cr(self.cache, RX)]

    def ann_register_responses(self) -> list[tuple[int, int, list]]:
        """
        Annotates the register responses for the IS, and ST queries.

        :return: The register annotations
        """
        start, end = self.text_run(self.cache[RX])
        cache = self.cache[RX][2:-1]
        data = cache[0]['data'][1]
        message = []
        reg_data = []
        if self.command_scope == 'ST':
            reg_data = status_query_data
        elif self.command_scope == 'IS':
            reg_data = instrument_status_data

        if len(cache) > 1:
            data.append(cache[1]['data'][1])
        data_len = len(data)

        for bit in reg_data:
            bit_position = bit.bit
            if data_len > bit_position and data[bit_position][0] == 1:
                message.append(bit.desc)

        if len(message) == 0:
            rx_string = 'Register empty'
        else:
            rx_string = ', '.join(message)

        return [(start, end, [Ann.RX_DETAIL, [rx_string]]), self.ann_cr(self.cache, RX)]

    def ann_response_code(self, cache: dict) -> tuple[int, int, list]:
        """
        Annotation for the ack response code

        :param cache: Transfer cache
        :return: Annotation for response code
        """
        status = {
            '0': 'Ok',
            '1': 'Syntax Error',
            '2': 'Execution Error',
            '3': 'Synchronization Error',
            '4': 'Communication Error'
        }
        item = cache[RX][0]
        ack = chr(item['data'][0])

        if ack in status:
            response = status[ack]
        else:
            response = 'Unknown Acknowledge'

        return item['start'], item['end'], [Ann.ACK, [response + ' (' + ack + ')', response, ack]]

    def ann_separator(self, rxtx: int, data: dict) -> tuple[int, int, list]:
        """
        Annotation for a separator.

        :param rxtx:
        :param data: Data chunk for the seperator character
        :return: Annotation string for a separator character
        """
        if rxtx == TX:
            xdir = Ann.SEPARATOR
        else:
            xdir = Ann.RX_SEPARATOR
        return data['start'], data['end'], [xdir, [data['string']]]

    def trim_param_start(self, cache):
        # Trim any leading space/tab characters.
        for item in cache:
            if item['data'][0] in [9, 32]:
                del cache[0]
            else:
                break

        return cache

    def response_organise(self) -> dict:
        ann = {}
        args = self.cache[RX][2:-1]
        if self.cmd_v_present():
            rx_items = ({
                            'name': 'Measurement value',
                        },)
        else:
            rx_items = ({
                            'name': 'Measurement type',
                        },
                        {
                            'name': 'Measurement value',
                        },
                        {
                            'name': 'Unit suffix',
                        },)
        # Response separators: comma
        comma = 44
        i = 0
        for item in args:
            if (item['data'][0] == comma and
                    (len(ann) == 0 or ann[i]['type'] != 'separator')):
                i += 1
                ann[i] = {'string': chr(item['data'][0]),
                          'data': [item['data']],
                          'type': 'separator',
                          'start': item['start'],
                          'end': item['end']}
            elif len(ann) == 0 or ann[i]['type'] != 'rx_data':
                i += 1
                ann[i] = {'string': chr(item['data'][0]),
                          'data': [item['data']],
                          'type': 'rx_data',
                          'start': item['start'],
                          'end': item['end']}
            else:
                ann[i]['string'] += chr(item['data'][0])
                ann[i]['data'].append(item['data'])
                ann[i]['end'] = item['end']

        j = 0
        values = len(rx_items)
        for k, item in ann.items():
            if item['type'] == 'rx_data':
                if j < values:
                    ann[k]['name'] = rx_items[j]['name']
                    j += 1
                else:
                    ann[k]['name'] = 'Unknown response data'

        return ann

    def cmd_s_present(self) -> bool:
        return chr(self.cache[TX][-1]['data'][0]).upper() == 'S'

    def cmd_v_present(self) -> bool:
        return chr(self.cache[TX][-1]['data'][0]).upper() == 'V'

    def command_param_organise(self, command: str) -> dict:
        ann = {}
        cache = self.cache[TX][2:-1]
        cmd_params = commands[command]['parameters']
        # Parameter separators: tab, space, comma
        separators = [9, 32, 44]
        args = self.trim_param_start(cache)
        i = 0
        for item in args:
            if (item['data'][0] in separators and
                    (len(ann) == 0 or ann[i]['type'] != 'separator')):
                i += 1
                ann[i] = {'string': chr(item['data'][0]),
                          'data': [item['data']],
                          'type': 'separator',
                          'start': item['start'],
                          'end': item['end']}
            elif len(ann) == 0 or ann[i]['type'] != 'parameter':
                i += 1
                ann[i] = {'string': chr(item['data'][0]),
                          'data': [item['data']],
                          'type': 'parameter',
                          'start': item['start'],
                          'end': item['end']}
            else:
                ann[i]['string'] += chr(item['data'][0])
                ann[i]['data'].append(item['data'])
                ann[i]['end'] = item['end']

        j = 0
        num_params = len(cmd_params)
        for k, item in ann.items():
            if item['type'] == 'parameter':
                if j < num_params:
                    ann[k]['param_name'] = cmd_params[j]['name']
                    j += 1
                else:
                    ann[k]['param_name'] = 'Unknown parameter'

        return ann

    def cmd_param_format(self, organised_params: dict) -> list:
        annotations = []
        for k in organised_params:
            item = organised_params[k]
            if item['type'] == 'separator':
                annotations.append(self.ann_separator(TX, item))
            else:
                annotations.append(self.ann_cmd_param(item))
        return annotations

    def handle_program_waveform_cmd(self, rxtx: int) -> list[tuple[int, int, list]]:
        # TODO PW snowflake
        return self.handle_simple_cmd(rxtx)

    def ann_query_measurement_rx(self) -> list[tuple[int, int, list]]:
        # TODO QM snowflake
        # Handle SCOPE vs METER mode
        return self.ann_plain_text()

    def ann_query_setup_rx(self) -> list[tuple[int, int, list]]:
        start, end = self.text_run(self.cache[RX])
        rx_string = self.buffer[RX][2:-1]
        return [(start, end, [Ann.RX_DETAIL, [rx_string]]), self.ann_cr(self.cache, RX)]

    def ann_query_waveform_rx(self) -> list[tuple[int, int, list]]:
        # TODO QW snowflake
        return self.ann_plain_text()

    def handle_simple_cmd(self, rxtx: int) -> list[tuple[int, int, list]]:
        ann = []
        cache = self.cache[rxtx]
        command = self.command_scope
        cmd_flow = commands[command]['flow']

        if self.progress is None and rxtx is TX:
            cmd_detail = self.ann_cmd_details(command)
            ann.append((cache[0]['start'], cache[1]['end'], cmd_detail))

            if len(self.buffer[TX]) > 3:
                cmd_params = self.ann_cmd_params(command)
                start, end = self.text_run(self.cache[TX])
                ann.append((start, end, cmd_params))
                organised_params = self.command_param_organise(command)
                param_details = self.cmd_param_format(organised_params)
                for param_detail in param_details:
                    ann.append(param_detail)

            ann.append(self.ann_cr(self.cache, TX))
            self.progress = 'T'
            self.state = State.BUFFERING_RX

        if rxtx is RX:
            if self.progress == 'T':
                ann.append(self.handle_response_code(self.cache))
                ann.append(self.ann_cr(self.cache, RX, 1))
                self.progress = 'TA'
                self.state = State.BUFFERING_RX

            elif self.progress == 'TA' and cmd_flow == 'TAR':
                cmd_info = commands[command]
                if self.cmd_xfer_type(command) == 'ASCII':
                    start, end = self.text_run(self.cache[RX])
                else:
                    start, end = self.binary_run(self.cache[RX])
                ann.append((start, end, [Ann.RESPONSE, ['RX for ' + cmd_info['name'], 'RX for ' + command]]))
                callback = commands.get(self.command_scope)['response_callback']
                fn = getattr(self, callback)
                annotations = fn()
                if annotations is not None:
                    for annotation in annotations:
                        ann.append(annotation)

                self.progress = 'TAR'

            if self.progress == cmd_flow:
                self.state = State.BUFFERING_TX
                self.reset_required = True

            # elif self.progress == 'TA' and cmd_flow == 'TATA':

        return ann

    def text_run(self, cache: list[dict]) -> tuple[int, int]:
        """
        Return the absolute first, and last index of the byte run for annotation length. This assumes
        the first 2 bytes, and last byte are not wanted.
        TX: First 2 bytes are the command, and last is CR, between is the parameters.
        RX: First 2 bytes are the ack followed by CR, the last is CR, between is the response.

        :param cache: The cache of the RX, or TX response.
        :return: Tuple of the index of the first, and last bit of the annotation.
        """
        return cache[2]['start'], cache[-2]['end']

    def binary_run(self, cache: list[dict]) -> tuple[int, int]:
        """
        Return the absolute first, and last index of the byte run for annotation length. This assumes
        the first 2 bytes are not wanted.
        RX: First 2 bytes are the ack followed by CR, the rest is the response.

        :param cache: The cache of the RX response.
        :return: Tuple of the index of the first, and last bit of the annotation.
        """
        return cache[2]['start'], cache[-1]['end']

    def cmd_xfer_type(self, command: str) -> str:
        """
        Get the expected format of the response. ASCII is treated as a string, checking for a <CR> terminator.
        Binary responses are formatted as <length>,<data><checksum> so we need to collect
        <length> + <length of <length>> + 2 bytes of data in total.

        :param command: A 2 letter command.
        :return: Whether the expected response is BINARY, or ASCII.
        """
        if command in ['QP', 'QG']:
            return 'BINARY'
        else:
            return 'ASCII'

    def transfer_length(self, string: str) -> tuple[int, int]:
        """
        Gets the length parameter of a transfer.

        :param string: String of the form <length>,<data>
        :return: Tuple of the <length>, and length of the <length>
        """
        items = string.split(',', 1)
        if len(items) == 2:
            return int(items[0]), len(items[0])

    def calc_checksum(self, string: str) -> int:
        """
        Calculates a checksum for a given string.

        :param string: The string to calculate the checksum for.
        :return: The calculated checksum.
        """
        cs = 0
        for char in string:
            cs = (cs + ord(char)) & 255
        return cs
