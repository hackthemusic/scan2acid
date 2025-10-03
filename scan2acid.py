import re
import html
import socket
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import mido
from mido import Message, MidiFile, MidiTrack
from simple_term_menu import TerminalMenu
import random
import configparser

# change these values to adjust how the port scanning results are mapped to musical notes
OCT_SHIFT = 36
TIE_THRESHOLD = 30

# internal values for the work-in-progress port scanner
TOP_PORTS_16 = [
    80,
    443,
    22,
    21,
    25,
    23,
    3389,
    110,
    445,
    139,
    143,
    53,
    135,
    3306,
    8080,
    993,
]

SERVICE_NAME_HINTS = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    135: "rpc",
    139: "netbios",
    143: "imap",
    443: "https",
    445: "smb",
    993: "imaps",
    3306: "mysql",
    3389: "rdp",
    8080: "http-alt",
}

BANNER_VERSION_PATTERNS = [
    re.compile(r"SSH-\d+\.\d+-(?P<service>[\w-]+)_(?P<version>[\w\.\-]+)", re.I),
    re.compile(r"(?P<service>[A-Za-z0-9\-_.]+)/(?P<version>\d[\w\.\-]*)", re.I),
    re.compile(r"(?P<service>[A-Za-z0-9\-_.]+)[ ]+version[ ]+(?P<version>\d[\w\.\-]*)", re.I),
    re.compile(r"(?P<service>[A-Za-z0-9\-_.]+)_(?P<version>\d[\w\.\-]*)", re.I),
]


class Step:
    """
    A single step in a sequence of steps. Depending on the 'type' argument, it can be:
    - active: plays a note (note_on -> 16th -> note_off)
    - rest: silent step (no note played)
    - tie: the note continues to the next step in order to create slides (note_on -> 16th -> next step is tie -> next step note_off)

    Depending on the octave_mod value, the note can be played in a different octave (+1 or -1).
    Accents (arg: 'accent') can be applied to active and tie steps as well. 
    Originally, this class was meant to be used in a circular linked list, but as of now it's only a data container.

    Usage example: 
        new_step = Step(note=36, accent=True, type='active', octave_mod=0)

    Steps can also be individually modified after creation with the 'mod' method:
        step.mod(note=39, accent=False, type='tie', octave_mod=1)
    """
    def __init__(self, note=30, accent=False, type='active', octave_mod=0, is_first = False, is_last = False):
        # data section ("the payload") --------------------
        self.accent = accent
        self.note = note
        self.type = type  # 'active', 'rest', 'tie'
        self.octave_mod = octave_mod  # -1, 0, +1
        self.source = "" # where this step came from - open port, vulnerable service, whatever.

    def __str__(self):
        return f"[STEP] -> (note={self.note}, accent={self.accent}, type={self.type}, octave_mod={self.octave_mod})"
    
    def mod(self, note, octave_mod, type, accent):
        self.note = note
        self.octave_mod = octave_mod
        self.type = type
        self.accent = accent

