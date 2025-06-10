import serial


class McPacket:
    def __init__(self, packet_type: int, data: int, crc: int):
        self.packet_type = packet_type
        self.data = data
        self.crc = crc

    @staticmethod
    def calculate_crc(data: bytes) -> int:
        crc = 0
        for inbyte in data:
            for _ in range(8):
                mix = (crc ^ inbyte) & 0x80
                crc = (crc << 1) & 0xFF  # Ensure it stays within 8 bits
                if mix:
                    crc ^= 0x07
                inbyte = (inbyte << 1) & 0xFF  # Also ensure inbyte stays within 8 bits
        return crc

    @classmethod
    def telemetry_request(cls):
        packet_type = 2
        data = 0
        raw_packet = bytes([packet_type, data, data])
        crc = cls.calculate_crc(raw_packet)
        return cls(packet_type, data, crc)

    @classmethod
    def set_speed_rpm(cls, speed_rpm: int):
        packet_type = 1
        data = speed_rpm
        raw_packet = bytes([packet_type, data & 0xFF, data >> 8])
        crc = cls.calculate_crc(raw_packet)
        return cls(packet_type, data, crc)

    def serialize(self):
        return bytes([self.packet_type, self.data & 0xFF, self.data >> 8, self.crc])


class McTelemetryPacket:
    def __init__(self, duty_cycle: int, reference_speed: int, average_speed: int, motor_state: int, crc: int):
        self.duty_cycle = duty_cycle
        self.reference_speed = reference_speed
        self.average_speed = average_speed
        self.motor_state = motor_state
        self.crc = crc

    @staticmethod
    def calculate_crc(data: bytes) -> int:
        crc = 0
        for inbyte in data:
            for _ in range(8):
                mix = (crc ^ inbyte) & 0x80
                crc = (crc << 1) & 0xFF  # Ensure it stays within 8 bits
                if mix:
                    crc ^= 0x07
                inbyte = (inbyte << 1) & 0xFF  # Also ensure inbyte stays within 8 bits
        return crc

    def serialize(self):
        return bytes([self.duty_cycle & 0xFF, self.duty_cycle >> 8, self.reference_speed & 0xFF, self.reference_speed >> 8, self.average_speed & 0xFF, self.average_speed >> 8, self.motor_state, self.crc])

    def validate(self):
        raw_packet = bytes([self.duty_cycle & 0xFF, self.duty_cycle >> 8, self.reference_speed & 0xFF, self.reference_speed >> 8, self.average_speed & 0xFF, self.average_speed >> 8, self.motor_state])
        return self.crc == self.calculate_crc(raw_packet)

    @classmethod
    def deserialize(cls, data: bytes):
        if len(data) != 8:
            return None
            # raise ValueError("Data must be exactly 8 bytes long.")

        duty_cycle = int.from_bytes(data[0:2], byteorder='little')
        reference_speed = int.from_bytes(data[2:4], byteorder='little')
        average_speed = int.from_bytes(data[4:6], byteorder='little')
        motor_state = data[6]
        received_crc = data[7]

        computed_crc = cls.calculate_crc(data[:7])
        if computed_crc != received_crc:
            raise ValueError(f"CRC mismatch: expected {computed_crc}, got {received_crc}")

        return cls(duty_cycle, reference_speed, average_speed, motor_state, received_crc)

    def __str__(self):
        return (
            f"McTelemetryPacket(\n"
            f"  DutyCycle      : {self.duty_cycle},\n"
            f"  ReferenceSpeed : {self.reference_speed},\n"
            f"  AverageSpeed   : {self.average_speed},\n"
            f"  MotorState     : {self.motor_state},\n"
            f"  CRC            : {self.crc:02X}\n"
            f")"
        )


class UART:
    def __init__(self):
        self.serial = serial.Serial('COM10', 230400, timeout=1)

    def send_mc_packet(self, packet: McPacket):
        self.serial.write(packet.serialize())
        self.serial.flush()

        # read 8 bytes
        if packet.packet_type == 2:
            response = self.serial.read(8)
            return McTelemetryPacket.deserialize(response)
