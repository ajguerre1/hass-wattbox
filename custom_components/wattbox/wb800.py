"""Driver shim making the WattBox 800 series work with pywattbox 0.9.0.

TEMPORARY. This module duplicates a fix submitted upstream as a pull request
against eseglem/pywattbox. Once that lands and a release is cut, delete this
file, bump the ``pywattbox`` pin in ``manifest.json``, and drop the
``create_ip_wattbox`` indirection in ``__init__.py``.

It is carried here rather than pulled from a patched wheel because Home
Assistant's ``is_installed()`` returns False for any URL requirement, so a
direct-URL wheel is re-fetched on *every* restart. On a system where the
WattBox itself powers the network equipment, that is a circular dependency:
a restart while the modem is down would leave the integration unable to load.

What pywattbox 0.9.0 gets wrong on the 800 series, in the order it bites
------------------------------------------------------------------------
1. **Login never completes.** scrapli's in-channel telnet auth does not
   satisfy these units, which fail it as "Invalid Login"; setup dies with
   ``ScrapliTimeout: timed out during in channel telnet authentication``.
   Nothing below is reachable until this is fixed.
2. ``_send_command`` guards the telnet path with
   ``self.transport not in ("telnet", "asynctelnet")``. ``self.transport`` is a
   transport *object*, so that is always true; every command takes the "read
   more" branch and blocks on a second ``_read_until_prompt()`` until
   ``timeout_ops``. ``split_response[1]`` is never reached, so the echo
   assumption is not what fails first.
3. ``PROMPTS`` leaves its alternatives ungrouped, so ``^`` binds only to the
   first branch and ``\\n$`` only to the last. ``#Error`` can never match at
   all, because scrapli strips the trailing newline before searching.
4. ``\\S+`` cannot match values containing spaces, and outlet names are user
   supplied (``?OutletName={Media Bridge 1 to 3},...``).

Verified against a WB-800-IPVM-6 on firmware 2.10.0.0.
"""

from __future__ import annotations

import logging
import re
from re import Pattern
from typing import Any, Final

from pywattbox.driver.async_driver import WattBoxAsyncDriver
from pywattbox.ip_wattbox import IpWattBox
from scrapli.exceptions import ScrapliTimeout
from scrapli.response import Response

_LOGGER = logging.getLogger(__name__)

#: Fixed channel prompt pattern. Every alternative is wrapped in a
#: non-capturing group so ``^``/``$`` anchor all of them, and values may
#: contain anything but a line break.
PROMPTS: Final[str] = (
    r"^(?:"
    r"(?:.*Successfully Logged In!)"
    r"|(?:\?\w+(?:=[^\r\n]*)?)"
    r"|(?:OK)"
    r"|(?:#Error)"
    r")[ \t]*\r?$"
)

TELNET_TRANSPORTS: Final[tuple[str, ...]] = ("telnet", "asynctelnet")

# Login prompts, captured verbatim. LF framed -- there is no CR, and no telnet
# IAC option negotiation takes place at all.
USERNAME_PROMPT: Final[bytes] = b"Username:"
PASSWORD_PROMPT: Final[bytes] = b"Password:"
LOGIN_SUCCESS: Final[bytes] = b"Successfully Logged In"


def _reply_body(command: str) -> bytes:
    if command.startswith("?"):
        key = re.escape(command.split("=", 1)[0].encode())
        return rb"(?:" + key + rb"=(?P<value>[^\r\n]*)|(?P<error>#Error))"
    return rb"(?:(?P<value>OK)|(?P<error>#Error))"


def reply_patterns(command: str) -> tuple[Pattern[bytes], Pattern[bytes]]:
    """Return (strict, lenient) patterns matching a reply to *command*.

    The strict pattern requires the terminating newline, which is what makes
    incremental reads safe: without it a reply still in flight --
    ``?OutletName={Media Brid`` -- looks like a finished line and is accepted
    truncated.
    """
    body = _reply_body(command)
    return (
        re.compile(rb"(?m)^" + body + rb"[ \t]*\r?\n"),
        re.compile(rb"(?m)^" + body + rb"[ \t]*\r?$"),
    )


def find_reply(buffer: bytes, command: str, *, strict: bool = True) -> bytes | None:
    """Extract the reply value for *command*, skipping an echoed command.

    Skipping the echo matters for requests carrying an argument: the echo of
    ``?OutletPowerStatus=1`` is itself a valid ``key=value`` line, so taking
    the first match would return the echo instead of the reading.
    """
    pattern = reply_patterns(command)[0 if strict else 1]
    encoded = command.encode()
    for match in pattern.finditer(buffer):
        if match.group(0).strip() == encoded:
            continue
        if match.group("error") is not None:
            return b"#Error"
        return match.group("value")
    return None


