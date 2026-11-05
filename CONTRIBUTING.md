# Contributing to Music Logos

Thanks for your interest in improving the project. This guide covers how to report a problem and how to add or change a logo.

## Reporting a problem

[Open an issue](https://github.com/hannya-man/music-logos/issues) and include:

- The logo, variant and format affected, such as `clef-white.svg`
- What you expected and what you saw, with a screenshot if it helps
- For script errors, the full error message, your operating system and your Python version

## Setting up

```bash
git clone https://github.com/hannya-man/music-logos.git
cd music-logos
pip install -r requirements.txt
```

Rendering also needs a browser. See [Regenerating the assets](README.md#regenerating-the-assets).

## Adding a logo

Everything lives in [`generate.py`](generate.py), and the asset files are never edited by hand.

### 1. Define it

Add an entry to the **end** of the `MARKS` list:

```python
{"name": "my-logo", "strands": [
    (diamond(-100, 0, 220), "g"),
    (diamond(100, 0, 220), "s")]},
```

Each strand is a `(path, colour)` pair, where the colour is `"g"` for gold or `"s"` for silver.

Folder numbers come from a logo's position in the list, and the script does not delete old folders. Adding a logo anywhere but the end would renumber the ones after it and leave stale folders behind.

Coordinates are in pixels with y pointing down. Draw around the origin, and the script will centre the finished logo on the canvas.

### 2. Build its strands

Use the existing helpers:

| Helper | Draws |
| :----- | :---- |
| `line(*points, r=R)` | An open polyline with rounded corners |
| `poly(points, r=R, closed=False)` | A polyline that can be closed, with one radius or one per vertex |
| `diamond(cx, cy, h, r=R)` | A rounded diamond |
| `ring(cx, cy, r, start=0, sweep=360)` | A circle or an arc |
| `rrect(x0, y0, x1, y1, r=R)` | A rounded rectangle |
| `rot(path, degrees)` | A path rotated around the origin |
| `T(x, y, heading)` | A turtle for curves: `.f(distance)` moves forward and `.a_(radius, degrees)` draws an arc, with the result in `.segs` |
| `note_head(cx, cy, h)` | A diamond notehead, plus the x position where its stem leaves |
| `chevron(apex, t, side=1)` | A `>` shape, or `<` with `side=-1` |
| `dot(x, y)` | A small solid diamond |

Turtle headings are in degrees: 0 points east and 90 points south. Positive arc angles turn clockwise.

### 3. Control the weave (optional)

Crossings alternate between over and under by default. To change that, add one of these keys to the logo's entry:

| Key | Effect |
| :-- | :----- |
| `"flip": True` | Swaps which strand goes over at each crossing |
| `"top": "g"` or `"top": "s"` | Keeps that colour on top at every crossing |
| `"nudge": (dx, dy)` | Moves the logo from its centred position, for optical balance |

Strands of the same colour are not woven, so they simply overlap where they meet.

### 4. Preview it

A contact sheet is the fastest way to iterate:

```bash
python generate.py --sheet sheet.png
```

### 5. Export and commit

```bash
python generate.py
```

This rewrites every asset, so your change should only add the new folder and update `preview.png`. If other files show up as changed, mention it in your pull request, as your browser may render them differently.

Finally, add the logo to [the table in the README](README.md#the-logos).

## Design rules

The script enforces these and stops with an error if one is broken:

| Rule | If it fails |
| :--- | :---------- |
| Gold and silver strands cross at more than 80° | Redraw the crossing closer to square, so the cut ends sit parallel to the strand on top |
| Pieces left after splitting are longer than 20 px | Move the crossing further from its neighbour or the strand's end |
| The logo is at least 150 px from every edge | Make the logo smaller |
| Opposite margins differ by no more than 4 px | Reduce any `nudge` |
| Each PNG is 1024 × 1024, with the correct background and colours | Check your browser path and the export code |

These are not enforced, but please keep to them as well:

- Use the shared stroke width (`W`), weave gap (`G`) and colours, so that the family stays consistent.
- Use only gold and silver strands, with at least one of each.
- Check that the logo is still recognisable at small sizes, such as 64 px.

## Submitting a pull request

1. Create a branch for your change.
2. Keep each pull request to one logo or one fix.
3. Include the regenerated assets, so they stay in sync with the script.
4. Describe your change, and add a screenshot if a logo's appearance changed.

By contributing, you agree that your work will be released under the project's [MIT License](LICENSE).