class X03Sequence:
    """
    A sequence of steps. Default length is 16.
    
    Usage example: new_seq = X03Sequence(name="My Sequence", length=8)
    This will create a sequence with 8 default steps (all active, note=0, no accent, octave_mod=0).

    Sequences can be modified step by step with the 'mod_step' method:
        seq.mod_step(index=0, note=36, octave_mod=0, type='active', accent=True)

    In order to play a sequence, just invoke the "play" method:
        seq.play(repetitions=4, midi_interface="your_interface_here", bpm=120, channel=1, send_clock=False)
    
    You can choose to send MIDI clock messages or not by setting the 'send_clock' argument to True or False.
    If you do, the sequence will start with a "start" message and end with a "stop" message, enabling proper sync with other devices
    such as drum machines or other synthesizers/sequencers.
    """

    def __init__(self, name="X03 Sequence", length=16):
        self.name = name
        self.length = length
        self.sequence = []
        for i in range(length):
            new_step = Step(is_first = True if i == 0 else False, is_last = True if i == length - 1 else False)
            self.sequence.append(new_step)

    def __str__(self):
        seq_string = ""
        seq_string += "| "
        for step in self.sequence:
            if step.type == 'active':
                seq_string += "X "
            elif step.type == 'rest':
                seq_string += "- "
            elif step.type == 'tie':
                seq_string += "> "
            seq_string += " | "
        return f"{self.name} - {self.length} steps:\n" + seq_string.strip()
        return seq_string.strip()
        #return f"X03Sequence(name={self.name}, length={self.length}, sequence={[str(step) for step in self.sequence]})"
    
    def mod_step(self, index, note, octave_mod, type, accent):
        if 0 <= index < self.length:
            self.sequence[index].mod(note, octave_mod, type, accent)
        else:
            raise IndexError("Step does not exist. Check your sequence length.")

    def play(self, repetitions=4, midi_interface="Onyx Producer 2-2:Onyx Producer 2-2 MIDI 1 20:0", bpm=120, channel=1, send_clock=False):
        print(f">>> Now playing: {self.name}")

        quarter_note = 60 / bpm
        sixteenth_note = quarter_note / 4
        outport = mido.open_output(midi_interface)

        last_active_note = None
        clock_ticks_per_step = 6  # TD-3 expects 24 PPQ clock, six pulses per 16th
        clock_message = mido.Message('clock') if send_clock else None

        def advance_step():
            if not send_clock:
                time.sleep(sixteenth_note)
                return

            interval = sixteenth_note / clock_ticks_per_step
            for _ in range(clock_ticks_per_step):
                outport.send(clock_message)
                time.sleep(interval)

        if send_clock:
            outport.send(mido.Message('start'))

        iteration = 0
        try:
            while True:
                if repetitions > 0 and iteration >= repetitions:
                    break
                print(f"[iter {iteration}] -----------------------------------------------------")
                for j in range(self.length):
                    step = self.sequence[j]

                    if step.type == 'active':
                        velocity = 120 if step.accent else 90
                        note = step.note + (step.octave_mod * 12)
                        msg_on = mido.Message('note_on', note=note, velocity=velocity, channel=channel)
                        outport.send(msg_on)
                        print(step, end="")
                        advance_step()
                        msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel)
                        outport.send(msg_off)
                        print(" -> OFF SENT")

                        if last_active_note is not None:
                            note = last_active_note.note + (last_active_note.octave_mod * 12)
                            msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel)
                            outport.send(msg_off)
                            last_active_note = None
                            print("-> OFF SENT (from tie)")

                    elif step.type == 'rest':
                        if last_active_note is not None:
                            note = last_active_note.note + (last_active_note.octave_mod * 12)
                            msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel)
                            outport.send(msg_off)
                            last_active_note = None
                            print("-> OFF SENT (from rest)")

                        advance_step()
                        print(f"{step} -> OFF SENT")

                    elif step.type == 'tie':
                        velocity = 120 if step.accent else 90
                        note = step.note + (step.octave_mod * 12)
                        msg_on = mido.Message('note_on', note=note, velocity=velocity, channel=channel)
                        outport.send(msg_on)
                        print(step)
                        advance_step()

                        if last_active_note is not None and last_active_note != step:
                            note = last_active_note.note + (last_active_note.octave_mod * 12)
                            msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel)
                            outport.send(msg_off)
                            print("-> OFF SENT (from tie)")

                        last_active_note = step

                    else:
                        raise ValueError(f"Unknown step type: {step.type}")

                iteration += 1
        except KeyboardInterrupt:
            print("\n>>> Playback interrupted by user (Ctrl+C).")
        finally:
            if last_active_note is not None:
                note = last_active_note.note + (last_active_note.octave_mod * 12)
                outport.send(mido.Message('note_off', note=note, velocity=0, channel=channel))

            outport.send(mido.Message('control_change', control=123, value=0, channel=channel))

            if send_clock:
                outport.send(mido.Message('stop'))

            outport.close()

    # still needs fixing. it's mostly working though!
    def __to_midi(self, bpm=120, channel=1, ppq=480, repetitions=1, filename=None):
        """Render the sequence into a MIDI file and optionally save it."""
        if repetitions < 1:
            raise ValueError("repetitions must be at least 1")

        ticks_per_step = max(1, round(ppq / 4))
        midi_channel = max(0, min(15, channel - 1))

        mid = MidiFile(ticks_per_beat=ppq, type=0)
        track = MidiTrack()
        mid.tracks.append(track)

        tempo = mido.bpm2tempo(bpm)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

        running_delta = 0
        active_note = None

        def note_on(note_value, velocity, delta):
            track.append(Message('note_on', note=note_value, velocity=velocity, channel=midi_channel, time=delta))

        def note_off(note_value, delta):
            track.append(Message('note_off', note=note_value, velocity=0, channel=midi_channel, time=delta))

        for _ in range(repetitions):
            for step in self.sequence:
                note_value = max(0, min(127, step.note + (step.octave_mod * 12)))
                step_ticks = ticks_per_step

                if step.type == 'rest':
                    if active_note is not None:
                        note_off(active_note, running_delta)
                        running_delta = 0
                        active_note = None
                    running_delta += step_ticks
                    continue

                velocity = 120 if step.accent else 90

                if step.type == 'active':
                    if active_note is not None:
                        note_off(active_note, running_delta)
                        running_delta = 0
                        active_note = None
                    note_on(note_value, velocity, running_delta)
                    active_note = note_value
                    running_delta = 0
                    running_delta += step_ticks
                    continue

                if step.type == 'tie':
                    if active_note is None:
                        note_on(note_value, velocity, running_delta)
                        active_note = note_value
                        running_delta = 0
                    elif note_value != active_note:
                        note_off(active_note, running_delta)
                        running_delta = 0
                        note_on(note_value, velocity, running_delta)
                        active_note = note_value
                        running_delta = 0
                    running_delta += step_ticks
                    continue

                raise ValueError(f"Unknown step type: {step.type}")

        if active_note is not None:
            note_off(active_note, running_delta)
            running_delta = 0

        track.append(mido.MetaMessage('end_of_track', time=running_delta))

        if filename:
            mid.save(filename)

        return mid

    # still needs fixing. it's mostly working though!
    def __to_sysex(self, group=0, pattern=0, triplet_mode=False, filename=None):
        """Return the TD-3 compatible SysEx message for this sequence."""
        if not (0 <= group <= 3):
            raise ValueError("group must be between 0 and 3")
        if not (0 <= pattern <= 15):
            raise ValueError("pattern must be between 0 and 15")
        if self.length < 1:
            raise ValueError("sequence must contain at least one step")
        if self.length > 16:
            raise ValueError("TD-3 patterns support at most 16 steps")

        def encode_nibble(value):
            value = max(0, min(127, value))
            return (value >> 4) & 0x0F, value & 0x0F

        def build_mask(flag_for_index):
            nibbles = [0x00] * 4
            for idx in range(16):
                if flag_for_index(idx):
                    nibble_idx = idx // 4
                    bit_idx = idx % 4
                    nibbles[nibble_idx] |= (1 << bit_idx)
            return [n & 0x0F for n in nibbles]

        steps = [self.sequence[idx] if idx < self.length else None for idx in range(16)]

        pitches = []
        accents = []
        slides = []

        for idx, step in enumerate(steps):
            if step is None or step.type == 'rest':
                msb, lsb = encode_nibble(0x18)
                pitches.extend([msb, lsb])
                accents.extend([0x00, 0x00])
                slides.extend([0x00, 0x00])
                continue

            if step.type not in {'active', 'tie'}:
                raise ValueError(f"Unknown step type: {step.type}")

            note_value = step.note + (step.octave_mod * 12)
            msb, lsb = encode_nibble(note_value)
            pitches.extend([msb, lsb])
            accents.extend([0x00, 0x01 if step.accent else 0x00])

            slide_flag = False
            if step.type == 'tie':
                slide_flag = True
            elif idx < self.length - 1:
                next_step = self.sequence[idx + 1]
                if next_step.type == 'tie' and step.type != 'rest':
                    slide_flag = True
            slides.extend([0x00, 0x01 if slide_flag else 0x00])

        tie_mask = build_mask(lambda idx: steps[idx] is not None and steps[idx].type == 'tie')
        rest_mask = build_mask(lambda idx: steps[idx] is None or steps[idx].type == 'rest')

        step_count = max(1, min(self.length, 16))
        step_count_msb, step_count_lsb = encode_nibble(step_count)

        sysex_data = [
            0xF0, 0x00, 0x20, 0x32, 0x00, 0x01, 0x0A, 0x78,
            group & 0x0F,
            pattern & 0x1F,
            0x00, 0x00,
            *pitches,
            *accents,
            *slides,
            0x00, 0x01 if triplet_mode else 0x00,
            step_count_msb, step_count_lsb,
            0x00, 0x00,
            *tie_mask,
            *rest_mask,
            0xF7,
        ]

        data_bytes = bytes(sysex_data)

        if filename:
            with open(filename, 'wb') as fh:
                fh.write(data_bytes)

        return data_bytes

    def to_html(self, filename, *, title=None):
        """Export the sequence as an HTML table for visual inspection."""
        if not filename:
            raise ValueError("filename must be provided")

        template_path = Path(__file__).with_name("template.html")
        if not template_path.is_file():
            raise FileNotFoundError(f"HTML template not found: {template_path}")

        steps = list(self.sequence)
        if not steps:
            raise ValueError("sequence contains no steps to export")

        page_title = title or self.name
        header_title = html.escape(page_title)
        sequence_name = html.escape(self.name)
        template = template_path.read_text(encoding="utf-8")

        header_cells = ['<th scope="col">Attribute</th>']
        header_cells.extend(
            f'<th scope="col">{idx}</th>'
            for idx in range(1, len(steps) + 1)
        )
        header_html = ''.join(header_cells)

        def build_row(label, values, *, row_class=""):
            class_attr = f' class="{row_class}"' if row_class else ''
            label_cell = f'                <th scope="row">{html.escape(label)}</th>'
            value_cells = ''.join(
                f'\n                <td>{value}</td>'
                for value in values
            )
            return f'            <tr{class_attr}>\n{label_cell}{value_cells}\n            </tr>'

        type_values = [html.escape(step.type) for step in steps]
        base_notes = [str(step.note) for step in steps]
        octave_mods = [str(step.octave_mod) for step in steps]
        midi_notes = [str(step.note + (step.octave_mod * 12)) for step in steps]
        accents = ['Yes' if step.accent else 'No' for step in steps]
        sources = [
            html.escape(step.source) if step.source else '&nbsp;'
            for step in steps
        ]

        row_specs = [
            ('Type', type_values, ''),
            ('Base Note', base_notes, ''),
            ('Octave Mod', octave_mods, ''),
            ('MIDI Note', midi_notes, ''),
            ('Accent', accents, ''),
            ('Source', sources, 'source-row'),
        ]
        rows = [
            build_row(label, values, row_class=row_class)
            for label, values, row_class in row_specs
        ]
        body_rows = '\n'.join(rows)

        max_label_len = max(len('Attribute'), *(len(label) for label, _, _ in row_specs))
        attribute_width = f"{max_label_len + 2}ch"

        html_content = (
            template
            .replace('{{TITLE}}', header_title)
            .replace('{{SEQUENCE_NAME}}', sequence_name)
            .replace('{{HEADER_CELLS}}', header_html)
            .replace('{{BODY_ROWS}}', body_rows)
            .replace('{{STEP_COUNT}}', str(len(steps)))
            .replace('{{ATTRIBUTE_WIDTH}}', attribute_width)
        )

        output_path = Path(f'exports/{filename}')
        output_path.write_text(html_content, encoding="utf-8")
        return output_path