async def _read_until_token(driver: WattBox800AsyncDriver, token: bytes) -> bytes:
    buf = b""
    while token not in buf:
        chunk = await driver.channel.read()
        if not chunk:
            raise ScrapliTimeout(
                f"connection closed while waiting for {token!r}, got {buf!r}"
            )
        buf += chunk
    return buf


async def on_open(driver: WattBox800AsyncDriver) -> None:
    """Complete the login handshake.

    Over SSH the transport authenticates and only the banner needs consuming.
    Over telnet the device presents its own prompts, which scrapli's telnet
    auth does not satisfy, so auth is bypassed and performed here.
    """
    if driver.transport_name not in TELNET_TRANSPORTS:
        await driver.channel._read_until_prompt()
        return

    await _read_until_token(driver, USERNAME_PROMPT)
    driver.channel.write(driver.auth_username)
    driver.channel.send_return()

    await _read_until_token(driver, PASSWORD_PROMPT)
    driver.channel.write(driver.auth_password)
    driver.channel.send_return()

    await _read_until_token(driver, LOGIN_SUCCESS)
    _LOGGER.debug("WattBox telnet login complete")


async def on_close(driver: WattBox800AsyncDriver) -> None:
    try:
        driver.channel.write("!Exit")
        driver.channel.send_return()
    except Exception:  # noqa: BLE001 - the socket may already be gone
        _LOGGER.debug("Could not send !Exit while closing", exc_info=True)


class WattBox800AsyncDriver(WattBoxAsyncDriver):
    """WattBoxAsyncDriver with 800-series command handling."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("comms_prompt_pattern", PROMPTS)
        kwargs.setdefault("on_open", on_open)
        kwargs.setdefault("on_close", on_close)
        if kwargs.get("transport") in TELNET_TRANSPORTS:
            kwargs["auth_bypass"] = True
        super().__init__(**kwargs)

    async def _send_command(self, command: str) -> Response:
        """Send one request and return its single-line reply.

        Reads until a *complete* reply line for this command arrives instead
        of relying on scrapli's prompt matching: replies carry no trailing
        prompt, values contain spaces and commas, and the command is not
        echoed over telnet, so its position in the buffer is transport
        dependent.
        """
        await self._open()

        response = Response(
            host=self._base_transport_args.host,
            channel_input=command,
            failed_when_contains="#Error",
        )

        raw_response = b""
        async with self.channel._channel_lock():
            self.channel.write(command)
            self.channel.send_return()
            while True:
                try:
                    chunk = await self.channel.read()
                except ScrapliTimeout:
                    break
                if not chunk:
                    break
                raw_response += chunk
                if find_reply(raw_response, command) is not None:
                    break

        processed = find_reply(raw_response, command)
        if processed is None:
            processed = find_reply(raw_response, command, strict=False)
        if processed is None:
            raise ScrapliTimeout(
                f"no reply to {command!r} from {self._base_transport_args.host}; "
                f"read {raw_response!r}"
            )

        response.record_response(processed)
        response.raw_result = raw_response
        return response


class WattBox800(IpWattBox):
    """IpWattBox that talks through the patched driver."""

    @property
    def async_driver(self) -> WattBox800AsyncDriver:
        # `IpWattBox._async_driver` is typed as the base driver, so narrow on
        # the subclass rather than merely on None -- that also rebuilds it if a
        # base-class driver was somehow assigned.
        driver = self._async_driver
        if not isinstance(driver, WattBox800AsyncDriver):
            driver = WattBox800AsyncDriver(
                **self._conninfo,
                transport="asyncssh" if self._transport == "ssh" else "asynctelnet",
            )
            self._async_driver = driver
        return driver

    async def async_close(self) -> None:
        """Close the channel so the session is released on the device.

        The 800s cap concurrent sessions, so a reload that leaves the old
        connection open eventually locks the integration out.
        """
        if self._async_driver is not None and self._async_driver.transport.isalive():
            await self._async_driver.close()


async def async_create_wb800(
    host: str, user: str, password: str, port: int
) -> WattBox800:
    """Build a WattBox800 and perform initial discovery."""
    wattbox = WattBox800(host=host, user=user, password=password, port=port)
    await wattbox.async_get_initial()
    return wattbox
