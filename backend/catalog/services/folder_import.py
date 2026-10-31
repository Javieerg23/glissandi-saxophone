"""Importación de una carpeta de música ya descargada.

Import of a folder of already downloaded music.

Each audio file is matched to a Deezer track through its tags (ISRC first, then
artist and title), whatever is missing from the catalogue is imported with
:class:`~catalog.services.importing.Importer`, and the file is recorded as a
``Download``. Files are never moved, renamed or retagged. A file already
recorded under the same path is skipped, so running the import twice changes
nothing.
"""

from pathlib import Path
from typing import Any

import mutagen
import requests
from django.db.models import Q

from catalog.models import Download, Track
from catalog.services.importing import Importer
from integrations import deezer as dz
from integrations.audio import Tags
from integrations.deezer import DeezerClient, DeezerError
from integrations.deezer.names import split_featured
from jobs import runner
from jobs.models import JobRun, JobRunLine

#: Extensiones que se leen; el resto (portadas, listas…) se ignora.
#: Extensions that are read; anything else (covers, playlists…) is ignored.
AUDIO_SUFFIXES = frozenset({".mp3", ".flac", ".opus", ".ogg", ".m4a"})

# Motivos por los que un fichero no se enlaza; la web los traduce.
# Reasons a file is not linked; the web translates them.
OUTSIDE = "outside"
UNREADABLE = "unreadable"
NO_TAGS = "no_tags"
NOT_FOUND = "not_found"
NOT_IN_CATALOG = "not_in_catalog"
LOOKUP_ERROR = "error"


def resolve_folder(root: Path, folder: str) -> Path:
    """Ruta real de ``folder`` dentro de ``root``.

    Real path of ``folder`` inside ``root``. Resolving first means ``..`` and
    symbolic links are judged by where they really lead, not by how they read.

    Args:
        root: Carpeta de descargas. / Downloads folder.
        folder: Subcarpeta relativa a ``root``. / Subfolder relative to ``root``.

    Returns:
        La ruta absoluta y resuelta. / The absolute, resolved path.

    Raises:
        ValueError: Si sale de ``root`` o no es una carpeta.
            If it leaves ``root`` or is not a folder.
    """
    base = root.resolve()
    target = (base / folder).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"La carpeta «{folder}» está fuera de la carpeta de descargas.")
    if not target.is_dir():
        raise ValueError(f"La carpeta «{folder}» no existe.")
    return target


def read_tags(path: Path) -> Tags | None:
    """Etiquetas del fichero; ``None`` si no tiene título.

    The file's tags; ``None`` without a title, as nothing can be matched then.

    Raises:
        mutagen.MutagenError: Si el fichero está dañado. / If the file is damaged.
    """
    audio = mutagen.File(path, easy=True)
    if audio is None or not audio.tags:
        return None

    def first(key: str) -> str:
        values = audio.tags.get(key) or [""]
        return str(values[0]).strip()

    title = first("title")
    if not title:
        return None
    number = first("tracknumber").partition("/")[0]
    return Tags(
        title=title,
        artists=tuple(str(a).strip() for a in audio.tags.get("artist") or () if str(a).strip()),
        album=first("album") or None,
        track_number=int(number) if number.isdigit() else None,
        isrc=first("isrc").upper() or None,
    )


def find_remote(client: DeezerClient, tags: Tags) -> dz.Track | None:
    """Canción de Deezer que corresponde a las etiquetas.

    Deezer track matching the tags. The ISRC is exact; the name search only
    accepts a hit whose title is the same, ignoring case and "feat." guests, so a
    loose match never links the wrong song.

    Raises:
        DeezerError: Si Deezer falla en la búsqueda. / If Deezer fails the search.
    """
    if tags.isrc:
        try:
            return client.get_track_by_isrc(tags.isrc)
        except DeezerError:
            pass  # ISRC desconocido: se prueba por nombre / unknown ISRC: try by name
    title = split_featured(tags.title)[0].casefold()
    # Las comillas cerrarían el campo de la búsqueda avanzada. / Quotes would end the field.
    query = f'track:"{tags.title.replace('"', "")}"'
    if tags.artists:
        query = f'artist:"{tags.artists[0].replace('"', "")}" {query}'
    for hit in client.search_tracks(query, limit=10).items:
        if hit.title.casefold() == title:
            return client.get_track(hit.id)
    return None


def _catalog_track(remote: dz.Track) -> Track | None:
    """Canción del catálogo con ese id de Deezer o ese ISRC.

    Catalogue track with that Deezer id or ISRC; the ISRC catches the same song
    imported from another edition.
    """
    match = Q(deezer_id=remote.id)
    if remote.isrc:
        match |= Q(isrc=remote.isrc)
    return Track.objects.filter(match).first()


