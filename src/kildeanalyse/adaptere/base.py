"""Felles adapterkontrakt.

En adapter oversetter en Inputpakke til leverandørens format og returnerer et Motorsvar.
Den skal aldri lese andre dokumenter enn pakken, og skal bevare råsvaret også ved feil.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from ..modell import Inputpakke, Motorsvar, Stotte


class AdapterFeil(Exception):
    pass


class Adapter(ABC):
    navn: str = "abstrakt"
    simulert: bool = True
    beskrivelse: str = ""

    def __init__(self, innstillinger: dict[str, Any] | None = None):
        self.innstillinger = dict(innstillinger or {})

    @abstractmethod
    def sjekk_stotte(self) -> Stotte:
        """Kan denne adapteren brukes nå? Returnerer ok, meldinger og observerte egenskaper."""

    @abstractmethod
    def kjor(self, pakke: Inputpakke, modell: str, stopp: Callable[[], bool], arbeidsmappe: str) -> Motorsvar:
        """Kjører ett forsøk. `stopp()` returnerer True når brukeren har bedt om stopp."""

    @abstractmethod
    def avbryt(self) -> None:
        """Forsøker å avbryte et pågående kall. Lover ikke at leverandørens behandling stopper."""
