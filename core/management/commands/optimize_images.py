"""Phase 9 image optimization pass for mirrored static assets.

The mirrored site ships 441 images (166 MB); the worst single PNG is 18.7 MB at
5242x3823 for a hero that never renders wider than ~1400px. This command
re-encodes oversized files **in place**, so every template reference keeps
working and no markup changes are needed:

  * downscales images larger than --max-dimension on their longest side
  * re-encodes PNG with optimize=True, JPEG with quality/progressive
  * leaves a file untouched when the saving is below --min-gain

Pillow is required by this command only; it is deliberately not a runtime
dependency of the site. Run `--dry-run` first.
"""
import os

from django.core.management.base import BaseCommand, CommandError

PNG = (".png",)
JPEG = (".jpg", ".jpeg")

DEFAULT_DIR = "static/images"


class Command(BaseCommand):
    help = "Downscale and re-encode oversized static images in place (Phase 9)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=DEFAULT_DIR, help="Directory to scan (default: static/images)")
        parser.add_argument("--max-dimension", type=int, default=1920, help="Longest side in pixels (default: 1920)")
        parser.add_argument("--min-gain", type=float, default=0.10, help="Skip files saving less than this fraction (default: 0.10)")
        parser.add_argument("--quality", type=int, default=82, help="JPEG quality (default: 82)")
        parser.add_argument("--min-bytes", type=int, default=150 * 1024, help="Ignore files smaller than this (default: 150 KB)")
        parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")

    def handle(self, *args, **options):
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise CommandError("Pillow is required for this command: pip install Pillow") from exc

        directory = options["dir"]
        if not os.path.isdir(directory):
            raise CommandError(f"Directory not found: {directory}")

        max_dim = options["max_dimension"]
        min_gain = options["min_gain"]
        quality = options["quality"]
        min_bytes = options["min_bytes"]
        dry = options["dry_run"]

        before_total = after_total = changed = scanned = 0
        rows = []

        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                ext = os.path.splitext(name)[1].lower()
                if ext not in PNG + JPEG:
                    continue
                path = os.path.join(root, name)
                original_bytes = os.path.getsize(path)
                if original_bytes < min_bytes:
                    continue
                scanned += 1
                try:
                    with Image.open(path) as probe:
                        width, height = probe.size
                        mode = probe.mode
                        probe.load()
                        image = probe.copy()
                except Exception as exc:  # unreadable file: report, never half-write
                    rows.append((path, original_bytes, original_bytes, f"SKIP ({exc.__class__.__name__})"))
                    continue

                scale = min(1.0, max_dim / max(width, height))
                new_size = (max(1, round(width * scale)), max(1, round(height * scale)))

                if ext in JPEG and mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                elif ext in PNG and mode == "P":
                    image = image.convert("RGBA")

                if new_size != (width, height):
                    image = image.resize(new_size, Image.LANCZOS)

                tmp_path = path + ".tmp"
                try:
                    if ext in JPEG:
                        image.save(tmp_path, "JPEG", quality=quality, optimize=True, progressive=True)
                    else:
                        image.save(tmp_path, "PNG", optimize=True, compress_level=9)
                    new_bytes = os.path.getsize(tmp_path)
                finally:
                    image.close()

                gain = 1 - (new_bytes / original_bytes) if original_bytes else 0
                resized = new_size != (width, height)

                if gain < min_gain and not resized:
                    os.remove(tmp_path)
                    rows.append((path, original_bytes, original_bytes, f"keep ({gain:.0%})"))
                    continue

                before_total += original_bytes
                after_total += new_bytes
                changed += 1
                rows.append(
                    (
                        path,
                        original_bytes,
                        new_bytes,
                        f"{width}x{height} -> {new_size[0]}x{new_size[1]}, -{gain:.0%}",
                    )
                )
                if dry:
                    os.remove(tmp_path)
                else:
                    os.replace(tmp_path, path)

        for path, before, after, note in rows:
            if note.startswith("keep") or note.startswith("SKIP"):
                continue
            self.stdout.write(f"{path}: {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB  [{note}]")

        saved = before_total - after_total
        verb = "would save" if dry else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"scanned {scanned} file(s) >= {min_bytes // 1024} KB; "
                f"{changed} {'eligible' if dry else 'rewritten'}; {verb} "
                f"{saved / 1e6:.2f} MB of {before_total / 1e6:.2f} MB"
            )
        )
