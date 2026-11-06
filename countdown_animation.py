"""Animate only the timer bar, sharing the same frames in preview and export."""
from PIL import Image, ImageChops, ImageDraw


class CountdownAnimation:
    def __init__(self, full, empty, remaining, total):
        self.empty = empty
        self.remaining = remaining
        self.total = max(1, total)
        # Include color differences even when both RGBA layers have equal alpha.
        self.bounds = ImageChops.difference(full, empty).getbbox(alpha_only=False)
        self.full_patch = full.crop(self.bounds) if self.bounds else None
        self.empty_patch = empty.crop(self.bounds) if self.bounds else None

    def patch(self, elapsed):
        fraction = max(0, min(1, (self.remaining - elapsed) / self.total))
        if fraction <= 0:
            return self.empty_patch.copy()
        if fraction >= 1:
            return self.full_patch.copy()
        width, height = self.full_patch.size
        # Supersampling keeps subpixel movement smooth at small preview sizes.
        scale = 4
        mask = Image.new("L", (width * scale, height * scale))
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, width * scale * fraction, height * scale),
                               radius=height * scale / 2, fill=255)
        mask = mask.resize((width, height), Image.Resampling.LANCZOS)
        return Image.composite(self.full_patch, self.empty_patch, mask)

    def frame(self, elapsed):
        picture = self.empty.copy()
        if self.bounds:
            # Replacement preserves translucent edge pixels without doubling alpha.
            picture.paste(self.patch(elapsed), self.bounds)
        return picture

    def base_frame(self):
        picture = self.empty.copy()
        if self.bounds and picture.mode == "RGBA":
            # FFmpeg restores this rectangle with the animated patch before
            # compositing onto the moving background.
            picture.paste((0, 0, 0, 0), self.bounds)
        return picture
