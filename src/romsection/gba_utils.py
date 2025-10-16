import typing


GBA_HEADER_SIZE = 192

EXTANDED_GBA_HEADER_SIZE = 228


def _as_struct(data: bytes, description: list[tuple[int, str]]) -> list[tuple[int, bytes, str]]:
    pos = 0
    result: list[tuple[int, bytes, str]] = []
    for desc in description:
        d = data[pos:pos + desc[0]]
        result.append((pos, d, desc[1]))
        pos += desc[0]
    return result


def format_32bit_opcode(memory: bytes, baseAddress: int) -> str:
    """
    Display the opcode as readable assembler.

    Here we assume it's a jump.
    """
    opcode = memory[3]
    if opcode == 0xEA:
        address = int.from_bytes(memory[0:3], byteorder='little', signed=False)
        return f"b #0x{address * 4 + baseAddress + 8:06X}"
    return "?"


class GbaHeader(typing.NamedTuple):
    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        gameTitle = data[0xA0:0xAC].rstrip(b"\x00").decode()
        gameCode = data[0xAC:0xB0].rstrip(b"\x00").decode()
        makerCode = data[0xB0:0xB2].rstrip(b"\x00").decode()
        description = [
            # Address 00h
            (4, f"ROM entry point: {format_32bit_opcode(data[0x00:0x04], 0x00)}"),
            # 156 bytes...
            (12, f"Nintendo logo"),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, ""),
            (12, f"Game title: {gameTitle}"),
            (4, f"Game code: {gameCode}"),
            (2, f"Maker code: {makerCode}"),
            (1, f"Fixed value: must be 0x96"),
            (1, f"Main unit code"),
            (1, f"Device type"),
            (7, f"Reserved area"),
            (1, f"Software version"),
            (1, f"Complement check: header checksum"),
            # Address BEh
            (2, f"Reserved area"),
        ]

        if len(data) == 0xC0:
            return _as_struct(data, description)

        description += [
            # Address C0h
            (4, f"RAM entry point: {format_32bit_opcode(data[0xC0:0xC4], 0xC0)}"),
            (1, "Boot mode"),
            (1, "Slave ID number"),
            # 26 bytes
            (9, "Not used"),
            (9, ""),
            (8, ""),
            # Address E0h
            (4, f"JOYBUS entry point: {format_32bit_opcode(data[0xE0:0xE4], 0xE0)}"),
        ]

        return _as_struct(data, description)