class PortService:
    """Represents a network service exposed on a given TCP port."""

    def __init__(self, port=0, service_name="unknown", version="unknown", *, banner="", is_vulnerable=False):
        self.port = port
        self.service_name = service_name or "unknown"
        self.version = version or "unknown"
        self.banner = banner.strip() if banner else ""
        self.is_vulnerable = is_vulnerable

    def __str__(self):
        vuln_str = " (vulnerable)" if self.is_vulnerable else ""
        version_part = f" {self.version}" if self.version and self.version.lower() != "unknown" else ""
        banner_part = f" | {self.banner}" if self.banner else ""
        return f"[{self.port}] {self.service_name}{version_part}"
        #return f"[{self.port}] {self.service_name}{version_part}{vuln_str}{banner_part}"

    def as_dict(self):
        return {
            "port": self.port,
            "service_name": self.service_name,
            "version": self.version,
            "banner": self.banner,
            "is_vulnerable": self.is_vulnerable,
        }

class Scanner:
    """TCP scanner that probes common ports and captures service banners."""

    def __init__(self, target="127.0.0.1"):
        self.target = target
        self.scan_results = []

    def scan(self, *, ports=None, top_n=16, timeout=1.0):
        target_ip = self._resolve_target()
        selected_ports = self._select_ports(ports, top_n)
        results = []

        for port in selected_ports:
            service = self._probe_port(target_ip, port, timeout)
            if service:
                results.append(service)

        self.scan_results = results
        return results

    def _resolve_target(self):
        try:
            return socket.gethostbyname(self.target)
        except socket.gaierror as exc:
            raise ValueError(f"Unable to resolve target '{self.target}': {exc}") from exc

    def _select_ports(self, ports, top_n):
        if ports:
            sanitized = []
            seen = set()
            for port in ports:
                try:
                    port_int = int(port)
                except (TypeError, ValueError):
                    continue
                if not (0 < port_int < 65536) or port_int in seen:
                    continue
                seen.add(port_int)
                sanitized.append(port_int)
            return sorted(sanitized)

        if top_n <= 0:
            top_n = 1

        return TOP_PORTS_16[: min(top_n, len(TOP_PORTS_16))]

    def _probe_port(self, target_ip, port, timeout):
        try:
            with socket.create_connection((target_ip, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                banner = self._grab_banner(sock, port)
                service_name, version = self._interpret_banner(port, banner)
                return PortService(port=port, service_name=service_name, version=version, banner=banner)
        except (socket.timeout, ConnectionRefusedError, OSError):
            return None

    def _grab_banner(self, sock, port):
        banner = self._recv_banner(sock)
        if banner:
            return banner

        for probe in self._build_probes(port):
            try:
                sock.sendall(probe)
            except OSError:
                break

            banner = self._recv_banner(sock)
            if banner:
                return banner

        return ""

    def _recv_banner(self, sock, chunk_size=4096, max_reads=2):
        data_parts = []
        reads = 0

        while reads < max_reads:
            reads += 1
            try:
                chunk = sock.recv(chunk_size)
            except (socket.timeout, OSError):
                break

            if not chunk:
                break

            data_parts.append(chunk)
            if len(chunk) < chunk_size:
                break

        if not data_parts:
            return ""

        data = b"".join(data_parts)
        return data.decode("utf-8", errors="ignore").strip()

    def _build_probes(self, port):
        host = self.target
        http_probe = (
            f"HEAD / HTTP/1.0\r\nHost: {host}\r\nUser-Agent: scan2acid/0.1\r\nConnection: close\r\n\r\n".encode("ascii")
        )

        if port in {80, 8080, 8000, 8888}:
            return [http_probe]
        if port == 443:
            return [http_probe]
        if port in {21, 25, 110, 143}:
            return [b"\r\n"]
        if port == 23:
            return [b"\r\n"]

        return []

    def _interpret_banner(self, port, banner):
        service_name = SERVICE_NAME_HINTS.get(port, "unknown")
        version = "unknown"

        if not banner:
            return service_name, version

        cleaned = banner.strip()
        lowered = cleaned.lower()

        if port in {80, 8080, 8000, 8888, 443}:
            server_header = self._extract_header(cleaned, "server")
            if server_header:
                service_name, version = self._split_service_version(server_header)
            if port == 443 and service_name == "unknown":
                service_name = "https"

        if service_name == "unknown" or version == "unknown":
            for pattern in BANNER_VERSION_PATTERNS:
                match = pattern.search(cleaned)
                if match:
                    candidate_service = match.group("service").lower().replace("_", "-")
                    candidate_version = match.group("version")
                    if service_name == "unknown":
                        service_name = candidate_service
                    if version == "unknown":
                        version = candidate_version
                    break

        if "ssh" in lowered:
            ssh_match = re.search(r"ssh-\d+\.\d+-([\w-]+)_([\w\.\-]+)", cleaned, re.I)
            if ssh_match:
                service_name = ssh_match.group(1).lower()
                version = ssh_match.group(2)
            elif service_name == "unknown":
                service_name = "ssh"

        if service_name == "unknown" and port in SERVICE_NAME_HINTS:
            service_name = SERVICE_NAME_HINTS[port]

        return service_name, version

    def _extract_header(self, banner, header):
        header_prefix = f"{header.lower()}:"
        for line in banner.splitlines():
            if line.lower().startswith(header_prefix):
                return line.split(":", 1)[1].strip()
        return ""

    def _split_service_version(self, text):
        for pattern in BANNER_VERSION_PATTERNS:
            match = pattern.search(text)
            if match:
                service = match.group("service").lower().replace("_", "-")
                version = match.group("version")
                return service, version

        return text.lower(), "unknown"

class Parser:
    def __init__(self, xml_path=None):
        self.name = "scan2acid parser"
        self.xml_path = Path(xml_path) if xml_path else None
        self._services = []

    def parse(self, xml_path=None):
        path = self._resolve_path(xml_path)
        root = ET.parse(path).getroot()
        services = []

        for host in root.findall("host"):
            ports_el = host.find("ports")
            if ports_el is None:
                continue

            for port_el in ports_el.findall("port"):
                service = self._parse_port_element(port_el)
                if service:
                    services.append(service)

        self._services = services
        return services

    def get_services(self):
        return list(self._services)

    def services_as_dicts(self):
        return [service.as_dict() for service in self._services]

    def _resolve_path(self, xml_path):
        candidate = xml_path or self.xml_path
        if candidate is None:
            raise ValueError("Parser.parse requires an XML path")

        path = Path(candidate)
        if not path.is_file():
            raise FileNotFoundError(f"XML file not found: {path}")

        self.xml_path = path
        return path

    def _parse_port_element(self, port_el):
        state_el = port_el.find("state")
        if state_el is None or state_el.get("state") != "open":
            return None

        try:
            port_number = int(port_el.get("portid", 0))
        except (TypeError, ValueError):
            return None

        service_el = port_el.find("service")
        service_name = SERVICE_NAME_HINTS.get(port_number, "unknown")
        version = "unknown"
        banner = ""

        if service_el is not None:
            raw_name = service_el.get("name") or service_el.get("product")
            if raw_name:
                service_name = raw_name

            product = service_el.get("product") or ""
            version_attr = service_el.get("version") or ""
            extrainfo = service_el.get("extrainfo") or ""

            version_parts = [part for part in (product, version_attr, extrainfo) if part]
            if version_parts:
                unique_parts = list(dict.fromkeys(version_parts))
                version = " ".join(unique_parts)

            banner_bits = []
            for key in ("product", "version", "extrainfo", "hostname", "tunnel", "ostype"):
                value = service_el.get(key)
                if value:
                    banner_bits.append(f"{key}={value}")

            cpe_values = [cpe.text for cpe in service_el.findall("cpe") if cpe.text]
            if cpe_values:
                banner_bits.append("cpe=" + ",".join(cpe_values))

            if banner_bits:
                banner = "; ".join(banner_bits)

        if service_name == "unknown" and port_number in SERVICE_NAME_HINTS:
            service_name = SERVICE_NAME_HINTS[port_number]

        return PortService(port=port_number, service_name=service_name, version=version, banner=banner)

class Manager:
    def __init__(self):
        self.name = "scan2acid manager"
        self.sequences = []
    
    def print_help(self):
        print("Available commands:")
        print("  help           - Show this help message")
        print("  demo           - Play a demo sequence (with MIDI sync)")
        print("  parse          - Parses an nmap XML file (nmap -sV --open --top-ports 16 -oX file.xml <target>).")
        print("                     > After parsing, you can choose to convert the scan into a 303 sequence.")
        print("  list midi      - List available MIDI output interfaces")
        print("  list sequences - List available sequences")
        print("  play           - Play a sequence (interactive menu)")
        print("  export         - Export a sequence to a file (interactive menu)")
        print("  exit, quit, q  - Exit the prompt")

    def play_demo_sequence(self):
        options = mido.get_output_names()
        menu = TerminalMenu(options, title="Select a MIDI output interface for playback")
        menu_entry_index = menu.show()
        midi_interface = options[menu_entry_index]
        
        print(">>> Playing demo sequence...")
        # da_funk = [55, 58, 55, 53, 39, 36, 48, 36, 51, 51, 53, 55, 58, 55, 48, 55]

        df_seq = X03Sequence(length=16, name="Daft Punk - Da Funk")
        df_seq.mod_step(0, note=43, octave_mod=0, type='active', accent=False)
        df_seq.mod_step(1, note=46, octave_mod=0, type='active', accent=False)
        df_seq.mod_step(2, note=43, octave_mod=0, type='tie', accent=False)
        df_seq.mod_step(3, note=41, octave_mod=0, type='active', accent=False)
        df_seq.mod_step(4, note=27, octave_mod=0, type='tie', accent=True)
        df_seq.mod_step(5, note=24, octave_mod=0, type='active', accent=False)
        df_seq.mod_step(6, note=36, octave_mod=-1, type='tie', accent=True)
        df_seq.mod_step(7, note=24, octave_mod=1, type='active', accent=True)
        df_seq.mod_step(8, note=39, octave_mod=1, type='tie', accent=False)
        df_seq.mod_step(9, note=39, octave_mod=0, type='active', accent=False)
        df_seq.mod_step(10, note=41, octave_mod=1, type='tie', accent=False)
        df_seq.mod_step(11, note=43, octave_mod=1, type='tie', accent=True)
        df_seq.mod_step(12, note=46, octave_mod=0, type='active', accent=True)
        df_seq.mod_step(13, note=43, octave_mod=0, type='tie', accent=False)
        df_seq.mod_step(14, note=36, octave_mod=0, type='tie', accent=False)
        df_seq.mod_step(15, note=43, octave_mod=1, type='active', accent=False)

        print(df_seq)

        df_seq.play(bpm=111, repetitions=4, send_clock=True, midi_interface=midi_interface, channel=1)

    def choose_scale(self):
        config = configparser.ConfigParser()
        config.read('./scales.conf')
        scales = config.sections()
        menu = TerminalMenu(scales, title="Select a musical scale for mapping services to notes. Add your own on 'scales.conf'")
        menu_entry_index = menu.show()
        chosen_scale = scales[menu_entry_index]
        print(f"Chosen scale: {chosen_scale}")
        return config[chosen_scale]
    
    def is_accent(self, keywords, service):
        service_full = f"{service.service_name} {service.version}".lower()
        for keyword in keywords:
            cleaned = keyword.strip().strip("'\"").lower()
            if cleaned and cleaned in service_full:
                return True
        return False
    
    def is_tie(self, service):
        service_full = f"{service.service_name} {service.version}"
        return len(service_full) > TIE_THRESHOLD

    def to_303(self, services):
        name = input("Enter a name for the new 303 sequence: ").strip() or "scan2acid import"
        new_seq = X03Sequence(length=8 if len(services) <= 8 else 16, name=name)
        random.seed(time.time())
        random_qty = (8 - len(services)) if len(services) <= 8 else (16 - len(services))
        
        # fill the sequence with active and rest steps first
        rests = []
        for i in range(random_qty):
            rand_rest = random.randint(0, new_seq.length - 1)
            while rand_rest in rests:
                rand_rest = random.randint(0, new_seq.length - 1)
            rests.append(rand_rest)
        for rest_index in rests:
            new_seq.mod_step(index=rest_index, note=0, octave_mod=0, type='rest', accent=False)
        
        # now we specify the notes themselves

        config = configparser.ConfigParser()
        config.read('./keywords.conf')
        accent_keywords = config['wordlists']['accents'].split(',')
        scale = self.choose_scale()
        notes = []
        accents = []
        ties = []
        sources = []
        scale_notes = scale["notes"].split(",")

        for service in services:
            # specify notes
            degree = service.port % len(scale_notes)
            note = (int(scale_notes[degree])) + OCT_SHIFT # shift to a more reasonable octave
            notes.append(note)
            # specify accents
            accents.append(self.is_accent(accent_keywords, service))
            ties.append(self.is_tie(service))
            sources.append(f"{service.port}:{service.service_name}")
        
        print(f"Notes: {notes}")
        print(f"Accents: {accents}")
        print(f"Ties: {ties}")
        

        for step in new_seq.sequence:
            if step.type == 'active':
                step.note = notes.pop(0)
                step.accent = accents.pop(0)
                step.octave_mod = 0 if random.randint(0,1) == 1 else (1 if random.randint(0,1) == 1 else -1)
                step.type = 'tie' if ties.pop(0) else 'active'
                step.source = sources.pop(0)

        self.sequences.append(new_seq)
        # new_seq.play(midi_interface="Onyx Producer 2-2:Onyx Producer 2-2 MIDI 1 28:0", bpm=133, repetitions=2, send_clock=False, channel=1) # uncomment this line to auto-play the imported sequence - make sure to change the MIDI interface to your own! use s2a> list midi to see available interfaces
        print(new_seq)

    def prompt(self):

        print("scan2acid 0.1 - a 303-style sequence manipulating tool.")
        print("   made with <3 by Hack the Music | @hackingmusic")
        while True:
            cmd = input("s2a> ").strip().lower()
            if cmd in {'exit', 'quit', 'q'}:
                print("Exiting scan2acid.")
                break

            elif cmd == 'help':
                self.print_help()
                
            elif cmd == 'demo':
                self.play_demo_sequence()
            
            elif cmd == 'list midi':
                print("Available MIDI output interfaces:")
                for name in mido.get_output_names():
                    print(f"  {name}")
            
            elif cmd == 'list sequences':
                if not self.sequences:
                    print("No sequences available.")
                else:
                    print("Available sequences:")
                    for idx, seq in enumerate(self.sequences):
                        print(f"  [{idx}] {seq.name} - {seq.length} steps")
            
            elif cmd == 'scan':
                target = input("Enter target IP or hostname to scan: ").strip()
                scanner = Scanner(target=target)
                print(f"Scanning {target}...")
                results = scanner.scan()
                if results:
                    print(f"Found {len(results)} open ports/services:")
                    for service in results:
                        print(f"  {service}")
                else:
                    print("No open ports found.")

            elif cmd == 'parse':
                xml_path = input("Enter path to Nmap XML file: ").strip()
                parser = Parser(xml_path=xml_path)
                try:
                    services = parser.parse()
                    if services:
                        print(f"Parsed {len(services)} services from {xml_path}:")
                        for service in services:
                            print(f"  {service}")
                        to_303_choice = input("Import as 303 sequence? (y/n): ").strip().lower()
                        
                        if to_303_choice == 'y':
                            self.to_303(services)
                        
                    else:
                        print("No services found in the XML file.")
                    
                except (FileNotFoundError, ValueError) as exc:
                    print(f"Error: {exc}")
            
            elif cmd == 'play':
                if not self.sequences:
                    print("No sequences available to play.")
                    continue
                
                options = [seq.name for seq in self.sequences]
                menu = TerminalMenu(options, title="Select a sequence to play")
                menu_entry_index = menu.show()
                selected_seq = self.sequences[menu_entry_index]

                midi_options = mido.get_output_names()
                midi_menu = TerminalMenu(midi_options, title="Select a MIDI output interface for playback")
                midi_entry_index = midi_menu.show()
                midi_interface = midi_options[midi_entry_index]

                bpm_input = input("Enter BPM (default 120): ").strip()
                try:
                    bpm = int(bpm_input) if bpm_input else 120
                except ValueError:
                    bpm = 120

                channel_input = input("Enter MIDI channel (1-16, default 1): ").strip()
                try:
                    channel = int(channel_input) if channel_input else 1
                    if not (1 <= channel <= 16):
                        raise ValueError
                except ValueError:
                    channel = 1

                repetitions_input = input("Enter number of repetitions (default 4; 0 = infinite): ").strip()
                try:
                    repetitions = int(repetitions_input) if repetitions_input else 4
                    if repetitions < 0:
                        raise ValueError
                except ValueError:
                    repetitions = 4

                clock_input = input("Send MIDI clock? (y/n, default n): ").strip().lower()
                send_clock = clock_input == 'y'

                selected_seq.play(bpm=bpm, repetitions=repetitions, midi_interface=midi_interface, channel=channel, send_clock=send_clock)
            
            elif cmd == 'export':
                if not self.sequences:
                    print("No sequences available to export.")
                    continue
                
                options = [seq.name for seq in self.sequences]
                menu = TerminalMenu(options, title="Select a sequence to export")
                menu_entry_index = menu.show()
                selected_seq = self.sequences[menu_entry_index]

                name_input = input(f"Enter filename to export (without extension) for '{selected_seq.name}': ").strip()
                selected_seq.to_html(f"{name_input}.html", title=selected_seq.name)
                print(f"Exported sequence to {name_input}.html")
            
            else:
                print(f"Unknown command: {cmd}. Type 'help' for a list of commands.")

if __name__ == "__main__":
    cli = Manager()
    cli.prompt()