class FolderImporter:
    """Enlaza los ficheros de una carpeta con el catálogo dentro de una ejecución.

    Links the files of a folder to the catalogue inside a job run.

    Args:
        run: Ejecución que recibe el progreso y las líneas de log.
            Run receiving progress and log lines.
        deezer: Cliente de Deezer. / Deezer client.
        root: Carpeta de descargas tal como está en los ajustes; las rutas se guardan
            con ella delante, igual que las de la tarea de descarga.
            Downloads folder as set in the preferences; paths are stored under it,
            like the download task stores them.
    """

    def __init__(self, run: JobRun, deezer: DeezerClient, root: Path) -> None:
        """Prepara el importador. / Sets the importer up."""
        self.run = run
        self._deezer = deezer
        self._root = root
        self._importer = Importer(run, deezer)
        self.linked = 0
        self.already_linked = 0
        self.unlinked: list[dict[str, str]] = []

    def import_folder(self, folder: str) -> bool:
        """Recorre ``folder`` y enlaza cada fichero de audio.

        Walks ``folder`` and links every audio file.

        Returns:
            ``False`` si se pidió parar antes de acabar. / ``False`` if a stop cut it short.

        Raises:
            ValueError: Si la carpeta no es válida (ver :func:`resolve_folder`).
                If the folder is not valid (see :func:`resolve_folder`).
        """
        base = self._root.resolve()
        target = resolve_folder(self._root, folder)
        # ``rglob`` no entra en carpetas enlazadas; los ficheros enlazados se miran uno a uno.
        # ``rglob`` does not enter linked folders; linked files are checked one by one.
        files = sorted(
            p for p in target.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES and p.is_file()
        )
        for index, path in enumerate(files):
            if runner.should_stop(self.run):
                return False
            relative = path.relative_to(base)
            runner.progress(self.run, index, len(files), str(relative))
            self._link(path, relative)
        runner.progress(self.run, len(files), len(files))
        return True

    @property
    def counts(self) -> dict[str, Any]:
        """Contadores del catálogo y de los ficheros. / Catalogue and file counters."""
        return {
            **self._importer.counts,
            "linked": self.linked,
            "already_linked": self.already_linked,
            "unlinked": self.unlinked,
        }

    def _link(self, path: Path, relative: Path) -> None:
        """Enlaza un fichero o anota por qué no. / Links one file or records why not."""
        stored = str(self._root / relative)
        if Download.objects.filter(file_path=stored).exists():
            self.already_linked += 1
            return
        if not path.resolve().is_relative_to(self._root.resolve()):
            self._skip(relative, OUTSIDE)
            return
        try:
            tags = read_tags(path)
        except mutagen.MutagenError:
            self._skip(relative, UNREADABLE)
            return
        if tags is None:
            self._skip(relative, NO_TAGS)
            return
        try:
            track, reason = self._track_for(tags)
        except (DeezerError, requests.RequestException) as error:
            self._skip(relative, LOOKUP_ERROR, str(error))
            return
        if track is None:
            self._skip(relative, reason)
            return
        Download.objects.create(
            track=track, file_path=stored, audio_format=path.suffix.lower().lstrip(".")
        )
        self.linked += 1
        runner.line(self.run, JobRunLine.Level.INFO, f"{relative} → «{track.title}»")

    def _track_for(self, tags: Tags) -> tuple[Track | None, str]:
        """Canción del catálogo para las etiquetas, importando su álbum si falta.

        Catalogue track for the tags, importing its album when missing.

        Returns:
            La canción, o ``None`` y el motivo. / The track, or ``None`` and the reason.
        """
        remote = find_remote(self._deezer, tags)
        if remote is None:
            return None, NOT_FOUND
        track = _catalog_track(remote)
        if track is None and remote.album is not None:
            self._importer.import_album(self._deezer.get_album(remote.album.id))
            track = _catalog_track(remote)
        # Sin canción tras importar: álbum o canción bloqueados.
        # No track after importing: the album or track is blocked.
        return track, NOT_IN_CATALOG

    def _skip(self, relative: Path, reason: str, detail: str = "") -> None:
        """Anota un fichero no enlazado. / Records a file that was not linked."""
        self.unlinked.append({"file": str(relative), "reason": reason})
        message = f"{relative}: {reason}" + (f" ({detail})" if detail else "")
        runner.line(self.run, JobRunLine.Level.WARNING, message)
