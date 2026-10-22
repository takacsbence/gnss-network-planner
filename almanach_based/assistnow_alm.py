#!/usr/bin/env python3
"""
AssistNow almanac letölto ZTP-vel (pl. ZED-F9P-hez).

Elso futás (vevo csatlakoztatva):
    python assistnow_alm.py -z ZTP-TOKEN -P /dev/ttyACM0
Késobbi futások (vevo nélkül, a mentett adatokból):
    python assistnow_alm.py -z ZTP-TOKEN

Opciók:
    -d  adattípusok (alapért.: ualm), pl. "ualm,ulorb_l1,ukion"
    -g  rendszerek (alapért.: gps,gal,glo,bds,qzss)
    -o  kimeneti fájl (alapért.: alm.ubx)

pip install pyserial requests
"""
import argparse, json, os, sys, time
import requests

ZTP_ENDPOINT = "https://api.thingstream.io/ztp/assistnow/credentials"
CACHE = "assistnow_device.json"
POLL_UNIQID = bytes.fromhex("b562270300002aa5")
POLL_MONVER = bytes.fromhex("b5620a0400000e34")


def checksum_ok(msg):
    a = b = 0
    for x in msg[2:-2]:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return bytes([a, b]) == msg[-2:]


def poll(ser, cmd, timeout=5.0):
    """Elküldi a poll parancsot, és visszaadja az elso egyezo, érvényes UBX választ."""
    prefix = cmd[:4]
    ser.reset_input_buffer()
    ser.write(cmd)
    buf, t0 = b"", time.time()
    while time.time() - t0 < timeout:
        buf += ser.read(1024)
        while True:
            i = buf.find(b"\xb5\x62")
            if i < 0 or len(buf) - i < 8:
                break
            buf = buf[i:]
            n = int.from_bytes(buf[4:6], "little") + 8
            if len(buf) < n:
                break
            msg, buf = buf[:n], buf[n:]
            if msg.startswith(prefix) and checksum_ok(msg):
                return msg
    raise RuntimeError(f"Nincs válasz a {cmd[2:4].hex()} pollra")


def read_device(port, baud):
    import serial
    with serial.serial_for_url(port, baudrate=baud, timeout=0.1) as ser:
        uniqid = poll(ser, POLL_UNIQID)
        monver = poll(ser, POLL_MONVER)
    return uniqid.hex(), monver.hex()


def ztp(token, uniqid_hex, monver_hex):
    body = {"token": token,
            "messages": {"UBX-SEC-UNIQID": uniqid_hex, "UBX-MON-VER": monver_hex}}
    r = requests.post(ZTP_ENDPOINT, json=body, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"ZTP hiba ({r.status_code}): {r.text}")
    return r.json()


def download(service_url, chipcode, data, gnss):
    r = requests.get(service_url, params={"chipcode": chipcode, "data": data, "gnss": gnss},
                     timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"AssistNow hiba ({r.status_code}): {r.text}")
    return r.content


def summarize(blob):
    """Kilistázza az üzenettípusokat, hogy látszódjon, jött-e dokumentált ALM."""
    names = {(0x13, 0x00): "MGA-GPS", (0x13, 0x02): "MGA-GAL", (0x13, 0x03): "MGA-BDS",
             (0x13, 0x05): "MGA-QZSS", (0x13, 0x06): "MGA-GLO", (0x13, 0x20): "MGA-ANO",
             (0x13, 0x40): "MGA-INI"}
    counts, i = {}, 0
    while i + 8 <= len(blob) and blob[i:i + 2] == b"\xb5\x62":
        n = int.from_bytes(blob[i + 4:i + 6], "little") + 8
        msg = blob[i:i + n]
        key = names.get((msg[2], msg[3]), f"{msg[2]:02x}-{msg[3]:02x}")
        if msg[2] == 0x13 and msg[3] in (0x00, 0x02, 0x03, 0x05, 0x06):
            key += f" type=0x{msg[6]:02x}"   # 0x02 = ALM GPS-nél, GAL/BDS/GLO/QZSS-nél is ALM típus
        if not checksum_ok(msg):
            key += " (HIBÁS CHECKSUM)"
        counts[key] = counts.get(key, 0) + 1
        i += n
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v} db")
    if i != len(blob):
        print(f"  Figyelem: {len(blob) - i} bájt nem UBX (lehet szöveges hibaüzenet)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-z", "--ztp_token", required=True)
    ap.add_argument("-P", "--port", help="Soros port; csak az elso futáshoz kell")
    ap.add_argument("-B", "--baudrate", type=int, default=38400)
    ap.add_argument("-d", "--data", default="ualm")
    ap.add_argument("-g", "--gnss", default="gps,gal,glo,bds,qzss")
    ap.add_argument("-o", "--out", default="alm.ubx")
    a = ap.parse_args()

    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            cache = json.load(f)

    if a.port:
        print("Vevo kiolvasása (SEC-UNIQID, MON-VER)...")
        cache["uniqid"], cache["monver"] = read_device(a.port, a.baudrate)
        cache.pop("chipcode", None)
    if "uniqid" not in cache:
        sys.exit("Nincs mentett eszközadat: elso futáskor add meg a -P portot.")

    def get_creds():
        z = ztp(a.ztp_token, cache["uniqid"], cache["monver"])
        cache.update(chipcode=z["chipcode"], serviceUrl=z["serviceUrl"],
                     allowedData=z.get("allowedData"))
        with open(CACHE, "w") as f:
            json.dump(cache, f, indent=2)
        print(f"ZTP OK, engedélyezett adattípusok: {cache['allowedData']}")

    if "chipcode" not in cache:
        get_creds()
    try:
        blob = download(cache["serviceUrl"], cache["chipcode"], a.data, a.gnss)
    except RuntimeError as e:
        print(f"{e}\nÚj chipcode kérése és újrapróbálás...")
        get_creds()
        blob = download(cache["serviceUrl"], cache["chipcode"], a.data, a.gnss)

    with open(a.out, "wb") as f:
        f.write(blob)
    print(f"Mentve: {a.out} ({len(blob)} bájt). Tartalom:")
    summarize(blob)


if __name__ == "__main__":
    main()
