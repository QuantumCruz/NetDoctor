
"""Read-only Wi-Fi association information from the Windows Native Wifi API.

No SSID scans, saved Wi-Fi profiles, credentials, or location requests.
If Windows restricts access to the current connection, return no association.
"""

import ctypes
import platform
from dataclasses import dataclass


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8),
    ]


# Windows WCHAR is exactly 16 bits (unlike wchar_t on some other systems).
_Wchars = ctypes.c_uint16 * 256


class _InterfaceInfo(ctypes.Structure):
    _fields_ = [
        ("guid", _Guid), ("description", _Wchars),
        ("state", ctypes.c_uint32),
    ]


class _Ssid(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint32),
        ("bytes", ctypes.c_ubyte * 32),
    ]


class _Association(ctypes.Structure):
    _fields_ = [
        ("ssid", _Ssid), ("bss_type", ctypes.c_uint32),
        ("bssid", ctypes.c_ubyte * 6),
        ("phy_type", ctypes.c_uint32),
        ("phy_index", ctypes.c_uint32),
        ("signal_quality", ctypes.c_uint32),
        ("rx_kbps", ctypes.c_uint32),
        ("tx_kbps", ctypes.c_uint32),
    ]


class _Security(ctypes.Structure):
    _fields_ = [
        ("enabled", ctypes.c_uint32),
        ("one_x", ctypes.c_uint32),
        ("auth", ctypes.c_uint32),
        ("cipher", ctypes.c_uint32),
    ]


class _Connection(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_uint32),
        ("mode", ctypes.c_uint32),
        ("profile", _Wchars),
        ("association", _Association),
        ("security", _Security),
    ]


@dataclass(frozen=True)
class WifiLink:
    description: str
    ssid: str | None
    signal_percent: int
    receive_link_mbps: float | None
    transmit_link_mbps: float | None


def _utf16(values) -> str:
    raw = bytes(
        ctypes.string_at(
            ctypes.addressof(values),
            ctypes.sizeof(values),
        )
    )
    return raw.decode(
        "utf-16-le", errors="replace"
    ).split("\x00", 1)[0]


def _decode_link(
    info: _InterfaceInfo,
    connection: _Connection,
) -> WifiLink | None:
    if (
        connection.state != 1
        or connection.association.signal_quality > 100
    ):
        return None

    ssid = connection.association.ssid
    if ssid.length > 32:
        return None

    label = bytes(
        ssid.bytes[:ssid.length]
    ).decode("utf-8", errors="replace") or None

    assoc = connection.association

    return WifiLink(
        description=_utf16(info.description),
        ssid=label,
        signal_percent=int(assoc.signal_quality),
        receive_link_mbps=(
            round(assoc.rx_kbps / 1000, 1)
            if assoc.rx_kbps else None
        ),
        transmit_link_mbps=(
            round(assoc.tx_kbps / 1000, 1)
            if assoc.tx_kbps else None
        ),
    )


def _read_native() -> tuple[WifiLink, ...]:
    dll = ctypes.WinDLL("wlanapi.dll")

    open_handle = dll.WlanOpenHandle
    open_handle.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    open_handle.restype = ctypes.c_uint32

    enum = dll.WlanEnumInterfaces
    enum.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    enum.restype = ctypes.c_uint32

    query = dll.WlanQueryInterface
    query.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_Guid),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    query.restype = ctypes.c_uint32

    free = dll.WlanFreeMemory
    free.argtypes = [ctypes.c_void_p]
    free.restype = None

    close = dll.WlanCloseHandle
    close.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    close.restype = ctypes.c_uint32

    handle = ctypes.c_void_p()
    negotiated = ctypes.c_uint32()

    if open_handle(
        2, None,
        ctypes.byref(negotiated),
        ctypes.byref(handle),
    ) != 0:
        return ()

    listing = ctypes.c_void_p()
    links: list[WifiLink] = []

    try:
        if (
            enum(handle, None, ctypes.byref(listing)) != 0
            or not listing.value
        ):
            return ()

        count = ctypes.c_uint32.from_address(
            listing.value
        ).value

        if count > 32:
            return ()

        rows = ctypes.cast(
            listing.value + 8,
            ctypes.POINTER(_InterfaceInfo * count),
        ).contents

        for row in rows:
            if row.state != 1:
                # wlan_interface_state_connected
                continue

            result = ctypes.c_void_p()
            size = ctypes.c_uint32()
            kind = ctypes.c_uint32()

            try:
                code = query(
                    handle,
                    ctypes.byref(row.guid),
                    7,  # wlan_intf_opcode_current_connection
                    None,
                    ctypes.byref(size),
                    ctypes.byref(result),
                    ctypes.byref(kind),
                )

                if (
                    code
                    or not result.value
                    or size.value < ctypes.sizeof(_Connection)
                ):
                    continue

                connection = ctypes.cast(
                    result,
                    ctypes.POINTER(_Connection),
                ).contents

                link = _decode_link(row, connection)
                if link:
                    links.append(link)

            finally:
                if result.value:
                    free(result)

    finally:
        if listing.value:
            free(listing)
        close(handle, None)

    return tuple(links)


def read_wifi_links() -> tuple[WifiLink, ...]:
    """Return connected wireless associations; absence is not a fault."""
    if platform.system() != "Windows":
        return ()

    try:
        return _read_native()
    except (OSError, ValueError, AttributeError):
        return ()
