"""Draw an illustrative README animation; never present it as a live run recording.
Rebuild: uv run --with pillow python scripts/render_workflow_gif.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
MONO = Path("/System/Library/Fonts/Supplemental/Courier New.ttf")


def font(size: int, mono: bool = False):
    path = MONO if mono else FONT
    return (
        ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default(size=size)
    )


steps = [
    "Clone",
    "Reproduce",
    "Locate",
    "Diagnose",
    "Patch",
    "Validate",
    "Test",
    "Review",
    "Your approval",
]
messages = [
    "Read a clean repository checkout.",
    "Reproduce the same failure twice.",
    "Locate relevant production source.",
    "Explain a concise root-cause hypothesis.",
    "Propose one focused source edit.",
    "Check patch scope. Protect test files.",
    "Run pytest in a networkless sandbox.",
    "Explain test evidence and risks.",
    "Pause. Nothing is pushed without you.",
]
frames = []
for active in range(9):
    image = Image.new("RGB", (1080, 540), "#0B0D12")
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((28, 25, 1052, 515), radius=18, fill="#12151C", outline="#272B3A", width=1)
    d.rounded_rectangle((57, 53, 89, 85), radius=9, fill="#8B6BEF")
    d.text((67, 55), "ϟ", font=font(25), fill="white")
    d.text((102, 56), "devpilot.", font=font(23), fill="#E6E8EE")
    d.text((802, 64), "ILLUSTRATIVE WORKFLOW", font=font(11), fill="#929AAF")
    d.text((57, 118), "Ship the fix. Keep the control.", font=font(31), fill="#E6E8EE")
    d.text(
        (58, 164),
        "Python + pytest    /    Sandboxed execution    /    Human approval",
        font=font(13),
        fill="#929AAF",
    )
    for i, label in enumerate(steps):
        x = 64 + (i % 5) * 197
        y = 225 + (i // 5) * 93
        if i < 8 and i % 5 != 4:
            d.line(
                (x + 156, y + 25, x + 192, y + 25),
                fill="#625181" if i < active else "#2A2F3E",
                width=2,
            )
        d.rounded_rectangle(
            (x, y, x + 157, y + 53),
            radius=9,
            fill="#1E1B2D" if i == active else "#171A23",
            outline="#9C85FF" if i == active else "#35564F" if i < active else "#303546",
            width=2 if i == active else 1,
        )
        d.text(
            (x + 13, y + 18),
            ("✓" if i < active else str(i + 1)) + "  " + label,
            font=font(13),
            fill="#62DCB1" if i < active else "#C3ADFF" if i == active else "#929AAF",
        )
    d.rounded_rectangle((58, 423, 1020, 483), radius=9, fill="#0E1017", outline="#272B3A")
    d.ellipse((77, 448, 83, 454), fill="#EFC36B" if active == 8 else "#9C85FF")
    d.text((98, 442), messages[active], font=font(16), fill="#E6E8EE")
    frames.append(image)
output = ROOT / "docs" / "devpilot-workflow.gif"
frames[0].save(
    output,
    save_all=True,
    append_images=frames[1:],
    duration=[1000] * 8 + [3000],
    loop=0,
    optimize=True,
)
print(output)
