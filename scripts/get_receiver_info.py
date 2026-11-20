from pathlib import Path
import serial


PORT = "COM3"
BAUDRATE = 9600

POLL_UNIQID = bytes.fromhex(
    "b562270300002aa5"
)

POLL_MONVER = bytes.fromhex(
    "b5620a0400000e34"
)


def read_ubx_message(
    ser: serial.Serial,
) -> bytes:
    """
    Read a complete UBX message.
    """

    header = ser.read(6)

    if len(header) != 6:
        raise RuntimeError(
            "Failed to read UBX header."
        )

    if header[:2] != b"\xB5\x62":
        raise RuntimeError(
            f"Invalid UBX header: {header.hex()}"
        )

    payload_len = int.from_bytes(
        header[4:6],
        "little",
    )

    payload_and_crc = ser.read(
        payload_len + 2,
    )

    if len(payload_and_crc) != payload_len + 2:
        raise RuntimeError(
            "Incomplete UBX payload."
        )

    return header + payload_and_crc


def update_env(
    key: str,
    value: str,
    env_path: Path,
):
    lines = []

    if env_path.exists():
        lines = env_path.read_text(
            encoding="utf-8",
        ).splitlines()

    updated = False

    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break

    if not updated:
        lines.append(
            f"{key}={value}"
        )

    env_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main():

    env_path = Path(".env")

    with serial.Serial(
        PORT,
        BAUDRATE,
        timeout=5,
    ) as ser:

        ser.reset_input_buffer()

        print(
            "Requesting UBX-SEC-UNIQID..."
        )

        ser.write(
            POLL_UNIQID,
        )

        uniqid_msg = read_ubx_message(
            ser,
        )

        print(
            "Requesting UBX-MON-VER..."
        )

        ser.write(
            POLL_MONVER,
        )

        monver_msg = read_ubx_message(
            ser,
        )

    update_env(
        "UBX_SEC_UNIQID_HEX",
        uniqid_msg.hex(),
        env_path,
    )

    update_env(
        "UBX_MON_VER_HEX",
        monver_msg.hex(),
        env_path,
    )

    print(
        "Saved to .env:"
    )

    print(
        f"UBX_SEC_UNIQID_HEX={uniqid_msg.hex()}"
    )

    print(
        f"UBX_MON_VER_HEX={monver_msg.hex()}"
    )


if __name__ == "__main__":
    main()